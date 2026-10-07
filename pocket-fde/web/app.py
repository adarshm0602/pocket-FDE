"""Serve a local UI over Surya's existing retrieval -> redaction -> triage pipeline."""
import json
import os
import secrets
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env")

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from pocketfd.knowledge import load_all, fingerprint
from pocketfd.known import OWN, VERSIONS
from pocketfd.llm import LLMError, extract_json
from pocketfd.retrieval import Index
from pocketfd.router import Router
from pocketfd.triage import case_text, triage
from web.provider import PROVIDERS, Provider, claude_logged_in, default_provider
from web.hybrid import HybridIndex, MODEL as EMBEDDING_MODEL, REVISION as EMBEDDING_REVISION, available as hybrid_available
from web.security import AUTH_TTL, authorized, require_access, seal, unseal, set_cookie, workspace_id
from web.storage import WorkspaceStore, RECORD, DemoLimit
from web.brain import BrainStore, BrainFull, ReviewConflict

app = FastAPI(title="Pocket FDE", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv("WEB_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,*.vercel.app").split(","))
app.mount("/assets", StaticFiles(directory=ROOT / "web/static"), name="assets")
INDEX = Index(load_all(include_pending=False))  # Preserve Surya's existing BM25 + TF-IDF index.
INDEX.corpus_revision = fingerprint(INDEX.items)
HYBRID_INDEX = None
PUBLIC_INDEX = INDEX
PUBLIC_HYBRID_INDEX = None
HYBRID_LOCK = threading.RLock()
SEARCH_MODES = {"surya": {"id": "surya", "label": "Keyword search", "method": "BM25 + TF-IDF",
                          "description": "Search exact terms using the existing pipeline."},
                "hybrid": {"id": "hybrid", "label": "Hybrid search", "method": "BM25 + MiniLM embeddings",
                           "description": "Search exact terms and related meanings using local embeddings."}}
LOG_DIR = Path(os.getenv("POCKET_FDE_LOG_DIR", str(Path(tempfile.gettempdir()) / "pocket-fde-web-logs")))
SESSIONS = {}  # Session-scoped keys, in memory only. Cleared on restart and after 8 hours.
SESSION_TTL = 8 * 60 * 60


class AccessRequest(BaseModel):
    code: str = Field(max_length=150, repr=False)


class LearningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=180)
    content: str = Field(min_length=20, max_length=12000)
    author: str = Field(min_length=2, max_length=80)
    versions: list[Literal["v1", "v2", "v3"]] = Field(default_factory=list, max_length=3)

    @field_validator("versions")
    @classmethod
    def unique_versions(cls, values):
        return sorted(set(values))


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["approved", "rejected"]
    reviewer: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=5, max_length=2000)
    verified: bool = False


def brain_call(method, *args):
    try:
        return method(*args)
    except (BrainFull, ReviewConflict) as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Second Brain storage is temporarily unavailable. Keep your draft and try again; no unreviewed knowledge will be used.") from exc


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    # FastAPI's default errors echo invalid input, which can include an API key.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()
    ]})


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(default="CUSTOM", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=3, max_length=250)
    description: str = Field(min_length=10, max_length=12000)
    version: Literal["v1", "v2", "v3"] | None = None
    customer_tier: Literal["standard", "enterprise"] = "standard"
    provided_evidence: list[str] = Field(default_factory=list, max_length=50)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str | None = Field(default=None, max_length=80, pattern=r"^CASE-[A-Za-z0-9_-]+$")
    incident: Incident | None = None
    retrieval: Literal["surya", "hybrid"] = "surya"


class SettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    provider: Literal["groq", "gemini", "xai", "claude_cli"]
    model: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9._:/-]+$")
    api_key: str = Field(default="", max_length=1000, repr=False)


class Question(BaseModel):
    text: str
    evidence: str | None = None


class ModelAnswer(BaseModel):
    """Reject malformed JSON before it reaches the existing triage post-processor."""
    model_config = ConfigDict(extra="allow")
    owning_team: str | None = None
    confidence: Literal["high", "medium", "low"]
    reasoning: str = ""
    hypotheses: list[dict] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list, max_length=6)
    logs_to_check: list[str] = Field(default_factory=list)
    flags_to_check: list[str] = Field(default_factory=list)
    recommended_fix: str = ""
    version_caveat: str = ""
    do_not_apply: list[str] = Field(default_factory=list)
    handover: dict | None = None
    escalate: bool = False
    escalation_reason: str = ""


@app.middleware("http")
async def local_origin_guard(request, call_next):
    origin = request.headers.get("origin")
    expected = f"https://{request.headers.get('host')}" if os.getenv("VERCEL") else str(request.base_url).rstrip("/")
    if request.method not in ("GET", "HEAD") and origin and origin.rstrip("/") != expected:
        return JSONResponse(status_code=403, content={"detail": "Open the app directly to make this request."})
    if request.url.path in {"/api/analyze", "/api/settings", "/api/history", "/api/brain"} or request.url.path.startswith(("/api/history/", "/api/brain/")):
        if not authorized(request):
            return JSONResponse(status_code=401, content={"detail": "Enter the demo access code to analyze and save work."})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response


def session_provider(request):
    if os.getenv("VERCEL"):
        if not authorized(request):
            current = default_provider()
            return Provider(current.name, current.model)
        data = unseal(request.cookies.get("pocketfde_session"), "provider", SESSION_TTL)
        if data and data.get("name") in PROVIDERS and data["name"] != "claude_cli":
            return Provider(data["name"], data["model"], data["key"])
        return default_provider()
    now = time.monotonic()
    for token in list(SESSIONS):
        if SESSIONS[token][1] < now:
            del SESSIONS[token]
    entry = SESSIONS.get(request.cookies.get("pocketfde_session"))
    return entry[0] if entry else default_provider()


def provider_status(provider):
    ready = claude_logged_in() if provider.name == "claude_cli" else bool(provider.key)
    return {"provider": provider.name, "label": PROVIDERS[provider.name]["label"], "model": provider.model,
            "fallback_model": provider.fallback_model,
            "ready": ready, "message": "Ready to analyze" if ready else "Connect a model to analyze cases"}


def case_catalog():
    cases = []
    # Demo cases shown in the meeting, plus 8 held-out cases. No resolution notes or ground truth.
    for folder in (ROOT / "cases", ROOT / "cases/heldout"):
        for path in sorted(folder.glob("CASE-*.json")):
            data = json.loads(path.read_text())
            recorded = data.get("evidence") or {}
            evidence = list(data.get("provided_evidence", recorded.get("logs", [])))
            for field in ("working_instance", "failing_instance", "configuration", "instance_configs"):
                if field in recorded:
                    value = recorded[field]
                    evidence.append(f"{field}: {json.dumps(value) if isinstance(value, dict) else value}")
            for field, finding in (data.get("validated_findings") or {}).items():
                if isinstance(finding, dict):
                    evidence.append(f"{field}: {finding.get('status', '')}; {finding.get('evidence', '')}")
            resolution = data.get("root_cause")
            resolved = isinstance(resolution, dict) and resolution.get("status") == "RESOLVED"
            cases.append({"id": data.get("id", data.get("case_number")), "title": data["title"],
                          "description": data["description"], "version": data.get("version"),
                          "status": data.get("status", "RESOLVED" if resolved else "OPEN"),
                          "customer_tier": data.get("customer_tier", "standard"), "provided_evidence": evidence})
    return cases


def resolve_case(payload):
    if bool(payload.case_id) == bool(payload.incident):
        raise HTTPException(422, "Choose either a case or a custom issue.")
    if payload.incident:
        case = payload.incident.model_dump()
        if any(len(line) > 2000 for line in case["provided_evidence"]):
            raise HTTPException(422, "Each evidence line must be at most 2,000 characters.")
        return case
    case = next((c for c in case_catalog() if c["id"] == payload.case_id), None)
    if case is None:
        raise HTTPException(404, "Case not found. Choose one from the case library.")
    return case


def refresh_knowledge(shared=True, learned_items=None):
    global INDEX, HYBRID_INDEX, PUBLIC_INDEX, PUBLIC_HYBRID_INDEX
    with HYBRID_LOCK:
        items = load_all(include_pending=False)
        if not shared:
            revision = fingerprint(items)
            if revision != PUBLIC_INDEX.corpus_revision:
                PUBLIC_INDEX = Index(items)
                PUBLIC_INDEX.corpus_revision = revision
                PUBLIC_HYBRID_INDEX = None
            return PUBLIC_INDEX
        items += brain_call(BrainStore().approved_items) if learned_items is None else learned_items
        revision = fingerprint(items)
        if revision != INDEX.corpus_revision:
            INDEX = Index(items)
            INDEX.corpus_revision = revision
            HYBRID_INDEX = None
        return INDEX


def index_for(mode, shared=True):
    global HYBRID_INDEX, PUBLIC_HYBRID_INDEX
    current = refresh_knowledge(shared)
    if mode == "surya":
        return current
    if not hybrid_available():
        raise HTTPException(503, "Hybrid search needs its local model. Run Setup Hybrid Search.command in the project folder, then refresh this page.")
    with HYBRID_LOCK:
        dense = HYBRID_INDEX if shared else PUBLIC_HYBRID_INDEX
        if dense is None or getattr(dense, "corpus_revision", current.corpus_revision) != current.corpus_revision:
            try:
                dense = HybridIndex(current.items)
                dense.corpus_revision = current.corpus_revision
                if shared:
                    HYBRID_INDEX = dense
                else:
                    PUBLIC_HYBRID_INDEX = dense
            except Exception as exc:
                raise HTTPException(503, "The local search model could not load. Run Setup Hybrid Search.command again, then retry.") from exc
    return dense


def sources_for(case, ids=None, index=None):
    index = index if index is not None else INDEX
    if case.get("version"):
        hits = index.search(case_text(case), case["version"], k=8, include_pending=False)
    else:
        # Inspect evidence without assuming a platform version. Analysis still requires one.
        candidates = {}
        for version in VERSIONS:
            for hit in index.search(case_text(case), version, k=8, include_pending=False):
                if hit.item.id not in candidates or hit.score > candidates[hit.item.id].score:
                    candidates[hit.item.id] = hit
        hits = sorted(candidates.values(), key=lambda h: -h.score)[:8]
    if ids is not None:
        hits = [h for h in hits if h.item.id in ids]
    return [{"id": h.item.id, "kind": h.item.kind, "text": h.item.text, "versions": h.item.versions,
             "status": h.item.status, "version_match": h.version_match if case.get("version") else None,
             "source_path": h.item.meta.get("source_path"),
             "caveat": "; ".join(filter(None, [h.caveat if case.get("version") else "Platform version is not supplied; confirm applicability.", h.item.meta.get("version_caveat")]))} for h in hits]


@app.get("/")
def home():
    return FileResponse(ROOT / "web/static/index.html")


@app.get("/api/status")
def status(request: Request):
    index = refresh_knowledge(shared=authorized(request))
    return {"model": provider_status(session_provider(request)), "backend": "Surya's existing pipeline",
            "retrieval": "BM25 + TF-IDF", "knowledge_items": len(index.items),
            "cards": sum(i.kind == "card" for i in index.items), "notes": sum(i.kind == "note" for i in index.items),
            "knowledge_revision": index.corpus_revision,
            "access_required": not authorized(request), "storage": WorkspaceStore().mode,
            "knowledge_sources": [{"id": i.id, "kind": i.kind, "versions": i.versions} for i in index.items],
            "retrieval_modes": [{**spec, "ready": mode == "surya" or hybrid_available()} for mode, spec in SEARCH_MODES.items()],
            "providers": [{"id": k, "label": v["label"], "default_model": v["model"]} for k, v in PROVIDERS.items()
                          if not os.getenv("VERCEL") or k != "claude_cli"]}


@app.post("/api/access")
def unlock(payload: AccessRequest, request: Request, response: Response):
    code = os.getenv("POCKET_FDE_ACCESS_CODE", "")
    if not code or not secrets.compare_digest(payload.code, code):
        raise HTTPException(401, "That access code is not valid.")
    set_cookie(response, request, "pocketfde_access", seal("access", code), AUTH_TTL)
    return {"ok": True}


@app.get("/api/history")
def history(request: Request, response: Response):
    identity = workspace_id(request, response)
    try:
        return {"records": WorkspaceStore().recent(identity)}
    except Exception as exc:
        raise HTTPException(503, "Saved analyses are temporarily unavailable. Your current work is still in this browser.") from exc


@app.get("/api/history/{record}")
def saved_analysis(record: str, request: Request):
    if not RECORD.fullmatch(record):
        raise HTTPException(404, "Saved analysis not found.")
    try:
        data = WorkspaceStore().get(workspace_id(request), record)
    except Exception as exc:
        raise HTTPException(503, "This saved analysis could not be loaded.") from exc
    if data is None:
        raise HTTPException(404, "Saved analysis not found.")
    return data


def capture_learning(case, analysis):
    try:
        note, created = BrainStore().capture_analysis(case, analysis)
        return {"id": note["id"], "status": note["status"], "created": created,
                "message": "A provisional learning was automatically queued for human review." if created else
                "These incident facts already have a learning. The existing review decision is preserved."}
    except Exception:
        return {"id": None, "status": "failed",
                "message": "The analysis completed, but its learning draft could not be saved. Retry saving the draft without another model call."}


@app.post("/api/history/{record}/learning")
def retry_learning(record: str, request: Request):
    saved = saved_analysis(record, request)
    learning = capture_learning(saved["incident"], saved["analysis"])
    if learning["status"] == "failed":
        raise HTTPException(503, "The learning draft could not be saved. Storage may be unavailable or the shared queue full; try later.")
    return learning


@app.get("/api/cases")
def cases():
    return {"cases": case_catalog()}


@app.get("/api/brain")
def brain_library():
    notes = brain_call(BrainStore().list_notes)
    index = refresh_knowledge(learned_items=BrainStore().approved_items(notes))
    sources = []
    for item in index.items:
        title = item.meta.get("title") or item.meta.get("description")
        if not title:
            title = item.text.splitlines()[0].removeprefix("Customer guide: ").removeprefix("symptom: ").removeprefix("learning: ")
            if item.kind == "flag":
                title = ("Configuration change: " if item.id.startswith("FLAG-CHANGE:") else "Configuration: ") + item.id.split(":", 1)[1]
            elif item.kind == "obs":
                title = "Team " + item.id.split(":", 1)[1] + " logs and observability"
            elif item.kind == "ownership":
                title = "Ownership: " + item.id.split(":", 1)[1].removeprefix("ambiguous:")
            elif item.kind == "version":
                title = "Platform " + item.versions[0]
        sources.append({"id": item.id, "title": title[:180], "kind": item.kind,
                        "content": item.text, "versions": item.versions, "status": "approved",
                        "source_path": item.meta.get("source_path"),
                        "caveat": item.meta.get("version_caveat", ""),
                        "web_id": item.id.removeprefix("WEB-NOTE:") if item.id.startswith("WEB-NOTE:") else None})
    order = {"note": 0, "card": 1, "doc": 2, "flag": 3, "obs": 4, "ownership": 5, "version": 6}
    sources.sort(key=lambda source: (0 if source["web_id"] else 1, order.get(source["kind"], 7), source["title"].lower()))
    return {"sources": sources, "learnings": notes, "knowledge_revision": index.corpus_revision,
            "storage": BrainStore().mode}


@app.post("/api/brain/learnings", status_code=201)
def submit_learning(payload: LearningRequest):
    return brain_call(BrainStore().submit, payload.model_dump())


@app.post("/api/brain/learnings/{note_id}/review")
def review_learning(note_id: str, payload: ReviewRequest):
    from web.brain import NOTE_ID
    if not NOTE_ID.fullmatch(note_id):
        raise HTTPException(404, "Learning not found.")
    if payload.status == "approved" and not payload.verified:
        raise HTTPException(422, "Verify the evidence and version scope before approving this learning.")
    note = brain_call(BrainStore().review, note_id, payload.model_dump(exclude={"verified"}))
    if note is None:
        raise HTTPException(404, "Learning not found.")
    return note


@app.post("/api/context")
def context(payload: AnalysisRequest, request: Request):
    case = resolve_case(payload)
    index = index_for(payload.retrieval, shared=authorized(request))
    return {"case": case, "sources": sources_for(case, index=index), "retrieval": SEARCH_MODES[payload.retrieval]["method"],
            "retrieval_mode": payload.retrieval, "knowledge_revision": getattr(index, "corpus_revision", None)}


@app.post("/api/settings")
def settings(payload: SettingsRequest, request: Request, response: Response):
    if os.getenv("VERCEL") and payload.provider == "claude_cli":
        raise HTTPException(422, "Claude Code is available only in the local app.")
    previous = session_provider(request)
    key = payload.api_key or (previous.key if previous.name == payload.provider else "")
    provider = Provider(payload.provider, payload.model, key)
    if provider.name != "claude_cli" and not key:
        raise HTTPException(422, "Enter an API key to connect this provider.")
    if provider.name == "claude_cli" and not claude_logged_in():
        raise HTTPException(422, "Claude Code is not logged in. Run claude auth login in Terminal first.")
    reserve_model_call(request, response)
    try:
        result = provider.complete('Return JSON only: {"ok": true}', "You are testing a model connection. Reply with valid JSON.")
        if extract_json(result.text).get("ok") is not True:
            raise LLMError("The model did not pass the connection check. Check the model ID and try again.")
    except (LLMError, ValueError, AttributeError) as exc:
        raise HTTPException(502, str(exc)) from exc
    if os.getenv("VERCEL"):
        token = seal("provider", {"name": provider.name, "model": provider.model, "key": provider.key})
        set_cookie(response, request, "pocketfde_session", token, SESSION_TTL)
        return {"model": provider_status(provider), "connection_tokens": result.input_tokens + result.output_tokens}
    token = request.cookies.get("pocketfde_session")
    if token not in SESSIONS:
        if len(SESSIONS) >= 100:
            raise HTTPException(503, "Too many active sessions. Restart the local app to reset them.")
        token = secrets.token_urlsafe(32)
    SESSIONS[token] = (provider, time.monotonic() + SESSION_TTL)
    response.set_cookie("pocketfde_session", token, httponly=True, samesite="strict", secure=request.url.scheme == "https", max_age=SESSION_TTL)
    return {"model": provider_status(provider), "connection_tokens": result.input_tokens + result.output_tokens}


@app.delete("/api/settings")
def disconnect(request: Request, response: Response):
    SESSIONS.pop(request.cookies.get("pocketfde_session"), None)
    response.delete_cookie("pocketfde_session")
    return {"model": provider_status(default_provider())}


def reserve_model_call(request, response):
    try:
        WorkspaceStore().reserve_model_call(workspace_id(request, response))
    except DemoLimit as exc:
        raise HTTPException(429, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "The demo could not check its usage budget. Please retry later.") from exc


@app.post("/api/analyze")
def analyze(payload: AnalysisRequest, request: Request, response: Response):
    case = resolve_case(payload)
    if case.get("version") not in VERSIONS:
        raise HTTPException(422, "Confirm the platform version (v1, v2 or v3) before analyzing this case. You can inspect sources without it.")
    index = index_for(payload.retrieval)
    provider = session_provider(request)
    if not provider_status(provider)["ready"]:
        raise HTTPException(503, "Connect a model in Model settings before analyzing. You can inspect retrieved sources without a model.")
    reserve_model_call(request, response)

    def validate_answer(answer):
        return ModelAnswer.model_validate(answer).model_dump()

    started = time.monotonic()
    router = Router(tier_mode="frontier_only", completion=provider.complete, outbound_log=LOG_DIR / "outbound.jsonl")
    try:
        result = triage(case, index, router, include_pending=False, min_questions=3, answer_validator=validate_answer)
    except (LLMError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise HTTPException(502, "Analysis could not finish. Check the model connection and try again.") from exc
    if not router.calls:
        message = result.get("escalation_reason", "The model could not complete the analysis.")
        raise HTTPException(502, message.removeprefix("model output unusable: "))
    if not result["model_answer_valid"]:
        raise HTTPException(502, "The model returned an incomplete analysis after one repair attempt. Try again or select a different model.")
    if result["invented_names"]:
        result.update(escalate=True, confidence="low", recommended_fix="No verified fix available; collect more evidence.",
                      escalation_reason="The model used names outside the platform definitions. A human should review the evidence.")
    models_used = list(dict.fromkeys(call["provider"].split(":", 1)[-1] for call in router.calls))
    data = {"result": result, "sources": sources_for(case, result["retrieval"]["ids"], index=index),
            "team_name": OWN["teams"].get(result["owning_team"], {}).get("name"),
            "elapsed_s": round(time.monotonic() - started, 2), "model": " + ".join(models_used),
            "models_used": models_used, "requested_model": provider.model,
            "fallback_used": bool(provider.fallback_model and provider.fallback_model in models_used),
            "provider": PROVIDERS[provider.name]["label"], "retrieval": SEARCH_MODES[payload.retrieval]["method"],
            "retrieval_mode": payload.retrieval,
            "knowledge_revision": getattr(index, "corpus_revision", None),
            "embedding_model": EMBEDDING_MODEL if payload.retrieval == "hybrid" else None,
            "embedding_revision": EMBEDDING_REVISION if payload.retrieval == "hybrid" else None}
    data["learning"] = capture_learning(case, data)
    try:
        data["saved_id"] = WorkspaceStore().save(workspace_id(request, response), case, data)
        data["save_status"] = "Saved privately"
    except Exception:
        # Never discard a successful, billable analysis because storage is down.
        data["save_status"] = "Cloud save failed; this result is kept in your browser. Copy it as a backup."
    return data
