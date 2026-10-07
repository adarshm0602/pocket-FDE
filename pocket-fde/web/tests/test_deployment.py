"""Cross-process persistence and hosted authorization, without live provider calls."""
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from web import app as module
from web import security
from web.provider import Provider
from web.storage import WorkspaceStore, DemoLimit
from pocketfd.knowledge import customer_documents, load_all
from pocketfd.llm import LLMResult


def test_analysis_persists_across_store_instances_and_is_isolated(monkeypatch, tmp_path):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("POCKET_FDE_DATA_DIR", str(tmp_path))
    identity = "a" * 32
    record = WorkspaceStore().save(identity, {"title": "Example"}, {"retrieval_mode": "hybrid"})
    assert WorkspaceStore().get(identity, record)["incident"]["title"] == "Example"
    assert WorkspaceStore().get("b" * 32, record) is None
    assert WorkspaceStore().recent(identity)[0]["id"] == record
    assert WorkspaceStore().recent("b" * 32) == []
    with pytest.raises(ValueError):
        WorkspaceStore().get(identity, "../../.env")


def test_cloud_save_fails_closed_without_private_store(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        WorkspaceStore().save("a" * 32, {"title": "example"}, {"retrieval_mode": "surya"})


def test_local_workspace_cookie_survives_new_cipher_instances(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("POCKET_FDE_SESSION_KEY", raising=False)
    monkeypatch.setenv("POCKET_FDE_DATA_DIR", str(tmp_path))
    token = security.seal("workspace", "a" * 32)
    assert security.unseal(token, "workspace", security.WORKSPACE_TTL) == "a" * 32
    corrupted = token[:30] + ("A" if token[30] != "A" else "B") + token[31:]
    assert security.unseal(corrupted, "workspace", security.WORKSPACE_TTL) is None
    assert security.unseal(token, "provider", security.WORKSPACE_TTL) is None


def test_hosted_model_is_locked_and_sessions_survive_process_restart(monkeypatch):
    from web.brain import BrainStore
    monkeypatch.setattr(BrainStore, "approved_items", lambda self: [])
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("POCKET_FDE_SESSION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("POCKET_FDE_ACCESS_CODE", "demo-private-code")
    monkeypatch.setattr(module, "default_provider", lambda: Provider("gemini", "demo-model", "owner-private-key"))
    monkeypatch.setattr(Provider, "complete", lambda *args: LLMResult('{"ok": true}', 10, 5, .1, "mock"))
    monkeypatch.setattr(module, "reserve_model_call", lambda *args: None)
    with TestClient(module.app, base_url="https://testserver") as client:
        assert not client.get("/api/status").json()["model"]["ready"]
        assert client.post("/api/analyze", json={"case_id": "CASE-101"}).status_code == 401
        assert client.get("/api/history").status_code == 401
        assert client.post("/api/context", json={"case_id": "CASE-101"}).status_code == 200
        assert client.post("/api/access", json={"code": "wrong"}).status_code == 401
        assert client.post("/api/access", json={"code": "demo-private-code"}).status_code == 200
        assert client.get("/api/status").json()["model"]["ready"]
        assert client.post("/api/settings", json={"provider": "groq", "model": "demo", "api_key": "browser-private-key"}).status_code == 200
        cookie = client.cookies.get("pocketfde_session")
        assert "browser-private-key" not in cookie
        module.SESSIONS.clear()
        assert client.get("/api/status").json()["model"]["provider"] == "groq"
        assert "private-key" not in client.get("/api/status").text
        response = client.post("/api/settings", json={"provider": "claude_cli", "model": "sonnet"})
        assert response.status_code == 422
        with TestClient(module.app, base_url="https://testserver") as stranger:
            assert not stranger.get("/api/status").json()["model"]["ready"]
        assert client.delete("/api/settings").status_code == 200
        assert client.get("/api/status").json()["model"]["provider"] == "gemini"


def test_customer_guide_sources_are_present_and_version_scoped():
    documents = customer_documents()
    assert documents and all(d.id.startswith("DOC:") for d in documents)
    assert all(d.meta["source_path"].startswith("docs/customer/") for d in documents)
    one_way = next(d for d in documents if "one-way-query" in d.id)
    caching = next(d for d in documents if "caching" in d.id)
    assert one_way.versions == ["v2", "v3"] and caching.versions == ["v3"]
    assert all("ground_truth" not in d.text for d in documents)
    assert len({d.id for d in load_all(False)}) == len(load_all(False))


def test_hosted_usage_limits_survive_new_store_instances(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "test-token")
    objects = {}
    class Remote:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def list_objects(self, prefix, limit):
            return SimpleNamespace(blobs=[p for p in objects if p.startswith(prefix)][:limit])
        def put(self, path, content, **options):
            assert options == {"access": "private", "overwrite": False}
            if path in objects:
                raise RuntimeError("create-only conflict")
            objects[path] = content
    monkeypatch.setattr(WorkspaceStore, "_client", lambda self: Remote())
    WorkspaceStore().reserve_model_call("a" * 32)
    with pytest.raises(DemoLimit, match="wait 15 seconds"):
        WorkspaceStore().reserve_model_call("a" * 32)
    for number in range(49):
        WorkspaceStore().reserve_model_call(f"{number:032x}")
    with pytest.raises(DemoLimit, match="daily model limit"):
        WorkspaceStore().reserve_model_call("b" * 32)


def test_configured_gemini_fallback_uses_actual_model_and_measured_tokens(monkeypatch):
    urls = []
    def post(url, **kwargs):
        urls.append(url)
        if 'primary' in url:
            return httpx.Response(429, json={"error": {"message": "private body must not leak"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok":true}'}]}}],
                                         "usageMetadata": {"promptTokenCount": 10, "totalTokenCount": 15}})
    monkeypatch.setattr(httpx, "post", post)
    result = Provider("gemini", "primary", "private-key", "fallback").complete('Return JSON')
    assert result.provider == "gemini:fallback" and result.input_tokens + result.output_tokens == 15
    assert len(urls) == 2 and 'fallback' in urls[-1]
    # A visitor-selected model has no fallback unless explicitly configured.
    with pytest.raises(Exception, match="quota"):
        Provider("gemini", "primary", "private-key").complete('Return JSON')


def test_fallback_does_not_hide_invalid_credentials(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        return httpx.Response(401, json={"error": {"message": "private key echo"}})
    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(Exception, match="rejected"):
        Provider("gemini", "primary", "private-key", "fallback").complete('Return JSON')
    assert len(calls) == 1
