"""Team Q - LLM gateway. Invocation, llm timeout, per-tenant rate limit (v2+), provider failover (v3).
Logs: q.invocation, q.ratelimit (v2+), q.failover (v3). Prompt/response bodies off in prod (PII + cost)."""
from ..sim import HopError, validate


def _lf(ctx, level, stream, **f):
    ctx.log("Q", stream, level, f"ts={ctx.ts()} level={level} svc=llm-gw " + " ".join(f"{k}={v}" for k, v in f.items()))


def invoke(ctx, req, attempt=0):
    sc, cfg = ctx.sc, ctx.cfg
    tid = sc.trace_id
    provider, latency = "provider-a", sc.provider_latency_ms
    failed_over = False

    def failover(reason):
        nonlocal provider, latency, failed_over
        _lf(ctx, "WARN", "q.failover", trace_id=tid, from_provider=provider, to_provider="provider-b", reason=reason)
        provider, latency, failed_over = "provider-b", sc.secondary_latency_ms, True
        ctx.flags["style_changed"] = True

    limit = cfg.get("llm.ratelimit.per_tenant_rpm")
    if limit and sc.tenant_rpm_load > limit * (1 + 0.5 * attempt):
        _lf(ctx, "WARN", "q.ratelimit", trace_id=tid, tenant=sc.tenant_id, rpm=sc.tenant_rpm_load, limit=limit)
        if cfg.get("llm.failover.enabled"):
            failover("rate_limited")
        else:
            ctx.tick(30)
            ctx.trail("Q", "429 rate limited")
            raise HopError("Q", "LLM_RATE_LIMITED", "per-tenant rpm exceeded")

    timeout = cfg.get("llm.timeout_ms")
    if latency > timeout:
        _lf(ctx, "INFO", "q.invocation", trace_id=tid, provider=provider, latency_ms=timeout, finish_reason="timeout", tokens=0)
        ctx.tick(timeout)
        if cfg.get("llm.failover.enabled") and not failed_over:
            failover("timeout")
        else:
            ctx.trail("Q", "llm timeout")
            raise HopError("Q", "LLM_TIMEOUT", f"provider exceeded llm.timeout_ms={timeout}")

    chunks = req["_context"]
    if req["model_variant"] == "base":
        text = "Generic answer from the base model (no tenant tuning)."
    elif any(c["relevant"] for c in chunks):
        text = "Grounded answer using the tenant's documents."
    elif chunks:
        text = "Generic answer; no matching document was in the context."
    else:
        text = "I don't have enough information to answer that."
    if failed_over:
        text = "[concise style] " + text
    _lf(ctx, "INFO", "q.invocation", trace_id=tid, provider=provider, latency_ms=latency, finish_reason="stop", tokens=412)
    ctx.tick(latency)
    ctx.trail("Q", f"{provider} {latency}ms")
    out = {"raw_text": text, "finish_reason": "stop", "usage": {"tokens": 412}, "provider": provider, "trace_id": tid,
           "_source_ids": req["_source_ids"]}
    validate("llm_to_val.v1", out, "Q")
    return out
