---
name: capture-solution
description: Run the closure gate on a resolved incident - convert vague notes into a structured case card
---

# Capture Solution (Closure Gate)

When an incident is resolved, use this to turn vague notes ("restarted and it worked") into a structured case card that Pocket FDE can learn from.

The gate will ask:
- Root cause (what actually broke)
- Affected versions (v1/v2/v3)
- Config flags involved
- Evidence that was checked
- What was ruled out
- How to detect it next time

Provide:
- **Case title** (e.g., "One-Way UI returns empty answers")
- **Resolution notes** (what you did to fix it, as vague as you want)
- **Teams touched** (which teams were involved)
- **Version** (v1, v2, v3)

The gate will ask follow-up questions, and output a structured card ready for curator review.
