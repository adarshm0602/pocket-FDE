"""Exercise real retrieval/triage with a controlled completion at the API boundary."""
import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pocketfd.llm import LLMError, LLMResult
from web import app as module
from web.provider import PROVIDERS, Provider
from web import provider as provider_module
from web import connect_gemini

ANSWER = {
    "owning_team": "B", "confidence": "high",
    "reasoning": "The v2 rewrite default loses the query without a session [CARD-001].",
    "questions": [{"text": "What does g.rewrite show?", "evidence": "g.rewrite"},
                  {"text": "Does the One-Way widget send a session, unlike chat UI?", "evidence": ""},
                  {"text": "What tenant override is set for tune.rewrite.mode?", "evidence": "tune.rewrite.mode"}],
    "logs_to_check": ["g.rewrite", "g.retrieval", "unknown.log"],
    "flags_to_check": ["tune.rewrite.mode"],
    "recommended_fix": "Use single_shot for the v2 One-Way tenant [CARD-001].",
    "handover": {"why_this_team": "Rewrite defaults are owned by B.", "suggested_next_action": "Check g.rewrite"},
    "escalate": False,
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("POCKET_FDE_DATA_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(module, "default_provider", lambda: Provider("groq", "test-model"))
    monkeypatch.setattr(module, "LOG_DIR", tmp_path)
    module.SESSIONS.clear()
    with TestClient(module.app) as client:
        yield client
    module.SESSIONS.clear()


def connect(client, monkeypatch, answer=ANSWER):
    def completion(self, prompt, system="", tier="frontier"):
        text = json.dumps({"ok": True}) if '"ok": true' in prompt else json.dumps(answer)
        return LLMResult(text, 400, 150, .1, "test:controlled")
    monkeypatch.setattr(Provider, "complete", completion)
    response = client.post("/api/settings", json={"provider": "groq", "model": "test-model", "api_key": "private-test-key"})
    assert response.status_code == 200
    return completion


def test_cases_exclude_hidden_answers_and_resolution_notes(client):
    response = client.get("/api/cases")
    assert response.status_code == 200
    assert len(response.json()["cases"]) == 13
    assert {"CASE-S45G7", "CASE-573544"} <= {c["id"] for c in response.json()["cases"]}
    assert "ground_truth" not in response.text
    assert "resolution_notes" not in response.text
    assert "root_cause" not in response.text
    assert "Reverted prepare()" not in response.text
    assert "Deployed missing file" not in response.text


def test_missing_version_remains_unknown_and_blocks_analysis(client, monkeypatch):
    case = next(c for c in client.get("/api/cases").json()["cases"] if c["id"] == "CASE-573544")
    assert case["version"] is None and case["status"] == "CLOSED"
    context = client.post("/api/context", json={"case_id": case["id"]})
    assert context.status_code == 200 and context.json()["case"]["version"] is None
    assert all(s["version_match"] is None for s in context.json()["sources"])
    response = client.post("/api/analyze", json={"case_id": case["id"]})
    assert response.status_code == 422 and "Confirm the platform version" in response.json()["detail"]


def test_new_alphanumeric_case_loads_validated_evidence_and_learning_sources(client):
    response = client.post("/api/context", json={"case_id": "CASE-S45G7"})
    assert response.status_code == 200
    data = response.json()
    assert data["case"]["version"] == "v2"
    assert "VALIDATED - NOT THE ISSUE" in " ".join(data["case"]["provided_evidence"])
    assert "NOTE:case_s45g7_diagnostics" in {s["id"] for s in data["sources"]}
    note = next(s for s in data["sources"] if s["id"] == "NOTE:case_s45g7_diagnostics")
    assert note["source_path"].endswith("case_s45g7_diagnostics.md")
    assert "applicability" in note["caveat"]


def test_markdown_file_mentions_are_not_presented_as_source_citations():
    from pocketfd.redact import Redactor
    from pocketfd.triage import build_prompt, case_text
    case = next(c for c in module.case_catalog() if c["id"] == "CASE-S45G7")
    hits = module.INDEX.search(case_text(case), "v2", k=8, include_pending=False)
    prompt = build_prompt(case, hits, None, Redactor())
    assert "[NOTE:case_s45g7_diagnostics]" in prompt
    assert "[team_e_finetune/service.py]" not in prompt
    assert "team_e_finetune/service.py" in prompt
    assert "[[reference_codebases]]" not in prompt
    assert "cite this NOTE source ID" in prompt


def test_reviewed_corpus_changes_invalidate_both_indexes(client, monkeypatch, tmp_path):
    from pocketfd.knowledge import Item
    original = module.load_all(include_pending=False)
    additions = [Item("NOTE:reviewed-change", "note", "A human reviewed discovery", versions=[])]
    monkeypatch.setattr(module, "load_all", lambda **kwargs: original + additions)
    monkeypatch.setattr(module, "INDEX", module.INDEX)
    monkeypatch.setattr(module, "HYBRID_INDEX", object())
    old = module.INDEX.corpus_revision
    updated = module.refresh_knowledge()
    assert updated.corpus_revision != old and module.HYBRID_INDEX is None
    assert "NOTE:reviewed-change" in {i.id for i in updated.items}


def test_context_works_without_key_uses_existing_index(client):
    response = client.post("/api/context", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    assert "CARD-001" in [s["id"] for s in response.json()["sources"]]
    assert response.json()["retrieval"] == "BM25 + TF-IDF"
    assert all(s["status"] == "approved" for s in response.json()["sources"])


def test_missing_key_is_actionable(client):
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 503
    assert "Model settings" in response.json()["detail"]


def test_complete_flow_uses_real_triage_redaction_and_measured_tokens(client, monkeypatch, tmp_path):
    connect(client, monkeypatch)
    prompts = []
    def completion(self, prompt, system="", tier="frontier"):
        prompts.append(prompt)
        return LLMResult(json.dumps(ANSWER), 400, 150, .1, "test:controlled")
    monkeypatch.setattr(Provider, "complete", completion)
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    output = response.json()
    assert output["result"]["owning_team"] == "B"
    assert output["result"]["cost"]["tokens"] == 550
    assert output["result"]["owner_contact"] == "tune-config-oncall"
    assert "CARD-001" in [s["id"] for s in output["sources"]]
    assert "unknown.log" not in [s["stream"] for s in output["result"]["logs_to_check"]]
    assert "ground_truth" not in prompts[0] and "false_lead" not in prompts[0]
    assert "acmelogistics.example" not in prompts[0] and "Acme" not in prompts[0]
    assert "private-test-key" not in response.text


def test_custom_issue_is_used_instead_of_selected_case(client, monkeypatch):
    connect(client, monkeypatch)
    observed = []
    def completion(self, prompt, system="", tier="frontier"):
        observed.append(prompt)
        return LLMResult(json.dumps(ANSWER), 400, 150, .1, "test:controlled")
    monkeypatch.setattr(Provider, "complete", completion)
    response = client.post("/api/analyze", json={"incident": {"id": "MY-CASE", "title": "Edited issue title", "description": "One-Way rewrite loses query on v2", "version": "v2"}})
    assert response.status_code == 200
    assert response.json()["result"]["case_id"] == "MY-CASE"
    assert "Edited issue title" in observed[0]


def test_bad_case_and_ambiguous_payload_rejected(client):
    assert client.post("/api/context", json={"case_id": "../../env"}).status_code == 422
    assert client.post("/api/context", json={"case_id": "CASE-999"}).status_code == 404
    assert client.post("/api/context", json={}).status_code == 422
    assert client.post("/api/context", json={"case_id": "CASE-101", "incident": {"title": "test", "description": "test incident description", "version": "v2"}}).status_code == 422
    assert client.post("/api/context", json={"case_id": "CASE-101", "retrieval": "unknown"}).status_code == 422


def test_hybrid_unavailable_is_explicit_and_keeps_surya_working(client, monkeypatch):
    monkeypatch.setattr(module, "hybrid_available", lambda: False)
    assert client.post("/api/context", json={"case_id": "CASE-101", "retrieval": "hybrid"}).status_code == 503
    assert client.post("/api/context", json={"case_id": "CASE-101", "retrieval": "surya"}).status_code == 200
    modes = client.get("/api/status").json()["retrieval_modes"]
    assert [m["ready"] for m in modes] == [True, False]


def test_hybrid_selection_uses_its_context_in_live_pipeline(client, monkeypatch):
    from pocketfd.retrieval import Hit
    class AlternativeIndex:
        sem_name = "minilm"
        def search(self, *args, **kwargs):
            item = next(i for i in module.INDEX.items if i.id == "CARD-014")
            return [Hit(item, .04, .8, True)]
    monkeypatch.setattr(module, "hybrid_available", lambda: True)
    monkeypatch.setattr(module, "HYBRID_INDEX", AlternativeIndex())
    connect(client, monkeypatch)
    observed = []
    def completion(self, prompt, system="", tier="frontier"):
        observed.append(prompt)
        return LLMResult(json.dumps({**ANSWER, "owning_team": "E", "reasoning": "Adapter migration can cause generic answers [CARD-014].",
                                    "recommended_fix": "Verify the adapter lookup [CARD-014]."}), 400, 150, .1, "test")
    monkeypatch.setattr(Provider, "complete", completion)
    context = client.post("/api/context", json={"case_id": "CASE-106", "retrieval": "hybrid"}).json()
    assert [s["id"] for s in context["sources"]] == ["CARD-014"]
    output = client.post("/api/analyze", json={"case_id": "CASE-106", "retrieval": "hybrid"}).json()
    assert output["retrieval_mode"] == "hybrid" and output["result"]["retrieval"]["sem_name"] == "minilm"
    assert [s["id"] for s in output["sources"]] == ["CARD-014"]
    assert "[CARD-014]" in observed[0] and "adapter" in observed[0].lower() and "[CARD-001]" not in observed[0]


def test_hybrid_model_failure_never_silently_uses_legacy_index(client, monkeypatch):
    monkeypatch.setattr(module, "hybrid_available", lambda: True)
    monkeypatch.setattr(module, "HYBRID_INDEX", None)
    def broken(*args, **kwargs):
        raise ImportError("Local model unavailable")
    monkeypatch.setattr(module, "HybridIndex", broken)
    response = client.post("/api/context", json={"case_id": "CASE-101", "retrieval": "hybrid"})
    assert response.status_code == 503
    assert "model could not load" in response.json()["detail"]


def test_credentials_are_browser_session_scoped_and_disconnectable(client, monkeypatch):
    connect(client, monkeypatch)
    assert client.get("/api/status").json()["model"]["ready"]
    with TestClient(module.app) as stranger:
        assert not stranger.get("/api/status").json()["model"]["ready"]
    assert "private-test-key" not in client.get("/api/status").text
    cookie = client.cookies.get("pocketfde_session")
    assert cookie and module.SESSIONS[cookie][0].key == "private-test-key"
    assert client.delete("/api/settings").status_code == 200
    assert not client.get("/api/status").json()["model"]["ready"]


def test_settings_failure_does_not_save_key(client, monkeypatch):
    def fail(*args, **kwargs):
        raise LLMError("The provider rejected this API key.")
    monkeypatch.setattr(Provider, "complete", fail)
    response = client.post("/api/settings", json={"provider": "gemini", "model": "gemini-3.5-flash", "api_key": "bad-key"})
    assert response.status_code == 502
    assert not module.SESSIONS
    assert "bad-key" not in response.text


def test_malformed_model_reply_returns_recoverable_error(client, monkeypatch):
    connect(client, monkeypatch)
    monkeypatch.setattr(Provider, "complete", lambda *a, **k: LLMResult('{"confidence": "100%", "questions": "oops"}', 20, 20, .1, "test"))
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 502
    assert "incomplete analysis" in response.json()["detail"]


@pytest.mark.parametrize("first_reply", ['{"confidence": "100%", "questions": "oops"}', 'not JSON'])
def test_invalid_response_uses_one_accounted_repair(client, monkeypatch, first_reply):
    connect(client, monkeypatch)
    calls = []
    def completion(self, prompt, system="", tier="frontier"):
        calls.append(prompt)
        return LLMResult(first_reply if len(calls) == 1 else json.dumps(ANSWER), 400, 150, .1, "test:controlled")
    monkeypatch.setattr(Provider, "complete", completion)
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["model_answer_valid"] and result["diagnostics_complete"]
    assert len(calls) == 2 and "field types" in calls[-1]
    assert result["cost"]["tokens"] == 1100
    assert [c["purpose"] for c in result["cost"]["calls"]] == ["triage", "repair"]


def test_repeated_invalid_responses_cannot_exceed_one_repair(client, monkeypatch):
    connect(client, monkeypatch)
    calls = []
    def completion(self, prompt, system="", tier="frontier"):
        calls.append(prompt)
        return LLMResult('{"confidence": "bad"}', 40, 15, .1, "test:controlled")
    monkeypatch.setattr(Provider, "complete", completion)
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 502 and len(calls) == 2
    assert "one repair attempt" in response.json()["detail"]


def test_cross_origin_setting_change_rejected(client):
    response = client.post("/api/settings", headers={"Origin": "https://unrelated.example"}, json={"provider": "groq", "model": "test", "api_key": "key"})
    assert response.status_code == 403


def test_invalid_credential_input_is_not_echoed(client):
    secret = "private-api-key-" * 100
    response = client.post("/api/settings", json={"provider": "groq", "model": "test", "api_key": secret})
    assert response.status_code == 422
    assert "private-api-key" not in response.text


def test_local_terminal_settings_reload_without_restart(monkeypatch, tmp_path):
    local = tmp_path / ".env"
    monkeypatch.setattr(provider_module, "LOCAL_ENV", local)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "old-model")
    local.write_text("LLM_PROVIDER=gemini\nLLM_MODEL=first\nGEMINI_API_KEY=private-test-key\n")
    assert provider_module.default_provider().name == "gemini"
    local.write_text("LLM_PROVIDER=gemini\nLLM_MODEL=updated\nGEMINI_API_KEY=private-test-key\n")
    assert provider_module.default_provider().model == "updated"


def test_terminal_saves_private_file_without_printing_key(monkeypatch, tmp_path, capsys):
    local = tmp_path / ".env"
    monkeypatch.setattr(connect_gemini, "LOCAL_ENV", local)
    connect_gemini.save("private-test-key", "gemini-2.5-flash")
    assert local.stat().st_mode & 0o777 == 0o600
    assert "private-test-key" not in capsys.readouterr().out


def test_terminal_discovers_available_model_before_completion(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, json={"models": [
        {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}]}))
    monkeypatch.setattr(Provider, "complete", lambda *a, **k: LLMResult('{"ok": true}', 10, 5, .1, "test"))
    assert connect_gemini.verify("private-test-key") == "gemini-2.5-flash"


def test_persistently_invented_names_require_human_review(client, monkeypatch):
    connect(client, monkeypatch, {**ANSWER, "reasoning": "Use zz.fake.flag to fix this."})
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["escalate"] and result["confidence"] == "low"
    assert result["recommended_fix"] == "No verified fix available; collect more evidence."


def test_missing_questions_get_one_budgeted_repair(client, monkeypatch):
    connect(client, monkeypatch)
    prompts = []
    def completion(self, prompt, system="", tier="frontier"):
        prompts.append(prompt)
        answer = {**ANSWER, "questions": []} if len(prompts) == 1 else ANSWER
        return LLMResult(json.dumps(answer), 400, 150, .1, "test")
    monkeypatch.setattr(Provider, "complete", completion)
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert len(prompts) == 2 and "DIAGNOSTIC QUESTION REQUIREMENT" in prompts[0]
    assert len(result["questions"]) == 3 and result["diagnostics_complete"]
    assert result["cost"]["tokens"] == 1100
    assert result["cost"]["calls"][-1]["purpose"] == "repair"


def test_persistently_missing_questions_are_explicitly_incomplete(client, monkeypatch):
    connect(client, monkeypatch, {**ANSWER, "questions": []})
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert not result["diagnostics_complete"]
    assert result["escalate"] and result["confidence"] == "low"
    assert "diagnostic questions" in result["escalation_reason"]
    assert len(result["cost"]["calls"]) == 2


def test_failed_question_repair_retains_first_answer(client, monkeypatch):
    connect(client, monkeypatch)
    calls = []
    def completion(self, *args, **kwargs):
        calls.append(1)
        if len(calls) > 1:
            raise LLMError("Provider temporarily unavailable")
        return LLMResult(json.dumps({**ANSWER, "questions": []}), 400, 150, .1, "test")
    monkeypatch.setattr(Provider, "complete", completion)
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["owning_team"] == "B" and result["escalate"]
    assert not result["diagnostics_complete"]
    assert result["cost"]["tokens"] == 550


def test_duplicate_and_wrong_version_questions_do_not_meet_requirement(client, monkeypatch):
    connect(client, monkeypatch, {**ANSWER, "questions": [
        ANSWER["questions"][0], ANSWER["questions"][0],
        {"text": "What is rag.cache.enabled?", "evidence": "rag.cache.enabled"}]})
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert len(result["questions"]) == 1 and not result["diagnostics_complete"]


def test_unsupported_citations_require_review(client, monkeypatch):
    connect(client, monkeypatch, {**ANSWER, "reasoning": "The root cause is documented [CARD-999]."})
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["escalate"] and result["confidence"] == "low"
    assert "unsupported citation" in " ".join(result["grounding_issues"])
    assert "No verified fix" in result["recommended_fix"]


def test_supplied_case_is_a_valid_citation_source(client, monkeypatch):
    connect(client, monkeypatch, {**ANSWER, "reasoning": "Widget and chat differ [CASE:CASE-101]. Rewrite behavior matches [CARD-001]."})
    response = client.post("/api/analyze", json={"case_id": "CASE-101"})
    assert response.status_code == 200
    assert not response.json()["result"]["escalate"]


def test_redacted_customer_name_is_not_mistaken_for_citation(client, monkeypatch):
    connect(client, monkeypatch)
    def completion(self, prompt, system="", tier="frontier"):
        import re
        placeholder = re.search(r"\[CUSTOMER_\d+\]", prompt).group()
        return LLMResult(json.dumps({**ANSWER, "reasoning": f"The issue for {placeholder} matches the rewrite default [CARD-001]."}), 400, 150, .1, "test")
    monkeypatch.setattr(Provider, "complete", completion)
    result = client.post("/api/analyze", json={"case_id": "CASE-101"}).json()["result"]
    assert not result["escalate"] and not result["grounding_issues"]
    assert "CUSTOMER_" not in result["reasoning"]
    assert result["cost"]["tokens"] == 550


def test_privacy_placeholders_cannot_replace_source_citations():
    from pocketfd.triage import citation_problems
    assert citation_problems({"reasoning": "[CUSTOMER_1] has an issue."}, {"CARD-001"}, {"CUSTOMER_1"}) == ["reasoning has no source citation"]
    assert "CUSTOMER_999" in citation_problems({"reasoning": "[CUSTOMER_999] [CARD-001]"}, {"CARD-001"}, {"CUSTOMER_1"})[0]


@pytest.mark.parametrize("provider", ["groq", "xai"])
def test_provider_adapter_request_shape_and_usage(monkeypatch, provider):
    observed = {}
    def post(url, **kwargs):
        observed.update(url=url, **kwargs)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 21, "completion_tokens": 8}})
    monkeypatch.setattr(httpx, "post", post)
    output = Provider(provider, PROVIDERS[provider]["model"], "secret").complete("query", "system")
    assert observed["url"].endswith("/chat/completions")
    assert observed["json"]["response_format"] == {"type": "json_object"}
    assert observed["json"]["messages"][1]["content"] == "query"
    assert "secret" not in json.dumps(observed["json"])
    assert output.input_tokens == 21 and output.output_tokens == 8


def test_gemini_native_request_and_reasoning_token_accounting(monkeypatch):
    observed = {}
    def post(url, **kwargs):
        observed.update(url=url, **kwargs)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "internal reasoning", "thought": True}, {"text": '{"ok": true}'}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 21, "candidatesTokenCount": 8, "thoughtsTokenCount": 4, "totalTokenCount": 33}})
    monkeypatch.setattr(httpx, "post", post)
    output = Provider("gemini", "gemini-3.5-flash", "secret").complete("query", "system")
    assert observed["url"].endswith("gemini-3.5-flash:generateContent")
    assert observed["headers"]["x-goog-api-key"] == "secret"
    assert "secret" not in observed["url"] and "secret" not in json.dumps(observed["json"])
    assert observed["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert observed["json"]["contents"][0]["parts"][0]["text"] == "query"
    assert output.text == '{"ok": true}'
    assert output.input_tokens == 21 and output.output_tokens == 12


@pytest.mark.parametrize("code", [401, 403, 404, 429, 500])
def test_provider_errors_do_not_echo_secrets(monkeypatch, code):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(code, json={"error": "secret-key private request content"}))
    with pytest.raises(LLMError) as exc:
        Provider("groq", "test", "secret-key").complete("private request content")
    assert "secret-key" not in str(exc.value) and "private request content" not in str(exc.value)


def test_transient_provider_overload_is_retried(monkeypatch):
    statuses = iter([503, 503, 200])
    def post(url, **kwargs):
        status = next(statuses)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}, "finishReason": "STOP"}],
                                         "usageMetadata": {"promptTokenCount": 5, "totalTokenCount": 9}})
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(provider_module.time, "sleep", lambda s: None)
    assert Provider("gemini", "gemini-2.5-flash", "secret").complete("q", "s").text == '{"ok": true}'


def test_persistent_overload_returns_safe_message(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, **k: httpx.Response(503, json={"error": {"message": "secret echoed"}}))
    monkeypatch.setattr(provider_module.time, "sleep", lambda s: None)
    with pytest.raises(LLMError, match="temporarily overloaded") as exc:
        Provider("gemini", "gemini-2.5-flash", "secret").complete("q", "s")
    assert "secret" not in str(exc.value)


def test_terminal_falls_back_when_preferred_model_is_overloaded(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, json={"models": [
        {"name": "models/" + m, "supportedGenerationMethods": ["generateContent"]}
        for m in (PROVIDERS["gemini"]["model"], "gemini-2.5-flash")]}))
    def complete(self, *a, **k):
        if self.model == PROVIDERS["gemini"]["model"]:
            raise LLMError("The selected model is temporarily overloaded at the provider.")
        return LLMResult('{"ok": true}', 10, 5, .1, "test")
    monkeypatch.setattr(Provider, "complete", complete)
    assert connect_gemini.verify("private-test-key") == "gemini-2.5-flash"
