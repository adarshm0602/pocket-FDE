from repos.flow import run
from repos.sim import Scenario
from pocketfd.known import invented_names, flag_exists


def test_oneway_v2_no_session_gives_empty_answer_and_v3_default_fixes_it():
    assert run(Scenario("v2", "t-acme", "oneway", False)).symptom() == "empty or odd answer"
    assert run(Scenario("v3", "t-acme", "oneway", False)).symptom() == "healthy answer"


def test_timeout_mismatch_gateway_success_ui_error():
    r = run(Scenario("v1", "t-stark", provider_latency_ms=11000))
    assert r.error_code == "UI_TIMEOUT"
    assert any("finish_reason=stop" in e["line"] for e in r.visible_logs())


def test_flag_absent_in_version_is_ignored():
    assert not flag_exists("llm.failover.enabled", "v2")
    r = run(Scenario("v2", "t-acme", provider_latency_ms=11000, overrides={"llm.failover.enabled": True}))
    assert r.error_code == "UI_TIMEOUT"


def test_citations_required_only_in_v3():
    assert run(Scenario("v3", "t-hooli")).error_code == "VAL_REJECT_042"
    assert run(Scenario("v2", "t-hooli")).status == "ok"


def test_off_in_prod_logs_hidden_until_enabled():
    sc = lambda **k: Scenario("v2", "t-umbrella", "oneway", False, **k)
    assert not any(e["stream"] == "u.verbose" for e in run(sc()).visible_logs())
    assert any(e["stream"] == "u.verbose" for e in run(sc(obs_enabled=("obs.oneway_u.verbose_log",))).visible_logs())


def test_hallucination_validator():
    assert invented_names("check tune.rewrite.mode and g.rewrite") == set()
    assert invented_names("set llm.magic.flag now") == {"llm.magic.flag"}
