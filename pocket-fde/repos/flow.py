"""Runs one request through the simulated platform: UI -> RAG(+Tune) -> Fine-tune -> LLM -> Validation -> Post -> UI.

Usage: from repos.flow import run; result = run(Scenario(version="v2", ui_mode="oneway", has_session=False))
"""
from dataclasses import dataclass

from .sim import Ctx, HopError, Scenario
from .team_e_finetune import service as ft
from .team_g_rag_flow import service as rag
from .team_p_postprocess import service as post
from .team_q_llm_gateway import service as llm
from .team_r_interactive_ui import service as ui_r
from .team_u_oneway_ui import service as ui_u
from .team_v_validation import service as val


@dataclass
class Result:
    status: str                # ok | error
    user_sees: str             # what the end user saw
    error_code: object         # internal code (not always visible to the UI team)
    attempts: int
    elapsed_ms: int
    flags: dict                # answer-quality facts (stale, docs_ignored, ...)
    events: list               # all log events, with .visible per observability.yaml
    hops: list

    def visible_logs(self):
        return [e for e in self.events if e["visible"]]

    def symptom(self):
        f = self.flags
        if self.status == "error":
            return self.user_sees
        if f.get("stale"):
            return "wrong or outdated answer"
        if f.get("empty_rewrite"):
            return "empty or odd answer"
        if f.get("docs_ignored"):
            return "answer ignores the customer's documents"
        if f.get("base_model"):
            return "answer is generic, not tenant-tuned"
        if f.get("style_changed"):
            return "answer style changed"
        return "healthy answer"


def run(sc: Scenario) -> Result:
    ctx = Ctx(sc)
    ui = ui_u if sc.ui_mode == "oneway" else ui_r
    if sc.ui_mode == "oneway" and sc.version == "v1":
        raise ValueError("One-Way UI does not exist in v1")
    platform_timeout = ctx.cfg.get("platform.http.timeout_ms")
    n_attempts = ui.attempts(ctx)
    final, err, used = None, None, 0
    start_all = 0
    for attempt in range(n_attempts):
        used = attempt + 1
        start = ctx.clock_ms
        final, err = None, None
        try:
            req = ui.build_request(ctx)
            kind, payload = rag.retrieve(ctx, req)
            if kind == "cached":
                final = {"final_text": payload}
            else:
                ftp = ft.prepare(ctx, payload)
                raw = llm.invoke(ctx, ftp, attempt)
                checked = val.check(ctx, raw)
                final = post.shape(ctx, checked)
            elapsed = ctx.clock_ms - start
            if elapsed > platform_timeout:
                ctx.trail("UI", f"gave up after {elapsed}ms > platform.http.timeout_ms={platform_timeout}")
                err = HopError("PLATFORM", "UI_TIMEOUT", f"{elapsed}ms exceeded platform.http.timeout_ms")
                ctx.clock_ms = start + platform_timeout
                final = None
        except HopError as e:
            err = e
        if err is None:
            break
    elapsed_all = ctx.clock_ms - start_all
    if err:
        ui.log_result(ctx, "error", elapsed_all, err.code)
        return Result("error", ui.render_error(ctx, err.code), err.code, used, elapsed_all, ctx.flags, ctx.events, ctx.hops)
    ui.log_result(ctx, "ok", elapsed_all)
    return Result("ok", final["final_text"], None, used, elapsed_all, ctx.flags, ctx.events, ctx.hops)
