---
name: triage-incident
description: Run Pocket FDE triage on a new incident - retrieval + one-round questions + handover brief
---

# Triage Incident

Give Pocket FDE a new incident and it will:
1. Retrieve similar cases from the knowledge repo
2. Identify the owning team
3. Ask the next best questions **in one round**
4. Provide a handover brief for the owning team
5. If it doesn't know, escalate and ask you to capture the solution

Provide:
- **Title** (e.g., "Answers are generic, not tenant-tuned")
- **Description** (what the customer reported)
- **Version** (v1, v2, v3)
- **Current evidence** (any logs/traces already pulled)
