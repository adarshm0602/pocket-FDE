# Common Issues & Troubleshooting

## 1. Empty Answers (One-Way UI Only)

**You see:** "I don't have enough information to answer that."

**Why this happens:** One-Way UI submits single queries without conversation history. Some models expect context from previous turns.

**Quick fix:**
- Provide more detail in your query. Instead of "What about caching?", say "We're using a distributed system with Redis. How do we handle cache invalidation?"
- If it persists, contact support with your exact query text.

**What the team checks:**
- Is `tune.rewrite.mode` set to `history_aware`? (Wrong for one-shot queries.)
- Is retrieval returning enough chunks? (Check `tune.top_k`.)
- Is the adapter matching your tenant? (Some tenants fall back to base model.)

---

## 2. Slow Responses / Timeouts

**You see:** Request times out after 8-20 seconds.

**Why this happens:** 
- LLM gateway taking too long (20s timeout, or platform timeout at 8s in v1)
- Rate limiting if you have high request volume (v2+)
- Retrieval is slow (rare, but can happen with large datasets)

**Quick fix:**
- Try again in a few seconds (transient timeout).
- If frequent, file a ticket with timestamps.

**What the team checks:**
- LLM provider availability (failover enabled in v3?)
- Per-tenant rate limits (check if you're at quota)
- Retrieval performance (cache hit rate, chunk size)

---

## 3. Inconsistent / Different Answers

**You see:** Same question asked twice gives different answers, or "it worked yesterday but not today."

**Why this happens:**
- Cache serving stale answers (v3, if cache invalidation broke)
- Adapter selection changed for your tenant
- Model failover to different provider (v3)

**Quick fix:**
- No immediate fix. File a ticket with the exact queries that differ.

**What the team checks:**
- Was there a recent config change for your tenant? (Team B)
- Is your adapter still assigned? (Team E)
- Cache invalidation wired correctly? (Team G, v3 only)

---

## 4. Cascading Failures (Multiple Features Down)

**You see:** Many different things broken at once, or support says "platform is degraded."

**Why this happens:**
- Single config change affects multiple teams
- LLM provider outage affecting everyone
- Retrieval misconfiguration affecting dependent services

**Quick fix:**
- None on your end. Wait for the platform team to diagnose.

**What the team does:**
- Check health monitoring for cascade detection
- Review recent config changes across all teams
- Contact LLM provider to confirm availability

---

## 5. "Model Gave Me the Base Model, Not My Tuned One"

**You see:** Answers are less specific to your domain than they should be.

**Why this happens:**
- Your tenant's adapter is missing or unassigned (Team E)
- Adapter lookup failed, fell back to base model

**Quick fix:**
- Contact support with your tenant ID
- Team E will verify your adapter is assigned

**What the team checks:**
- Is your adapter in the system? (Team E, query adapter list)
- Is it assigned to your tenant? (Team E, query tenant→adapter mapping)
- Did it recently fail? (Check E logs for "adapter_not_found" or "fallback" events)

---

## Version-Specific Notes

### v1 (Baseline)
- No one-way UI (only interactive)
- No caching
- No rate limiting
- No provider failover
- Adapter fallbacks are silent (no logs)

### v2 (One-Way UI Added)
- New one-way UI option available
- Still no caching
- Rate limiting introduced (per-tenant)
- Adapter fallbacks still silent
- Different request/response contracts between UI modes

### v3 (Latest)
- Cache enabled by default (watch for stale answers)
- Citations required by default (might reject your answers if retrieval has no source metadata)
- Provider failover enabled (answers might change style mid-conversation)
- Adapter fallbacks now logged
- Platform timeout increased (12s vs 8s in v1)

---

**Can't find your issue?** → [Contact Support](../support.md)
