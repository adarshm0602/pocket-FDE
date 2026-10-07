"""Builds cases/history, cases/gate_answers, cases/heldout and world/sample_logs from the data below.
Every case is backed by a Scenario run through repos/flow.py, so root causes and evidence are real.
Run: python cases/build_cases.py"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from repos.flow import run  # noqa: E402
from repos.sim import Scenario  # noqa: E402

UI_STREAMS = {"r.request", "r.ui_error", "u.request"}

# ---------------------------------------------------------------- HISTORY (14 resolved)
# keys: id,title,tenant,tier,version,reported_by,description,teams,bounces,notes,quality,scenario, answers(for gate)
H = []
def hist(**k): H.append(k)

hist(id="CASE-001", title="One-Way widget gives empty/odd answers, chat UI fine", tenant="t-umbrella", version="v2", reported_by="support-engineer",
     description="Umbrella Media says the embedded One-Way widget returns 'I don't have enough information' for questions that the chat UI answers fine. Same tenant, same question. Contact: ops@umbrellamedia.example.",
     teams=["U", "R", "B"], bounces=2, notes="config issue fixed", quality="vague",
     scenario=Scenario("v2", "t-umbrella", "oneway", False),
     answers=dict(symptom="One-Way UI returns empty/odd answers while Interactive UI works", owning_team="B", affected_versions=["v2"],
        root_cause="v2 default tune.rewrite.mode=history_aware. One-Way UI sends no session_id, so the rewrite step has no history and produces an empty query; retrieval returns 0 chunks.",
        config_involved=["tune.rewrite.mode"], evidence_checked=["g.rewrite log: had_session=false rewrite_mode=history_aware", "g.retrieval log: n_chunks=0"],
        ruled_out=["One-Way UI rendering bug", "LLM gateway", "validation"], fix="Set tenant override tune.rewrite.mode=single_shot. Fixed by default in v3.",
        detection_tip="Compare Interactive vs One-Way for the same tenant; check g.rewrite had_session=false and g.retrieval n_chunks=0."))
hist(id="CASE-002", title="One-Way requests fail with generic error under load", tenant="t-wonka", version="v2", reported_by="support-engineer",
     description="Wonka Labs: One-Way UI shows ERR_UPSTREAM on questions that take a long time. Chat UI users report 'timed out'. Started this week, customer IP range 203.0.113.0/24.",
     teams=["U", "Q", "PLATFORM"], bounces=2, quality="adequate",
     notes="Gateway logs showed provider latency around 9.5s and success, but the UI hop gives up at 8s (platform.http.timeout_ms). Raised platform timeout for the tenant with platform on-call. LLM gateway was healthy.",
     scenario=Scenario("v2", "t-wonka", "oneway", False, provider_latency_ms=9500, overrides={"tune.rewrite.mode": "single_shot"}),
     answers=dict(symptom="Generic error / timeout on slow answers", owning_team="PLATFORM", affected_versions=["v1", "v2", "v3"],
        root_cause="Provider latency (9.5s) is below llm.timeout_ms (20s) but above platform.http.timeout_ms (8s), so the UI hop times out while the gateway logs success.",
        config_involved=["platform.http.timeout_ms", "llm.timeout_ms"], evidence_checked=["q.invocation: latency_ms=9500 finish_reason=stop", "r.ui_error / u.request status=error"],
        ruled_out=["LLM gateway fault", "validation"], fix="Raise platform.http.timeout_ms for the tenant above observed provider latency (platform on-call owns it).",
        detection_tip="If q.invocation shows success but the UI shows an error, compare latency_ms with platform.http.timeout_ms."))
hist(id="CASE-003", title="Chat answers time out for bank customer", tenant="t-globex", version="v3", reported_by="support-engineer",
     description="Globex Bank: Interactive UI times out roughly every other question, 'please try again' message. Retried by users, same result.",
     teams=["R", "Q", "PLATFORM"], bounces=2, quality="good",
     notes="Q logs show provider-a latency 15s, finish_reason=stop, under llm.timeout_ms=25000. UI hop budget platform.http.timeout_ms=12000 on v3 is lower, so both attempts time out. Failover does not trigger because the LLM never timed out. Fix: raised platform.http.timeout_ms for tenant to 20000 via platform on-call; asked Q to investigate provider latency separately.",
     scenario=Scenario("v3", "t-globex", provider_latency_ms=15000),
     answers=dict(symptom="Interactive UI timeouts", owning_team="PLATFORM", affected_versions=["v1", "v2", "v3"],
        root_cause="Provider latency 15s is under llm.timeout_ms (25s) but over platform.http.timeout_ms (12s); failover never triggers.",
        config_involved=["platform.http.timeout_ms", "platform.retry.max_attempts", "llm.timeout_ms", "llm.failover.enabled"], evidence_checked=["q.invocation latency_ms=15000 finish_reason=stop", "r.ui_error error_code=UI_TIMEOUT"],
        ruled_out=["validation", "retrieval"], fix="Raise platform.http.timeout_ms for tenant; Q to look at provider latency.", detection_tip="Gateway success + UI error means the platform hop budget is the limit."))
hist(id="CASE-004", title="Assistant ignores tenant documents (v3)", tenant="t-wayne", version="v3", reported_by="support-engineer",
     description="Wayne Foods says answers are generic and never quote their uploaded manuals. First suspicion was model quality at the gateway, then retrieval.",
     teams=["Q", "G", "B"], bounces=2, quality="good",
     notes="Effective top_k for the tenant was 2 due to a tenant override set by Team B during a cost experiment. The manual section ranks 5th, so it never reaches context. g.retrieval showed n_chunks=2. Removed the override (default top_k=8 on v3). Not a model or RAG bug.",
     scenario=Scenario("v3", "t-wayne", overrides={"tune.top_k": 2}, relevant_doc_rank=5,
                       config_changes=[{"flag": "tune.top_k", "old": 8, "new": 2, "when": "2025-03-05T14:00:00Z", "by": "cost-experiment"}]),
     answers=dict(symptom="Answers ignore tenant documents", owning_team="B", affected_versions=["v1", "v2", "v3"],
        root_cause="Tenant-level override tune.top_k=2 means the relevant chunk (rank 5) is never retrieved.",
        config_involved=["tune.top_k", "tune.tenant_override.enabled"], evidence_checked=["g.retrieval n_chunks=2 top_k_effective=2", "b.config_change audit for tenant"],
        ruled_out=["model quality (LLM gateway)", "RAG rewrite"], fix="Remove the tenant override so default top_k applies (8 on v3, 5 on v1/v2).",
        detection_tip="Check g.retrieval top_k_effective against the default and look in b.config_change for tenant overrides."))
hist(id="CASE-005", title="Answers stopped using our docs", tenant="t-stark", version="v1", reported_by="support-engineer",
     description="Stark Industries (v1): answers lost document references since last week. Support restarted things, no change at first.",
     teams=["G", "Q", "B"], bounces=2, notes="restarted rag and it worked", quality="vague",
     scenario=Scenario("v1", "t-stark", overrides={"tune.top_k": 1}, relevant_doc_rank=3, config_changes=[{"flag": "tune.top_k", "old": 5, "new": 1, "when": "2025-03-04T10:00:00Z", "by": "tenant-admin"}]),
     answers=dict(symptom="Answers ignore documents", owning_team="B", affected_versions=["v1", "v2", "v3"],
        root_cause="Tenant override tune.top_k=1; the relevant doc ranks 3rd. The restart refreshed config which masked the issue only briefly.",
        config_involved=["tune.top_k"], evidence_checked=["g.retrieval n_chunks=1", "b.config_change tune.top_k 5->1"], ruled_out=["RAG service crash", "LLM gateway"],
        fix="Reset tune.top_k override to default 5 for the tenant.", detection_tip="g.retrieval n_chunks=1 with top_k_effective=1 means an override; check b.config_change."))
hist(id="CASE-006", title="Intermittent errors in One-Way UI", tenant="t-umbrella", version="v2", reported_by="support-engineer",
     description="Umbrella Media: One-Way UI shows ERR_UPSTREAM randomly, mostly during their afternoon batch. Chat UI mostly fine.",
     teams=["U", "R", "Q"], bounces=1, quality="adequate",
     notes="q.ratelimit lines at the gateway: rpm=85 vs limit 60 for the tenant. One-Way UI has no retry (ui.retry.enabled=false), so the first 429 surfaces as ERR_UPSTREAM. Interim: raised llm.ratelimit.per_tenant_rpm to 120 for the tenant.",
     scenario=Scenario("v2", "t-umbrella", "oneway", False, overrides={"tune.rewrite.mode": "single_shot"}, tenant_rpm_load=85),
     answers=dict(symptom="Intermittent ERR_UPSTREAM in One-Way UI", owning_team="Q", affected_versions=["v2"],
        root_cause="Per-tenant rate limit (60 rpm) at the LLM gateway is exceeded; One-Way UI has no retry so the 429 becomes a generic error.",
        config_involved=["llm.ratelimit.per_tenant_rpm", "ui.retry.enabled"], evidence_checked=["q.ratelimit rpm=85 limit=60", "u.request status=error"],
        ruled_out=["One-Way UI bug", "validation"], fix="Raise llm.ratelimit.per_tenant_rpm for the tenant or smooth the batch; consider enabling UI retry.",
        detection_tip="u.request has no error code; look for q.ratelimit lines at the same time."))
hist(id="CASE-007", title="Wrong answer only sometimes after settings change", tenant="t-globex", version="v3", reported_by="support-engineer",
     description="Globex Bank: after the team changed retrieval settings, some questions still return old-style answers while others are right. 'Worked yesterday.'",
     teams=["Q", "B", "G"], bounces=2, notes="cleared cache, fine now", quality="vague",
     scenario=Scenario("v3", "t-globex", cache_stale=True, config_changes=[{"flag": "tune.top_k", "old": 4, "new": 8, "when": "2025-03-11T16:02:00Z", "by": "tenant-admin"}]),
     answers=dict(symptom="Intermittent stale answers after Tune change", owning_team="G", affected_versions=["v3"],
        root_cause="v3 response cache keyed by query+tenant+tune-hash is not invalidated on Tune changes (rag.cache.invalidate_on_tune_change=false), so old answers are served.",
        config_involved=["rag.cache.enabled", "rag.cache.invalidate_on_tune_change", "tune.top_k"], evidence_checked=["g.cache hit_or_miss=hit", "no q.invocation for the trace", "b.config_change shortly before"],
        ruled_out=["model nondeterminism", "retrieval bug"], fix="Purge tenant cache; set rag.cache.invalidate_on_tune_change=true (v3 only).",
        detection_tip="Bad answers with g.cache hit and no q.invocation line for the trace id."))
hist(id="CASE-008", title="Users get a generic error after reindex", tenant="t-globex", version="v3", reported_by="support-engineer",
     description="Globex Bank: every question now returns 'something went wrong' since their documents were re-indexed over the weekend.",
     teams=["R", "V", "G"], bounces=2, quality="adequate",
     notes="v.verdict shows FAIL code=VAL_REJECT_042. Citations are required on v3 and the reindexed corpus lost source metadata so source_ids is empty. Re-indexed with metadata; validation was behaving correctly.",
     scenario=Scenario("v3", "t-globex", source_metadata=False),
     answers=dict(symptom="Generic error on every question after reindex", owning_team="G", affected_versions=["v3"],
        root_cause="validation.citations.required=true on v3 rejects responses with no source ids; the reindexed corpus has no source metadata.",
        config_involved=["validation.citations.required"], evidence_checked=["v.verdict FAIL VAL_REJECT_042", "g.chunk_ids (masked, enabled temporarily)"],
        ruled_out=["validation bug", "LLM gateway"], fix="Re-index with source metadata. Do not disable citations as a first move.",
        detection_tip="VAL_REJECT_042 means no citations; enable obs.rag_g.masked_chunk_id_log to see empty chunk/source ids."))
hist(id="CASE-009", title="Answer tone changes mid-conversation", tenant="t-wayne", version="v3", reported_by="support-engineer",
     description="Wayne Foods: in one conversation the assistant switched to short, terse answers halfway through.",
     teams=["E", "Q"], bounces=1, quality="adequate",
     notes="q.failover lines show provider-a -> provider-b due to rate limiting; provider-b has a more concise style. Works as designed on v3 (llm.failover.enabled=true). Customer decision needed: accept, or pin the provider.",
     scenario=Scenario("v3", "t-wayne", tenant_rpm_load=75),
     answers=dict(symptom="Answer style changes mid-conversation", owning_team="Q", affected_versions=["v3"],
        root_cause="Provider failover (default ON in v3) switched to provider-b after a rate-limit event; provider-b has a different style.",
        config_involved=["llm.failover.enabled", "llm.ratelimit.per_tenant_rpm"], evidence_checked=["q.ratelimit", "q.failover provider-a->provider-b"],
        ruled_out=["adapter change", "validation"], fix="Works as designed; customer decides whether to disable failover or raise the rate limit.", detection_tip="Look for q.failover lines (v3 only)."))
hist(id="CASE-010", title="Tuned behaviour gone for one tenant", tenant="t-northwind", version="v1", reported_by="support-engineer",
     description="Northwind Retail: the assistant used to answer in their house style; now it sounds generic. Nothing was changed on their side.",
     teams=["Q", "G", "E"], bounces=2, notes="adapter thing fixed", quality="vague",
     scenario=Scenario("v1", "t-northwind", adapter_present=False),
     answers=dict(symptom="Answers generic, tenant tuning lost", owning_team="E", affected_versions=["v1", "v2"],
        root_cause="Adapter lookup by tenant_id found nothing after a tenant id change, so the adapter layer silently fell back to the base model (silent in v1/v2).",
        config_involved=["ft.adapter.fallback_to_base"], evidence_checked=["e.adapter adapter_selected=base"], ruled_out=["model quality", "retrieval"],
        fix="Re-register the adapter under the current tenant_id.", detection_tip="v1/v2: e.adapter shows adapter_selected=base with no warning. v3 logs a fallback WARN."))
hist(id="CASE-011", title="Cannot trace One-Way failures", tenant="t-umbrella", version="v2", reported_by="support-engineer",
     description="Umbrella Media One-Way UI failures cannot be traced: support only has a request id, no trace id, and the gateway logs are keyed by trace id.",
     teams=["U", "Q", "G"], bounces=1, notes="enabled logging, found it", quality="vague",
     scenario=Scenario("v2", "t-umbrella", "oneway", False, overrides={"tune.rewrite.mode": "single_shot"}, tenant_rpm_load=85, obs_enabled=("obs.oneway_u.verbose_log",)),
     answers=dict(symptom="One-Way failures cannot be correlated to backend logs", owning_team="U", affected_versions=["v2", "v3"],
        root_cause="One-Way UI drops trace_id in prod and logs only request id and status; evidence gap, not a defect.",
        config_involved=["obs.oneway_u.verbose_log"], evidence_checked=["u.verbose (after enabling)", "q.ratelimit by timestamp"], ruled_out=["bug in gateway logging"],
        fix="Temporarily enable obs.oneway_u.verbose_log (global, log volume risk) and correlate by timestamp.", detection_tip="Enable obs.oneway_u.verbose_log for a short window; correlate to q.* by timestamp."))
hist(id="CASE-012", title="Timeouts persist after enabling failover", tenant="t-acme", version="v2", reported_by="support-engineer",
     description="Acme Logistics (v2): chat UI times out on slow answers. A colleague set llm.failover.enabled=true for the tenant per a v3 doc; no change.",
     teams=["R", "Q", "PLATFORM"], bounces=2, quality="good",
     notes="llm.failover.enabled does not exist on v2 (introduced in v3), so the override is ignored. Real cause: provider latency 11s vs platform.http.timeout_ms=8000. Fixed by raising platform.http.timeout_ms to 15000 for the tenant. Longer term: upgrade to v3 for failover.",
     scenario=Scenario("v2", "t-acme", provider_latency_ms=11000, overrides={"llm.failover.enabled": True}),
     answers=dict(symptom="Timeouts persist after a v3-only flag was set", owning_team="PLATFORM", affected_versions=["v1", "v2"],
        root_cause="v3 mitigation (llm.failover.enabled) is not available on v2; the real cause is provider latency above platform.http.timeout_ms.",
        config_involved=["llm.failover.enabled", "platform.http.timeout_ms"], evidence_checked=["q.invocation latency_ms=11000 finish_reason=stop"],
        ruled_out=["failover (absent on v2)"], fix="Raise platform.http.timeout_ms; recommend upgrade to v3 for failover.", detection_tip="Check the flag exists for the customer's version in config_flags before recommending it."))
hist(id="CASE-013", title="Batch jobs failing at the gateway", tenant="t-umbrella", version="v2", reported_by="support-engineer",
     description="Umbrella Media One-Way batch jobs fail in bursts of errors every night around 02:00.",
     teams=["U", "Q"], bounces=1, notes="ratelimit thing, raised limit", quality="vague",
     scenario=Scenario("v2", "t-umbrella", "oneway", False, overrides={"tune.rewrite.mode": "single_shot"}, tenant_rpm_load=95),
     answers=dict(symptom="Burst failures during nightly batch", owning_team="Q", affected_versions=["v2"],
        root_cause="Nightly batch exceeds llm.ratelimit.per_tenant_rpm=60 (observed 95 rpm).", config_involved=["llm.ratelimit.per_tenant_rpm"],
        evidence_checked=["q.ratelimit rpm=95 limit=60"], ruled_out=["One-Way UI defect"], fix="Raised per-tenant rpm to 120 and asked the customer to spread the batch.",
        detection_tip="q.ratelimit lines aligned with failure bursts."))
hist(id="CASE-014", title="Tuned answers missing after migration", tenant="t-wayne", version="v3", reported_by="support-engineer",
     description="Wayne Foods (v3): after migrating their tenant, answers lost the tuned tone.",
     teams=["Q", "E"], bounces=1, quality="adequate",
     notes="e.adapter logs a WARN fallback_to_base reason=no_adapter_for_tenant (v3 only). Adapter not registered after migration. Registered it.",
     scenario=Scenario("v3", "t-wayne", adapter_present=False),
     answers=dict(symptom="Tuned tone lost after migration", owning_team="E", affected_versions=["v3"],
        root_cause="No adapter registered for the migrated tenant; adapter layer fell back to the base model (v3 logs a WARN).", config_involved=["ft.adapter.fallback_to_base"],
        evidence_checked=["e.adapter WARN fallback_to_base"], ruled_out=["model quality"], fix="Register the adapter for the tenant.", detection_tip="e.adapter WARN fallback_to_base on v3."))

# ---------------------------------------------------------------- HELD-OUT (8, hidden ground truth)
G = []
def held(**k): G.append(k)

def kq(topic, *any_of): return {"topic": topic, "any_of": list(any_of)}

held(id="CASE-101", title="Widget gives odd answers, chat is fine", tenant="t-acme", version="v2",
     description="Acme Logistics reports that their embedded assistant widget returns strange 'not enough information' answers for simple questions. Their users in the main chat app get good answers for the same questions. Raised by a support engineer, contact priya.n@acmelogistics.example.",
     scenario=Scenario("v2", "t-acme", "oneway", False),
     gt=dict(owning_team="B", root_cause="v2 default tune.rewrite.mode=history_aware with One-Way UI (no session) yields an empty rewritten query and 0 retrieved chunks.",
        false_lead="U", first_guess_wrong_team="U", expected_redirect=["U", "B"], expected_escalate=False,
        key_questions_needed=[kq("interactive vs one-way comparison", "interactive", "chat ui"), kq("session context", "session"), kq("rewrite mode / overrides", "rewrite", "tune.rewrite.mode")],
        needed_evidence=["g.rewrite", "g.retrieval", "tune.rewrite.mode"],
        version_caveat="On v3 the default is fixed (single_shot for One-Way); the fix is a v2 tenant override.", invalid_fix_flags=[]))
held(id="CASE-102", title="One-Way odd answers continue after upgrade to v3", tenant="t-wayne", version="v3",
     description="Wayne Foods upgraded to v3 last week. Their One-Way widget now fails with ERR_UPSTREAM on most questions, though we were told the One-Way rewrite default was fixed in v3. Interactive chat is fine. Validation team says their rejections are 'working as intended' (citations are required on v3).",
     scenario=Scenario("v3", "t-wayne", "oneway", False, overrides={"tune.rewrite.mode": "history_aware"},
                       config_changes=[{"flag": "tune.rewrite.mode", "old": "single_shot", "new": "history_aware", "when": "2025-03-09T08:00:00Z", "by": "migration-script"}]),
     gt=dict(owning_team="B", root_cause="A tenant-level override tune.rewrite.mode=history_aware (pinned during upgrade migration) overrides the fixed v3 default; with no session the rewrite is empty, no source ids are returned, and v3 citation validation rejects every response (VAL_REJECT_042).",
        false_lead="V", first_guess_wrong_team="U", expected_redirect=["U", "V", "B"], expected_escalate=False,
        key_questions_needed=[kq("tenant overrides / config change history", "override", "b.config_change", "config change"), kq("rewrite mode effective value", "rewrite", "tune.rewrite.mode"), kq("interactive vs one-way", "interactive")],
        needed_evidence=["b.config_change", "g.rewrite", "v.verdict", "tune.rewrite.mode"],
        version_caveat="v3 default is already fixed; do not blindly apply the v2 'set single_shot' fix, remove the stale tenant override instead.", invalid_fix_flags=[]))
held(id="CASE-103", title="Timeouts on chat for industrial customer", tenant="t-stark", version="v1", description="Stark Industries (v1) chat users get 'something went wrong' on longer questions, sometimes after about 8 seconds. Support suspects the LLM gateway is slow and wants the gateway team to add a fallback provider.",
     scenario=Scenario("v1", "t-stark", provider_latency_ms=11000),
     gt=dict(owning_team="PLATFORM", root_cause="Provider latency (11s) below llm.timeout_ms but above platform.http.timeout_ms (8s) on v1; the gateway reports success.",
        false_lead="Q", first_guess_wrong_team="Q", expected_redirect=["Q", "PLATFORM"], expected_escalate=False,
        key_questions_needed=[kq("how long before the error / latency", "seconds", "latency", "how long"), kq("gateway outcome for the trace", "q.invocation", "gateway", "finish_reason"), kq("trace id", "trace")],
        needed_evidence=["q.invocation", "r.ui_error", "platform.http.timeout_ms"],
        version_caveat="llm.failover.enabled does not exist on v1; mitigation is raising platform.http.timeout_ms, or upgrade.", invalid_fix_flags=["llm.failover.enabled", "llm.ratelimit.per_tenant_rpm", "rag.cache.invalidate_on_tune_change"]))
held(id="CASE-104", title="Every answer returns a generic error", tenant="t-hooli", version="v3", description="Hooli Cloud (v3): all questions now return a generic error message. The validation team's rejection counter is climbing. Customer says nothing changed on their side except a nightly docs sync.",
     scenario=Scenario("v3", "t-hooli", obs_enabled=()),
     gt=dict(owning_team="G", root_cause="v3 requires citations; the tenant's retrieval returns no source metadata (source_ids empty), so validation rejects every response (VAL_REJECT_042).",
        false_lead="V", first_guess_wrong_team="V", expected_redirect=["V", "G"], expected_escalate=False,
        key_questions_needed=[kq("validation reason code", "reason code", "v.verdict", "VAL_REJECT"), kq("source metadata / citations in retrieval", "source", "citation", "metadata"), kq("docs sync change", "sync", "re-index", "reindex")],
        needed_evidence=["v.verdict", "g.chunk_ids", "obs.rag_g.masked_chunk_id_log", "validation.citations.required"],
        version_caveat="Citations are only required by default in v3; on v1/v2 this symptom would not occur.", invalid_fix_flags=["validation.citation_check"]))
held(id="CASE-105", title="Random failures in embedded widget", tenant="t-wonka", version="v2", description="Wonka Labs reports random failures in the embedded widget during their bulk summarisation runs. Customer ID WL-8841. Widget error is ERR_UPSTREAM; the chat app is fine.",
     scenario=Scenario("v2", "t-wonka", "oneway", False, overrides={"tune.rewrite.mode": "single_shot"}, tenant_rpm_load=90, config_changes=[{"flag": "tune.rewrite.mode", "old": "history_aware", "new": "single_shot", "when": "2025-02-20T10:00:00Z", "by": "ops-bot"}]),
     gt=dict(owning_team="Q", root_cause="Per-tenant rate limit (60 rpm, v2+) exceeded by bulk runs; One-Way UI has no retry so the 429 surfaces as ERR_UPSTREAM.",
        false_lead="U", first_guess_wrong_team="U", expected_redirect=["U", "Q"], expected_escalate=False,
        key_questions_needed=[kq("request volume / rate during runs", "rate", "rpm", "volume", "bulk"), kq("gateway rate limit events", "q.ratelimit", "rate limit", "429"), kq("trace id / timestamps", "timestamp", "trace", "time")],
        needed_evidence=["q.ratelimit", "u.request", "llm.ratelimit.per_tenant_rpm"],
        version_caveat="On v3 provider failover would mask this; on v2 raise llm.ratelimit.per_tenant_rpm or spread load. llm.failover.enabled is not available on v2.", invalid_fix_flags=["llm.failover.enabled"]))
held(id="CASE-106", title="Assistant lost our brand voice after upgrade", tenant="t-initech", version="v3", description="Initech Health (v3): answers sound generic since the platform upgrade. Support thinks the new model is simply worse and asks the LLM gateway team to roll back the model.",
     scenario=Scenario("v3", "t-initech"),
     gt=dict(owning_team="E", root_cause="No adapter registered for the tenant after upgrade; adapter layer falls back to base model (WARN in v3 logs).",
        false_lead="Q", first_guess_wrong_team="Q", expected_redirect=["Q", "E"], expected_escalate=False,
        key_questions_needed=[kq("adapter selected for tenant", "adapter", "e.adapter"), kq("fallback warning", "fallback", "warn"), kq("when did tone change / upgrade", "upgrade", "migration", "when")],
        needed_evidence=["e.adapter", "ft.adapter.fallback_to_base"],
        version_caveat="On v3 a WARN fallback_to_base line exists; on v1/v2 the fallback is silent and only adapter_selected=base is visible.", invalid_fix_flags=[]))
held(id="CASE-107", title="Answers contradict new retrieval settings", tenant="t-piedpiper", version="v3", description="Pied Piper (v3): after we raised their retrieval depth, some answers still behave like the old setting while others are right. It looks like the model is hallucinating sometimes. Another engineer suspects the Tune team.",
     scenario=Scenario("v3", "t-piedpiper", cache_stale=True, config_changes=[{"flag": "tune.top_k", "old": 4, "new": 8, "when": "2025-03-11T09:30:00Z", "by": "tenant-admin"}]),
     gt=dict(owning_team="G", root_cause="v3 response cache is not invalidated after the Tune change (rag.cache.invalidate_on_tune_change=false), serving stale answers.",
        false_lead="Q", first_guess_wrong_team="B", expected_redirect=["Q", "B", "G"], expected_escalate=False,
        key_questions_needed=[kq("cache hit/miss", "cache", "g.cache"), kq("time of settings change vs bad answers", "change", "b.config_change", "when"), kq("trace id of a stale answer", "trace")],
        needed_evidence=["g.cache", "b.config_change", "rag.cache.invalidate_on_tune_change"],
        version_caveat="The cache and its invalidation flag exist only in v3; on v1/v2 this symptom has another cause.", invalid_fix_flags=[]))
held(id="CASE-108", title="Assistant feels worse lately", tenant="t-northwind", version="v1", description="A Northwind Retail user said 'the assistant feels worse lately'. No example question, no trace id, no time given. Support has no further details and can reach the customer only through their account manager.",
     scenario=Scenario("v1", "t-northwind", overrides={"tune.top_k": 1}, relevant_doc_rank=4, config_changes=[{"flag": "tune.top_k", "old": 5, "new": 1, "when": "2025-03-06T09:00:00Z", "by": "tenant-admin"}]),
     gt=dict(owning_team="B", acceptable_owners=["B", "G"], root_cause="(Unknowable from the report.) Actual: tenant override tune.top_k=1, effective params not visible without the masked/volume log.",
        false_lead=None, first_guess_wrong_team=None, expected_redirect=[], expected_escalate=True,
        key_questions_needed=[kq("example question and time", "example", "question", "when"), kq("trace id", "trace"), kq("config change history", "change", "b.config_change", "override")],
        needed_evidence=["b.config_change", "g.retrieval", "obs.tune_b.effective_params_log"],
        version_caveat="v1 has no rewrite mode, cache or failover; do not suggest v2/v3 flags.", invalid_fix_flags=["llm.failover.enabled", "tune.rewrite.mode", "rag.cache.invalidate_on_tune_change"]))

# ---------------------------------------------------------------- build
def fmt_logs(res, only_ui=False):
    ev = [e for e in res.events if e["visible"] and (not only_ui or e["stream"] in UI_STREAMS)]
    return [e["line"] for e in ev]

def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")

def main():
    from repos.sim import TENANTS
    for c in H:
        sc = c["scenario"]; res = run(sc)
        write(ROOT / "cases/history" / f"{c['id']}.json", {
            "id": c["id"], "title": c["title"], "reported_by": c["reported_by"], "customer_tier": TENANTS[c["tenant"]]["tier"],
            "tenant_id": c["tenant"], "customer": TENANTS[c["tenant"]]["name"], "version": c["version"], "description": c["description"],
            "teams_touched": c["teams"], "bounces": c["bounces"], "resolution_notes": c["notes"], "quality": c["quality"]})
        write(ROOT / "cases/gate_answers" / f"{c['id']}.json", c["answers"])
        (ROOT / "world/sample_logs" / f"{c['id']}.log").write_text(f"# {c['id']} v={c['version']} symptom={res.symptom()!r} code={res.error_code}\n" + "\n".join(fmt_logs(res)) + "\n")
    for c in G:
        sc = c["scenario"]; res = run(sc)
        full = fmt_logs(res)
        write(ROOT / "cases/heldout" / f"{c['id']}.json", {
            "id": c["id"], "title": c["title"], "reported_by": "support-engineer", "customer_tier": TENANTS[c["tenant"]]["tier"],
            "tenant_id": c["tenant"], "customer": TENANTS[c["tenant"]]["name"], "version": c["version"], "description": c["description"],
            "provided_evidence": fmt_logs(res, only_ui=True) if c["id"] != "CASE-108" else [],
            "ground_truth": {**c["gt"], "scenario": asdict(sc), "observed_symptom": res.symptom(), "observed_error_code": res.error_code}})
        (ROOT / "world/sample_logs/heldout" / f"{c['id']}.log").write_text(f"# {c['id']} (evidence that EXISTS in prod for this incident; hidden from the agent)\n" + "\n".join(full) + "\n")
    print(len(H), "history,", len(G), "held-out")

if __name__ == "__main__":
    main()
