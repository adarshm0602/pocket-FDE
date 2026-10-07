import json

import pytest

from pocketfd import llm
from pocketfd.knowledge import Item
from pocketfd.retrieval import Index
from pocketfd.router import Budget, BudgetExceeded, Router
from pocketfd.triage import triage

CASE = {"id": "CASE-X", "title": "t", "version": "v2", "customer_tier": "standard", "description": "Acme Logistics widget odd, ops@acme.example"}


def test_step_budget_raises():
    r = Router(budget=Budget(max_steps=2))
    llm.set_mock_handler(lambda p, s: "{}")
    r.call("a", "x", external=False); r.call("b", "x", external=False)
    with pytest.raises(BudgetExceeded):
        r.call("c", "x", external=False)


def test_token_budget_raises():
    r = Router(budget=Budget(max_tokens=5))
    llm.set_mock_handler(lambda p, s: "y" * 400)
    with pytest.raises(BudgetExceeded):
        r.call("a", "x" * 400, external=False)


def test_triage_escalates_with_handover_when_budget_hit(tmp_path):
    llm.set_mock_handler(lambda p, s: json.dumps({"owning_team": "B", "confidence": "high"}))
    ix = Index([Item("CARD-1", "card", "widget odd answers rewrite")])
    r = Router(budget=Budget(max_steps=1), outbound_log=tmp_path / "o.jsonl")  # retrieve uses the only step
    out = triage(CASE, ix, r)
    assert out["escalate"] and "budget" in out["escalation_reason"]


def test_outbound_prompt_is_redacted(tmp_path):
    seen = {}
    def h(p, s):
        seen["p"] = p
        return json.dumps({"owning_team": "B", "confidence": "medium", "reasoning": "x", "handover": {}})
    llm.set_mock_handler(h)
    ix = Index([Item("CARD-1", "card", "widget odd answers rewrite")])
    triage(CASE, ix, Router(outbound_log=tmp_path / "o.jsonl"))
    assert "Acme" not in seen["p"] and "acme.example" not in seen["p"]
    assert "Acme" not in (tmp_path / "o.jsonl").read_text()


def test_unredacted_external_prompt_is_refused(tmp_path):
    llm.set_mock_handler(lambda p, s: "{}")
    r = Router(outbound_log=tmp_path / "o.jsonl")
    with pytest.raises(RuntimeError):
        r.call("x", "mail priya@acme.example", external=True)


def test_question_with_extra_words_around_known_stream_is_kept(tmp_path):
    llm.set_mock_handler(lambda p, s: json.dumps({"owning_team": "PLATFORM", "confidence": "high", "reasoning": "x", "handover": {},
        "questions": [{"text": "gateway outcome?", "evidence": "q.invocation latency_ms"}, {"text": "bogus", "evidence": "zz.fake.stream"}]}))
    ix = Index([Item("CARD-1", "card", "widget odd answers rewrite")])
    out = triage(CASE, ix, Router(outbound_log=tmp_path / "o.jsonl"))
    assert [q["text"] for q in out["questions"]] == ["gateway outcome?"]


def test_budget_stop_during_repair_keeps_first_answer_and_escalates(tmp_path):
    llm.set_mock_handler(lambda p, s: json.dumps({"owning_team": "B", "confidence": "high", "reasoning": "uses zz.fake.flag", "handover": {}}))
    ix = Index([Item("CARD-1", "card", "widget odd answers rewrite")])
    r = Router(budget=Budget(max_steps=2), outbound_log=tmp_path / "o.jsonl")   # retrieve + triage; no step left for repair
    out = triage(CASE, ix, r)
    assert out["owning_team"] == "B" and out["escalate"] and "repair" in out["escalation_reason"]
    assert out["invented_names"] == ["zz.fake.flag"]
