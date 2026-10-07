"""Team E - Fine-tune / adapter layer. Picks adapter by tenant_id, falls back to base model.
v1/v2: fallback is SILENT (adapter_selected=base only). v3 adds a WARN line."""
from ..sim import validate


def prepare(ctx, payload):
    sc = ctx.sc
    present = sc.adapter_present if sc.adapter_present is not None else ctx.tenant["has_adapter"]
    variant = f"adapter-{sc.tenant_id}" if present else "base"
    t = ctx.ts()
    ctx.log("E", "e.adapter", "INFO", f"[adapter] {t} trace={sc.trace_id} tenant={sc.tenant_id} adapter_selected={variant}")
    if not present:
        ctx.flags["base_model"] = True
        if sc.version == "v3":
            ctx.log("E", "e.adapter", "WARN", f"[adapter] {t} WARN trace={sc.trace_id} fallback_to_base reason=no_adapter_for_tenant")
    out = {"model_variant": variant, "prompt": payload["prompt"], "max_tokens": 1024,
           "timeout_ms": ctx.cfg.get("llm.timeout_ms"), "trace_id": payload["trace_id"],
           "_context": payload["context_chunks"], "_source_ids": payload["source_ids"]}
    validate("ft_to_llm.v1", out, "E")
    ctx.tick(20)
    ctx.trail("E", f"variant={variant}")
    return out
