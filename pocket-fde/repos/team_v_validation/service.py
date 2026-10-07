"""Team V - Response validation. Schema + citation checks. Reason codes are intentionally vague.
v1/v2: validation.citation_check (off). v3: validation.citations.required (on). Rejected text log off (PII)."""
from ..sim import HopError, validate


def check(ctx, resp):
    cfg, sc = ctx.cfg, ctx.sc
    required = bool(cfg.get("validation.citations.required")) or bool(cfg.get("validation.citation_check"))
    code = None
    if required and not resp["_source_ids"]:
        code = "VAL_REJECT_042"   # means: no citations available
    if code:
        ctx.log("V", "v.verdict", "INFO", f"VERDICT trace={sc.trace_id} result=FAIL code={code}")
        ctx.tick(15)
        ctx.trail("V", f"rejected {code}")
        raise HopError("V", code, "validation failed")
    ctx.log("V", "v.verdict", "INFO", f"VERDICT trace={sc.trace_id} result=PASS code=-")
    out = {"text": resp["raw_text"], "citations": resp["_source_ids"], "validation_status": "pass", "trace_id": sc.trace_id}
    validate("val_to_post.v1", out, "V")
    ctx.tick(15)
    ctx.trail("V", "pass")
    return out
