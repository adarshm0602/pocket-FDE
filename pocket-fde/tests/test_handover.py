from pocketfd.handover import Handover, accept_or_reject


def _h(to, why, **kw):
    base = dict(case_id="C", from_team="support", to_team=to, why_this_team=why, checked_and_ruled_out="gateway healthy",
                trace_ids=["tr-1"], version_and_config="v2", question_for_receiver="confirm?", suggested_next_action="check")
    base.update(kw)
    return Handover(**base)


def test_accepts_when_evidence_points_at_receiver():
    d = accept_or_reject(_h("B", "g.rewrite shows had_session=false and tune.rewrite.mode=history_aware"))
    assert d.accepted


def test_rejects_with_specific_reason_and_alternative():
    h = _h("Q", "u.request failed; tune.rewrite.mode=history_aware is the cause")
    d = accept_or_reject(h)
    assert not d.accepted and d.alternative_team == "B"
    assert "tune-config-oncall" in d.reason
    assert h.bounces == 1


def test_platform_flag_routes_to_platform():
    d = accept_or_reject(_h("Q", "q.invocation success but platform.http.timeout_ms=8000 is below latency"))
    assert not d.accepted and d.alternative_team == "PLATFORM"


def test_rejects_insufficient_handover():
    d = accept_or_reject(_h("B", "tune.rewrite.mode", trace_ids=[], question_for_receiver=""))
    assert not d.accepted and "missing" in d.reason


def test_rejects_when_no_known_evidence():
    assert not accept_or_reject(_h("B", "it feels like your area")).accepted
