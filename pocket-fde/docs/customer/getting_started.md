# Getting Started with Pocket FDE

## What is Pocket FDE?

Pocket FDE (Fault Detection Engine) is a GenAI assistant platform that helps teams diagnose and resolve incidents quickly. It powers both interactive chat and one-shot embed integrations.

## For Customers

### I have a problem with my assistant

**Your assistant is giving wrong answers?** → Your issue likely originates in the Retrieval or Model layer. The assistant is retrieving the wrong context or the model is hallucinating.

**Your assistant is slow?** → This is a timeout or rate-limiting issue, usually in the LLM gateway or platform layer.

**Your assistant returns empty answers?** → One-Way UI customers often see this with single-shot queries. Interactive UI users experience this when conversation history isn't being passed correctly.

### Quick Troubleshooting

1. **Check your assistant type:**
   - Do you use interactive chat (back-and-forth conversation)? → Your issue is likely in the Interactive UI or conversation state handling.
   - Do you use one-shot embed (single query, single response)? → Your issue is likely in the One-Way UI or single-request path.

2. **Note your symptoms:**
   - When did it start? (This helps identify recent config changes.)
   - Does it affect all users or just one tenant/workspace?
   - What does the error message say, if any?

3. **Contact Support:**
   - File a ticket with your **incident title** and **symptoms**
   - Tell us your **platform version** (v1, v2, or v3)
   - Include any **error codes** or **timestamps** you see

## For Support Teams

### Routing Incidents

When a customer reports an issue, ask yourself:

| **Symptom** | **Most Likely Team** | **Evidence to Pull** |
|---|---|---|
| Wrong answers / bad retrieval | Team G (RAG) or Team B (Tune config) | Retrieval logs, config flags |
| Slow / timeout | Team Q (LLM Gateway) or PLATFORM | Latency logs, rate-limit events |
| Empty answers (One-Way only) | Team B or Team G (rewrite mode) | Rewrite logs, session context |
| Answers inconsistent / wrong sometimes | Team G (cache, v3) or Team E (adapter) | Cache hit/miss logs, adapter selection |

### When to Escalate

Escalate to the platform team if:
- Multiple teams affected (cascading failure)
- Root cause is unclear after reviewing standard logs
- Issue is intermittent and hard to reproduce
- Incident needs a config change at the platform level

---

**Next:** See [Common Issues](./common_issues.md) for specific scenarios.
