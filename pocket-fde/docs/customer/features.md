# Feature Guide

## Chat Modes

### Interactive Chat (All Versions)

**What it is:** Conversation with full state. You can ask follow-up questions and the assistant remembers context.

**Best for:** Research, exploratory questions, iterative problem-solving.

**Team:** Team R (Interactive UI)

**Performance:** Each request includes conversation history, so slightly slower than one-way.

### One-Way Query (v2+)

**What it is:** Single question, single answer. No conversation state. Designed for embedded use (e.g., in email, in a doc, in a scheduled job).

**Best for:** Quick lookups, batch processing, embedding in other systems.

**Team:** Team U (One-Way UI)

**Performance:** Faster and cheaper (no session overhead), but can't do follow-ups.

**Note:** One-Way queries sometimes return "not enough information" if the model doesn't have context from previous turns. If you see this, make your question more specific.

---

## Retrieval & Context

### What Retrieval Does

Your questions get matched against a knowledge base (documents, past Q&As, company wiki, etc.). The top results are sent to the model along with your question.

**Team:** Team G (RAG Flow)

**Factors that affect quality:**
- **Number of results retrieved** (Team B controls this via `tune.top_k`)
  - Too few (3-5) → might miss relevant info
  - Too many (20+) → model gets confused by noise
- **Your question quality**
  - Specific questions get better matches than vague ones
- **Knowledge base freshness**
  - Outdated docs lead to outdated answers

### Caching (v3 Only)

Your responses are cached if you ask the same (or very similar) question. This makes repeat queries instant.

**Note:** If we update the knowledge base or tune the model, the cache is invalidated. If you see inconsistent answers after an update, it might be a cache timing issue—contact support.

---

## Customization

### Tuning (All Versions)

Your tenant can be configured to use a **specialized model variant** tuned for your domain or use case.

**Team:** Team E (Fine-tune / Adapter layer)

**What this means for you:**
- If configured, your questions go to a specialized model that's better for your use case
- Faster and cheaper than the base model for your domain
- If misconfigured or missing, you fall back to the general base model

**How to check:** Ask support if your tenant has a tuned adapter assigned.

---

## Safety & Content Filtering

### Guardrails (All Versions)

Before your question reaches the model, it's checked for:
- Abuse patterns (jailbreaks, prompt injection)
- Sensitive content (if enabled; off by default to avoid false positives)
- Policy violations (e.g., asking for internal-only information)

**Team:** Team V (Validation)

**What happens if filtered:** You'll see an error message. Contact support if you think it's a false positive.

---

## Observability (What We Log)

We log:
- Your request timestamps and response times
- Error messages and codes
- Model provider info (in case we switch providers mid-session)
- Citations and sources (if citations are required in your version)

**We don't log:**
- Your actual questions or answers (too much PII risk)
- Retrieval results (unless you have a support incident)

If you need detailed debugging, contact support and we can enable debug logging temporarily.

---

**Questions?** → [Getting Started](./getting_started.md) or [Common Issues](./common_issues.md)
