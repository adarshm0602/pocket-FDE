"""Team B - Tune / RAG config layer. Owns retrieval params and per-tenant overrides.
Logs: b.config_change (on), b.effective_params (off in prod - volume). trace_id is HASHED here."""
import hashlib
import json

from ..sim import validate


def _tid_hash(trace_id):
    return hashlib.sha1(trace_id.encode()).hexdigest()[:8]


def get_params(ctx, ui_mode):
    sc, cfg = ctx.sc, ctx.cfg
    for ch in sc.config_changes:  # audit events from earlier changes
        ctx.log("B", "b.config_change", "INFO", json.dumps(
            {"ts": ch.get("when", "2025-03-11T16:02:00Z"), "evt": "config_change", "tenant": sc.tenant_id,
             "flag": ch["flag"], "old": ch["old"], "new": ch["new"], "by": ch.get("by", "ops-bot")}))
    allow = cfg.get("tune.tenant_override.enabled")
    top_k = cfg.get("tune.top_k") if allow else None
    if top_k is None:
        from ..sim import FLAGS
        top_k = FLAGS["tune.top_k"][sc.version]
    if cfg.exists("tune.rewrite.mode"):
        if "tune.rewrite.mode" in sc.overrides:
            mode = sc.overrides["tune.rewrite.mode"]
        elif sc.version == "v3":
            mode = "single_shot" if ui_mode == "oneway" else "history_aware"
        else:
            mode = "history_aware"  # v2 default: wrong for One-Way UI
    else:
        mode = "history_aware"      # v1: always history-aware, no flag
    params = {"top_k": top_k, "chunk_size": 512, "rerank_weight": 0.3, "overrides": list(sc.overrides),
              "rewrite_mode": mode}
    validate("tune_params.v1", params, "B")
    ctx.log("B", "b.effective_params", "DEBUG", json.dumps(
        {"evt": "effective_params", "tid_hash": _tid_hash(sc.trace_id), "tenant": sc.tenant_id, **{k: params[k] for k in ("top_k", "rewrite_mode")}}))
    ctx.tick(5)
    ctx.trail("B", f"params top_k={top_k} rewrite_mode={mode}")
    return params
