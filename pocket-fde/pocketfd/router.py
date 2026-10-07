"""Tiered routing + budget guard.
Tier 0: rules (ownership/flag/log lookups, no LLM)   Tier 1: small local model (optional)   Tier 2: frontier model, redacted + retrieved chunks only.
TIER_MODE = local_only | hybrid | frontier_only (default hybrid)."""
import os
from dataclasses import dataclass, field

from . import llm
from .redact import Redactor, log_outbound


class BudgetExceeded(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Budget:
    max_steps: int = int(os.getenv("MAX_STEPS", 6))
    max_tokens: int = int(os.getenv("MAX_TOKENS_PER_RUN", 12000))
    steps: int = 0
    tokens: int = 0

    def step(self, name=""):
        if self.steps >= self.max_steps:
            raise BudgetExceeded(f"step budget exhausted ({self.max_steps}) before '{name}'")
        self.steps += 1

    def charge(self, r):
        self.tokens += r.input_tokens + r.output_tokens
        if self.tokens > self.max_tokens:
            raise BudgetExceeded(f"token budget exceeded ({self.tokens}>{self.max_tokens})")


@dataclass
class Router:
    tier_mode: str = field(default_factory=lambda: os.getenv("TIER_MODE", "hybrid"))
    budget: Budget = field(default_factory=Budget)
    outbound_log: object = None
    calls: list = field(default_factory=list)
    completion: object = None  # Optional per-request provider; avoids changing process-wide settings.

    def local_available(self):
        if self.tier_mode == "frontier_only":
            return False
        try:
            llm.complete("ping", tier="local")
            return True
        except Exception:
            return False

    def call(self, purpose, prompt, system="", chunk_ids=(), redactor=None, external=True):
        """One budgeted LLM step. External calls MUST pass already-redacted text; we assert nothing raw leaves."""
        self.budget.step(purpose)
        tier = "local" if self.tier_mode == "local_only" else "frontier"
        if tier == "frontier" and external:
            from .redact import leaks
            bad = leaks(prompt)
            if bad:
                raise RuntimeError(f"refusing to send unredacted identifiers outbound: {bad[:3]}")
            kw = {"path": self.outbound_log} if self.outbound_log else {}
            log_outbound(purpose, prompt, list(chunk_ids), redactor.counts if redactor else {}, **kw)
        r = (self.completion or llm.complete)(prompt, system, tier=tier)
        self.budget.charge(r)
        self.calls.append({"purpose": purpose, "tier": tier, "in": r.input_tokens, "out": r.output_tokens, "latency_s": round(r.latency_s, 2), "provider": r.provider})
        return r
