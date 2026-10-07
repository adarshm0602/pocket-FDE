"""Team U - One-Way UI (v2+). Single-shot submit, no session, no retry UX.
Logs: u.request only (req id + status, NO trace_id, NO error code); verbose log off in prod."""
from ..sim import validate


def build_request(ctx):
    sc = ctx.sc
    req = {"query": sc.query, "tenant_id": sc.tenant_id, "ui_mode": "oneway", "trace_id": sc.trace_id}  # no session_id
    validate("ui_to_rag.v2", req, "U")
    return req


def attempts(ctx):
    return (ctx.cfg.get("platform.retry.max_attempts") or 1) if ctx.cfg.get("ui.retry.enabled") else 1


def log_result(ctx, status, latency_ms, error_code=None):
    ctx.log("U", "u.request", "INFO", f"u.request id=u-{ctx.sc.trace_id[-4:]} status={status}")
    ctx.log("U", "u.verbose", "DEBUG", f"u.verbose id=u-{ctx.sc.trace_id[-4:]} latency_ms={latency_ms} error_code={error_code}")


def render_error(ctx, code):
    return "ERR_UPSTREAM"
