"""Exercise durable human review, shared access and live retrieval boundaries."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from web import app as module
from web.brain import BrainStore, ReviewConflict
from pocketfd.retrieval import Index
from pocketfd.llm import LLMResult, LLMError
from web.provider import Provider

DRAFT = {"title": "Quartz sentinel rewrite evidence", "author": "Demo engineer",
         "content": "Quartz sentinel requests lose rewrite context on v2. Verified g.rewrite shows an empty query; use single_shot only after confirming missing session context.",
         "versions": ["v2"]}
APPROVE = {"status": "approved", "reviewer": "Demo reviewer",
           "reason": "Confirmed rewrite logs and v2 applicability against the incident evidence.", "verified": True}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("POCKET_FDE_ACCESS_CODE", raising=False)
    monkeypatch.setenv("POCKET_FDE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(module, "INDEX", module.INDEX)
    monkeypatch.setattr(module, "PUBLIC_INDEX", module.PUBLIC_INDEX)
    monkeypatch.setattr(module, "HYBRID_INDEX", None)
    monkeypatch.setattr(module, "PUBLIC_HYBRID_INDEX", None)
    with TestClient(module.app) as client:
        yield client


def test_pending_persists_across_clients_without_entering_search(client):
    before = module.refresh_knowledge().corpus_revision
    note = client.post("/api/brain/learnings", json=DRAFT).json()
    assert note["status"] == "pending" and note["review"] is None
    assert BrainStore().get_note(note["id"])["content"] == DRAFT["content"]
    with TestClient(module.app) as teammate:
        assert teammate.get("/api/brain").json()["learnings"][0]["id"] == note["id"]
    assert module.refresh_knowledge().corpus_revision == before
    assert all("Quartz sentinel" not in item.text for item in module.INDEX.items)


def test_approval_requires_verification_and_refreshes_both_indexes(client, monkeypatch):
    class TestHybrid(Index):
        pass
    monkeypatch.setattr(module, "hybrid_available", lambda: True)
    monkeypatch.setattr(module, "HybridIndex", TestHybrid)
    before = module.index_for("hybrid").corpus_revision
    note = client.post("/api/brain/learnings", json=DRAFT).json()
    path = f"/api/brain/learnings/{note['id']}/review"
    assert client.post(path, json={**APPROVE, "verified": False}).status_code == 422
    response = client.post(path, json=APPROVE)
    assert response.status_code == 200 and response.json()["status"] == "approved"
    source_id = "WEB-NOTE:" + note["id"]
    keyword = module.index_for("surya")
    hybrid = module.index_for("hybrid")
    assert keyword.corpus_revision == hybrid.corpus_revision != before
    for index in (keyword, hybrid):
        assert source_id in {hit.item.id for hit in index.search("Quartz sentinel rewrite evidence", "v2", k=8, include_pending=False)}
    assert BrainStore().get_note(note["id"])["review"]["reviewer"] == APPROVE["reviewer"]
    assert client.post(path, json={**APPROVE, "status": "rejected"}).status_code == 409
    assert BrainStore().get_note(note["id"])["status"] == "approved"


def test_rejection_is_retained_without_changing_knowledge(client):
    revision = module.refresh_knowledge().corpus_revision
    note = client.post("/api/brain/learnings", json={**DRAFT, "versions": []}).json()
    response = client.post(f"/api/brain/learnings/{note['id']}/review", json={**APPROVE, "status": "rejected", "verified": False})
    assert response.status_code == 200
    assert client.get("/api/brain").json()["learnings"][0]["status"] == "rejected"
    assert module.refresh_knowledge().corpus_revision == revision


def test_unknown_scope_is_preserved_in_approved_source(client):
    note = client.post("/api/brain/learnings", json={**DRAFT, "versions": []}).json()
    client.post(f"/api/brain/learnings/{note['id']}/review", json=APPROVE)
    source = next(s for s in client.get("/api/brain").json()["sources"] if s["web_id"] == note["id"])
    assert source["versions"] == [] and "not established" in source["caveat"]


def test_locked_users_cannot_read_submit_review_or_retrieve_shared_learning(client, monkeypatch):
    note = client.post("/api/brain/learnings", json=DRAFT).json()
    client.post(f"/api/brain/learnings/{note['id']}/review", json=APPROVE)
    monkeypatch.setenv("POCKET_FDE_ACCESS_CODE", "test-access-code")
    assert client.get("/api/brain").status_code == 401
    assert client.post("/api/brain/learnings", json=DRAFT).status_code == 401
    assert client.post(f"/api/brain/learnings/{note['id']}/review", json=APPROVE).status_code == 401
    incident = {"title": DRAFT["title"], "description": DRAFT["content"], "version": "v2"}
    anonymous = client.post("/api/context", json={"incident": incident}).json()
    assert all(not s["id"].startswith("WEB-NOTE:") for s in anonymous["sources"])
    assert "WEB-NOTE:" not in client.get("/api/status").text
    assert client.post("/api/access", json={"code": "test-access-code"}).status_code == 200
    assert client.get("/api/brain").status_code == 200
    private = client.post("/api/context", json={"incident": incident}).json()
    assert "WEB-NOTE:" + note["id"] in {s["id"] for s in private["sources"]}


def test_invalid_learning_and_review_paths_do_not_write_data(client):
    for patch in ({"status": "approved"}, {"versions": ["v4"]}, {"content": "too short"}, {"author": " "}):
        assert client.post("/api/brain/learnings", json={**DRAFT, **patch}).status_code == 422
    assert client.get("/api/brain").json()["learnings"] == []
    assert client.post("/api/brain/learnings/not-an-id/review", json=APPROVE).status_code == 404
    assert client.post("/api/brain/learnings/" + "a" * 32 + "/review", json=APPROVE).status_code == 404


def test_private_cloud_submission_and_decision_survive_instances(client, monkeypatch):
    from vercel.blob.errors import BlobNotFoundError
    objects = {}
    class Remote:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_objects(self, prefix):
            return [SimpleNamespace(pathname=key) for key in objects if key.startswith(prefix)]
        def put(self, key, content, **options):
            assert options["access"] == "private" and options["overwrite"] is False
            if key in objects: raise RuntimeError("exists")
            objects[key] = content
        def get(self, key, **options):
            assert options == {"access": "private", "use_cache": False}
            if key not in objects: raise BlobNotFoundError()
            return SimpleNamespace(status_code=200, content=objects[key])
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "controlled-token")
    monkeypatch.setattr(BrainStore, "_client", lambda self: Remote())
    note = BrainStore().submit(DRAFT)
    assert BrainStore().get_note(note["id"])["status"] == "pending"
    decision = {key: APPROVE[key] for key in ("status", "reviewer", "reason")}
    BrainStore().review(note["id"], decision)
    assert BrainStore().approved_items()[0].id == "WEB-NOTE:" + note["id"]
    with pytest.raises(ReviewConflict):
        BrainStore().review(note["id"], {**decision, "status": "rejected"})


def test_storage_outage_never_silently_drops_approved_knowledge(client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError, match="not configured"):
        BrainStore().list_notes()
    with pytest.raises(module.HTTPException) as error:
        module.refresh_knowledge()
    assert error.value.status_code == 503


def controlled_analysis(monkeypatch):
    answer = {"owning_team": "B", "confidence": "medium",
              "reasoning": "A rewrite hypothesis needs verification [CARD-001].",
              "questions": [{"text": "Does g.rewrite show an empty query?", "evidence": "g.rewrite"},
                            {"text": "Does the widget pass a session?", "evidence": ""},
                            {"text": "What is tune.rewrite.mode?", "evidence": "tune.rewrite.mode"}],
              "logs_to_check": ["g.rewrite"], "flags_to_check": ["tune.rewrite.mode"],
              "recommended_fix": "Check evidence before changing the tenant override [CARD-001].",
              "escalate": False}
    calls = []
    monkeypatch.setattr(module, "default_provider", lambda: Provider("groq", "test-model", "controlled-key"))
    def complete(*args, **kwargs):
        calls.append(1)
        return LLMResult(json.dumps(answer), 400, 150, .01, "test:controlled")
    monkeypatch.setattr(Provider, "complete", complete)
    return calls


def test_completed_analysis_automatically_queues_sanitized_provisional_learning(client, monkeypatch):
    calls = controlled_analysis(monkeypatch)
    before = module.refresh_knowledge().corpus_revision
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    data = response.json()
    assert data["learning"]["status"] == "pending" and data["learning"]["created"] is True
    assert len(calls) == 1 and data["result"]["cost"]["tokens"] == 550
    note = client.get("/api/brain").json()["learnings"][0]
    assert note["id"] == data["learning"]["id"] and note["origin"] == "analysis"
    assert note["source_case"] == "CASE-101" and note["versions"] == ["v2"]
    assert "PROVISIONAL" in note["content"] and "unverified" in note["content"]
    assert "CARD-001" in note["content"] and "g.rewrite" in note["content"]
    assert "demo@example.test" not in note["content"] and "not-a-real-secret-value" not in note["content"]
    assert "priya.n@" not in note["content"] and "Acme Logistics" not in note["content"]
    assert module.refresh_knowledge().corpus_revision == before
    saved = client.get('/api/history/' + data['saved_id']).json()
    assert saved["analysis"]["learning"]["id"] == note["id"]


def test_reanalysis_deduplicates_and_never_undoes_a_human_decision(client, monkeypatch):
    controlled_analysis(monkeypatch)
    first = client.post("/api/analyze", json={"case_id": "CASE-101"}).json()["learning"]
    second = client.post("/api/analyze", json={"case_id": "CASE-101"}).json()["learning"]
    assert first["id"] == second["id"] and second["created"] is False
    client.post(f"/api/brain/learnings/{first['id']}/review", json={**APPROVE, "status": "rejected"})
    third = client.post("/api/analyze", json={"case_id": "CASE-101"}).json()["learning"]
    assert third["id"] == first["id"] and third["status"] == "rejected"
    assert len(client.get("/api/brain").json()["learnings"]) == 1


def test_new_evidence_creates_a_new_provisional_draft(client, monkeypatch):
    controlled_analysis(monkeypatch)
    case = next(case for case in module.case_catalog() if case["id"] == "CASE-101")
    incident = {key: case[key] for key in ("id", "title", "description", "version", "customer_tier", "provided_evidence")}
    first = client.post("/api/analyze", json={"incident": incident}).json()["learning"]
    incident["provided_evidence"] = [*incident["provided_evidence"], "g.rewrite: query was empty"]
    second = client.post("/api/analyze", json={"incident": incident}).json()["learning"]
    assert first["id"] != second["id"] and second["status"] == "pending"


def test_failed_analysis_and_source_inspection_never_create_learning(client, monkeypatch):
    controlled_analysis(monkeypatch)
    assert client.post("/api/context", json={"case_id": "CASE-101"}).status_code == 200
    assert client.post("/api/analyze", json={"case_id": "CASE-573544"}).status_code == 422
    def fail(*args, **kwargs):
        raise LLMError("Controlled provider failure")
    monkeypatch.setattr(Provider, "complete", fail)
    assert client.post("/api/analyze", json={"case_id": "CASE-101"}).status_code == 502
    assert client.get("/api/brain").json()["learnings"] == []


def test_capture_failure_preserves_analysis_and_can_retry_without_a_model_call(client, monkeypatch):
    calls = controlled_analysis(monkeypatch)
    create = BrainStore._create
    def fail(*args, **kwargs):
        raise OSError("Controlled learning storage outage")
    monkeypatch.setattr(BrainStore, "_create", fail)
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    data = response.json()
    assert data["learning"]["status"] == "failed" and data["saved_id"]
    path = f"/api/history/{data['saved_id']}/learning"
    assert client.post(path).status_code == 503
    monkeypatch.setattr(BrainStore, "_create", create)
    retry = client.post(path)
    assert retry.status_code == 200 and retry.json()["status"] == "pending"
    assert len(calls) == 1
    assert client.post(path).json()["id"] == retry.json()["id"]
    with TestClient(module.app) as stranger:
        assert stranger.post(path).status_code == 404


def test_automatic_shared_summary_masks_restored_identifiers_and_omits_raw_logs(client, monkeypatch):
    controlled_analysis(monkeypatch)
    analysis = client.post("/api/analyze", json={"case_id": "CASE-101"}).json()
    case = {"id": "CUSTOM", "title": "Acme Logistics contact demo@example.test",
            "version": "v2", "customer_tier": "standard",
            "description": "Raw private description is not part of shared learning.",
            "provided_evidence": ["Raw private log line is not shared."]}
    analysis["result"]["reasoning"] += " Contact demo@example.test; api_key=not-a-real-secret-value; AIza1234567890123456789012345."
    note, _ = BrainStore().capture_analysis(case, analysis)
    shared = note["title"] + note["content"]
    for private in ("Acme Logistics", "demo@example.test", "not-a-real-secret-value", "AIza1234567890123456789012345", case["description"], case["provided_evidence"][0]):
        assert private not in shared
