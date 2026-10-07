"""Team R - Interactive UI + BFF. Keeps session state; shows errors to the user.
Logs: r.request, r.ui_error (on); full query text off in prod (PII). trace_id logged raw."""
from ..sim import HopError, validate


def build_request(ctx):
    sc = ctx.sc
    req = {"query": sc.query, "tenant_id": sc.tenant_id, "ui_mode": "interactive", "trace_id": sc.trace_id}
    if sc.has_session:
        req["session_id"] = "sess-1042"
    validate("ui_to_rag.v1" if sc.version == "v1" else "ui_to_rag.v2", req, "R")
    return req


def attempts(ctx):
    return ctx.cfg.get("platform.retry.max_attempts") or 1


def log_result(ctx, status, latency_ms, error_code=None):
    sc = ctx.sc
    ctx.log("R", "r.request", "INFO", f"{ctx.ts()} INFO ui-r req=req-{sc.trace_id[-4:]} tenant={sc.tenant_id} latency_ms={latency_ms} status={status}")
    ctx.log("R", "r.masked_query", "DEBUG", f"{ctx.ts()} DEBUG ui-r req=req-{sc.trace_id[-4:]} query_masked=\"{sc.query[:12]}***\"")
    if error_code:
        ctx.log("R", "r.ui_error", "WARN", f"{ctx.ts()} WARN ui-r req=req-{sc.trace_id[-4:]} error_code={error_code}")


def render_error(ctx, code):
    return "Sorry, something went wrong. Please try again."
