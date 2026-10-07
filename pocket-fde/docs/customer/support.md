# Getting Support

## Before You Contact Us

**Have you checked:**
- [Common Issues](./common_issues.md)? Your issue might be self-service fixable.
- [Features](./features.md)? Your issue might be expected behavior.
- [Getting Started](./getting_started.md)? This has basic troubleshooting steps.

---

## How to File a Support Ticket

**What we need:**

1. **Incident Title**
   - e.g., "One-Way widget returns empty answers"
   - e.g., "Chat is slow after yesterday's config change"

2. **Symptoms**
   - What are you seeing? (error message, wrong answer, timeout, etc.)
   - When did it start? (exact time or relative, e.g., "after we updated our query")
   - Does it affect all users or specific ones?

3. **Your Setup**
   - Tenant ID
   - Platform version (v1, v2, or v3)
   - UI mode (interactive chat or one-way)
   - Are you using a custom adapter? (optional)

4. **Evidence**
   - Exact query that failed (if safe to share)
   - Error codes or messages
   - Timestamps
   - Frequency (one-time, recurring, intermittent?)

**Example ticket:**
```
Title: One-Way queries timeout after 3PM daily

Symptoms: 
  Customers report timeouts (20s+) on one-way queries starting at 3PM, 
  resolves by 5PM. Interactive chat is unaffected.

Setup:
  Tenant: acme-logistics-v2
  Version: v2
  Mode: One-Way UI embed in customer portal

Evidence:
  Error: "Request timeout at 20000ms"
  Timestamps: Oct 6, 3:15 PM, 3:47 PM, 4:22 PM
  Frequency: Every day around 3 PM
```

---

## Response Times

| **Severity** | **Response** | **Resolution** |
|---|---|---|
| Platform down (all users) | 15 min | 1-2 hours |
| Major feature broken | 30 min | 2-4 hours |
| Degraded performance | 1 hour | 4-8 hours |
| Questions / feature requests | 1 business day | N/A |

---

## What Happens After You File

1. **Triage** — We classify your incident (routing, features, performance, etc.)
2. **Investigation** — We pull logs, check configs, identify the root cause
3. **Communication** — We explain what we found and next steps
4. **Resolution** — We fix it, or we escalate if it requires a platform change
5. **Closure** — We verify the fix works on your end and document the solution

---

## Common Root Causes We Find

| **You reported** | **Root cause** | **Who fixes it** | **Typical fix** |
|---|---|---|---|
| Wrong answers | Retrieval too narrow (`top_k` too low) | Team B or G | Increase `top_k`, refresh docs |
| One-way returns empty | Rewrite mode is `history_aware` (wrong for single-shot) | Team B | Change to `single_shot` for one-way path |
| Slow responses | Rate limiting quota exceeded | Team Q | Increase quota, batch requests |
| Inconsistent answers | Cache serving stale results | Team G | Manual cache invalidation, verify config |
| Cascading failures | Single platform config breaks multiple teams | PLATFORM | Revert change, test more carefully |

---

## Escalation

If your issue:
- Requires a platform-wide change
- Involves multiple teams
- Is a known gap (missing feature, known limitation)
- Needs executive approval (e.g., quota increase)

We'll escalate to the platform reliability team and set an expectation for resolution time.

---

## Contact

- **Email:** support@pocket-fde.internal
- **Slack:** #platform-support (for quick questions)
- **Status Page:** status.pocket-fde.internal

---

**Thanks for using Pocket FDE!**
