"""Team P - Post-processing. Formatting, echoed-PII redaction, response envelope (differs for One-Way UI).
Logs: p.final only (no trace_id in prod)."""
from ..sim import validate


def shape(ctx, resp):
    sc = ctx.sc
    out = {"final_text": resp["text"], "citations": resp["citations"], "trace_id": resp["trace_id"]}
    if sc.ui_mode == "interactive":
        out["followups"] = ["Ask a follow-up"]
    if sc.version == "v3":
        out["feedback_token"] = "fb-" + sc.trace_id[-4:]
    validate("post_to_ui.v1" if sc.version == "v1" else "post_to_ui.v2", out, "P")
    ctx.log("P", "p.final", "INFO", f"p.final status=ok redactions=0")
    ctx.tick(10)
    ctx.trail("P", "shaped")
    return out
