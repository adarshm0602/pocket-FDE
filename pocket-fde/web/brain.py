"""Shared learning: immutable submissions and one explicit human decision.

Uses the existing private store, not the deployment's temporary filesystem.
Analysis history remains browser-scoped; reviewed learning is shared by the demo.
"""
import json
import hashlib
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from pocketfd.knowledge import Item
from pocketfd.redact import Redactor
from web.storage import WorkspaceStore

NOTE_ID = re.compile(r"^[a-f0-9]{32}$")


class ReviewConflict(Exception):
    pass


class BrainFull(Exception):
    pass


class BrainStore(WorkspaceStore):
    # Separate namespace allows isolated staging checks without touching live learning.
    @property
    def prefix(self):
        prefix = os.getenv("POCKET_FDE_BRAIN_NAMESPACE", "second-brain-v1")
        if not re.fullmatch(r"[a-z0-9-]{1,80}", prefix):
            raise ValueError("Invalid knowledge namespace")
        return prefix

    def _key(self, group, note_id):
        if not NOTE_ID.fullmatch(note_id):
            raise ValueError("Invalid learning identifier")
        return f"{self.prefix}/{group}/{note_id}.json"

    def _read(self, key):
        if os.getenv("VERCEL") and not self.token:
            raise RuntimeError("Private cloud storage is not configured")
        if self.token:
            from vercel.blob.errors import BlobNotFoundError
            with self._client() as client:
                try:
                    # A missing decision can have been cached before approval.
                    # Read the origin so a newly created decision is immediate.
                    result = client.get(key, access="private", use_cache=False)
                except BlobNotFoundError:
                    return None
                if result is None:
                    return None
                if result.status_code != 200:
                    raise RuntimeError("Knowledge storage returned an incomplete response")
                return json.loads(result.content)
        path = self.root / key
        return json.loads(path.read_bytes()) if path.exists() else None

    def _create(self, key, data):
        if os.getenv("VERCEL") and not self.token:
            raise RuntimeError("Private cloud storage is not configured")
        content = json.dumps(data, ensure_ascii=False).encode()
        if self.token:
            with self._client() as client:
                client.put(key, content, access="private", content_type="application/json", overwrite=False)
        else:
            path = self.root / key
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open("xb") as stream:
                os.chmod(path, 0o600)
                stream.write(content)

    def list_notes(self):
        if os.getenv("VERCEL") and not self.token:
            raise RuntimeError("Private cloud storage is not configured")
        prefix = f"{self.prefix}/submissions/"
        if self.token:
            with self._client() as client:
                ids = [obj.pathname.rsplit("/", 1)[-1][:-5] for obj in client.iter_objects(prefix=prefix)]
        else:
            ids = [path.stem for path in (self.root / prefix).glob("*.json")]
        ids = [note_id for note_id in ids if NOTE_ID.fullmatch(note_id)]
        if self.token and ids:
            with ThreadPoolExecutor(max_workers=8) as pool:
                notes = list(pool.map(self.get_note, ids))
        else:
            notes = [self.get_note(note_id) for note_id in ids]
        return sorted((note for note in notes if note), key=lambda note: note["created_at"], reverse=True)

    def get_note(self, note_id):
        note = self._read(self._key("submissions", note_id))
        if not note:
            return None
        decision = self._read(self._key("decisions", note_id))
        return {**note, "status": decision["status"] if decision else "pending", "review": decision}

    def submit(self, fields):
        if len(self.list_notes()) >= 200:
            raise BrainFull("This demo holds up to 200 shared learnings. Contact the maintainer before adding more.")
        note_id = uuid4().hex
        self._create(self._key("submissions", note_id), {
            **fields, "id": note_id, "created_at": time.time(),
        })
        return self.get_note(note_id)

    def capture_analysis(self, incident, analysis):
        """Draft from the measured analysis, without another model call.

        Deduplicate by incident facts, not a model's changing wording or corpus
        revision. Re-analysis never overwrites a human review decision. New
        evidence/version/context creates a new draft for the new investigation.
        """
        identity = {key: incident.get(key) for key in
                    ("id", "title", "description", "version", "customer_tier", "provided_evidence")}
        note_id = hashlib.sha256(("analysis-learning-v1:" + json.dumps(identity, sort_keys=True)).encode()).hexdigest()[:32]
        existing = self.get_note(note_id)
        if existing:
            return existing, False
        if len(self.list_notes()) >= 200:
            raise BrainFull("The shared learning queue is full. The analysis still works; contact the maintainer to expand storage.")
        result = analysis["result"]
        redactor = Redactor()
        def sanitize(text):
            text = re.sub(r"\bAIza[A-Za-z0-9_-]{20,}\b", "[API_KEY]", text)
            text = re.sub(r"(?i)\b(api[_ -]?key|access[_ -]?token|password|secret|authorization)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", text)
            for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "XAI_API_KEY", "POCKET_FDE_ACCESS_CODE", "POCKET_FDE_SESSION_KEY", "BLOB_READ_WRITE_TOKEN"):
                secret = os.getenv(name, "")
                if len(secret) >= 8:
                    text = text.replace(secret, "[REDACTED]")
            return redactor.redact(text)
        title = sanitize("Investigation: " + incident["title"])[:180]
        lines = [
            "AUTOMATIC PROVISIONAL DRAFT — not a confirmed resolution.",
            "Check independent incident evidence before approving. Model hypotheses and proposed fixes are unverified.",
            "Recognized identifiers are masked; review for any remaining sensitive details.",
            f"\nIncident: {incident['title']}", f"Platform version supplied: {incident['version']}",
            "\nEvidence boundary: Raw incident descriptions and supplied logs are omitted from this shared draft. Consult the original investigation and verify the diagnostic references below.",
            f"\nOwner hypothesis: {result.get('owning_team') or 'Unassigned'} ({result.get('confidence', 'low')} confidence)",
            f"Reasoning:\n{result.get('reasoning', '')}",
            "\nHypotheses (unverified):\n" + "\n".join(str(h.get("text", "")) for h in result.get("hypotheses", [])),
            "\nQuestions still to verify:\n" + "\n".join(q["text"] for q in result.get("questions", [])),
            "\nLogs to check: " + ", ".join(log["stream"] for log in result.get("logs_to_check", [])),
            "Flags to check: " + ", ".join(result.get("flags_to_check", [])),
            f"\nSuggested next step (not verified):\n{result.get('recommended_fix') or 'Collect evidence first.'}",
            f"Version caveat: {result.get('version_caveat') or 'Confirm applicability before using this guidance.'}",
            "\nRetrieved source IDs: " + ", ".join(source["id"] for source in analysis.get("sources", [])),
        ]
        if result.get("escalate") or result.get("grounding_issues") or not result.get("diagnostics_complete", False):
            lines += ["\nREVIEW WARNING: This analysis has unresolved evidence or validation gaps.",
                      result.get("escalation_reason", ""), *result.get("grounding_issues", [])]
        content = sanitize("\n".join(lines))
        if len(content) > 12000:
            content = content[:11850] + "\n[Draft shortened. Consult the original investigation for the complete evidence.]"
        fields = {"title": title, "author": "Pocket FDE (automatic draft)", "content": content,
                  "versions": [incident["version"]], "origin": "analysis",
                  "source_case": sanitize(incident["id"]),
                  "model": analysis.get("model"), "retrieval_mode": analysis.get("retrieval_mode"),
                  "knowledge_revision": analysis.get("knowledge_revision"),
                  "id": note_id, "created_at": time.time()}
        key = self._key("submissions", note_id)
        try:
            self._create(key, fields)
        except Exception:
            # A concurrent completion may already have queued these incident facts.
            existing = self.get_note(note_id)
            if existing:
                return existing, False
            raise
        return self.get_note(note_id), True

    def review(self, note_id, fields):
        note = self.get_note(note_id)
        if not note:
            return None
        if note["status"] != "pending":
            raise ReviewConflict("This learning has already been reviewed. Refresh to see the decision.")
        key = self._key("decisions", note_id)
        try:
            self._create(key, {**fields, "reviewed_at": time.time()})
        except Exception:
            if self._read(key) is not None:
                raise ReviewConflict("Another reviewer has already recorded a decision. Refresh to see it.") from None
            raise
        return self.get_note(note_id)

    def approved_items(self, notes=None):
        items = []
        for note in self.list_notes() if notes is None else notes:
            if note["status"] != "approved":
                continue
            caveat = "" if note["versions"] else "Version applicability is not established for this learning; confirm before applying it."
            items.append(Item(f"WEB-NOTE:{note['id']}", "note",
                              f"learning: {note['title']}\n{note['content']}",
                              versions=note["versions"], visibility="internal",
                              meta={"title": note["title"], "author": note["author"],
                                    "reviewed_by": note["review"]["reviewer"],
                                    "review_reason": note["review"]["reason"],
                                    "reviewed_at": note["review"]["reviewed_at"],
                                    "source_path": f"Second Brain / {note['title']}",
                                    "version_caveat": caveat}))
        return items
