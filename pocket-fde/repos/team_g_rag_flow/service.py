"""Team G - RAG Flow. Query rewrite, retrieval, context assembly, response cache (v3).
Logs: g.retrieval, g.rewrite (v2+), g.cache (v3); g.chunk_ids off in prod (PII/volume)."""
from ..sim import HopError, validate
from ..team_b_tune import service as tune


def _kv(ctx, level, stream, **f):
    ctx.log("G", stream, level, f"{ctx.ts()} {level} rag-flow {stream} " + " ".join(f"{k}={v}" for k, v in f.items()))


def retrieve(ctx, req):
    """Returns ('cached', text) or ('ok', rag_to_ft payload)."""
    sc, cfg = ctx.sc, ctx.cfg
    tid = sc.trace_id
    if cfg.get("rag.cache.enabled"):
        if sc.cache_stale:
            _kv(ctx, "INFO", "g.cache", trace_id=tid, hit_or_miss="hit")
            ctx.flags["stale"] = True
            ctx.tick(20)
            ctx.trail("G", "cache hit (entry predates latest Tune change; invalidate_on_tune_change=%s)" % cfg.get("rag.cache.invalidate_on_tune_change"))
            return "cached", "Based on your previous configuration, the answer is ..."
        _kv(ctx, "INFO", "g.cache", trace_id=tid, hit_or_miss="miss")
    params = tune.get_params(ctx, req["ui_mode"])
    had_session = "session_id" in req
    mode = params["rewrite_mode"]
    if cfg.exists("tune.rewrite.mode"):
        _kv(ctx, "INFO", "g.rewrite", trace_id=tid, rewrite_mode=mode, had_session=str(had_session).lower())
    rewritten = req["query"] if (mode == "single_shot" or had_session) else ""
    if not rewritten:
        ctx.flags["empty_rewrite"] = True
    top_k = params["top_k"]
    n = top_k if rewritten else 0
    chunks = [{"id": f"doc-{i}", "relevant": i == sc.relevant_doc_rank} for i in range(1, n + 1)]
    if rewritten and sc.relevant_doc_rank > top_k:
        ctx.flags["docs_ignored"] = True
    meta = sc.source_metadata if sc.source_metadata is not None else ctx.tenant["source_metadata"]
    source_ids = [c["id"] for c in chunks] if meta else []
    _kv(ctx, "INFO", "g.retrieval", trace_id=tid, n_chunks=len(chunks), rewrite_mode=mode, top_k_effective=top_k)
    _kv(ctx, "DEBUG", "g.chunk_ids", trace_id=tid, chunk_ids=",".join(source_ids) or "none")
    payload = {"prompt": rewritten or "(empty)", "context_chunks": chunks, "source_ids": source_ids,
               "tenant_id": sc.tenant_id, "trace_id": tid}
    validate("rag_to_ft.v1", payload, "G")
    ctx.tick(120)
    ctx.trail("G", f"retrieved {len(chunks)} chunks, source_ids={len(source_ids)}")
    return "ok", payload
