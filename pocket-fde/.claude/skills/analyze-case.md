---
name: analyze-case
description: Investigate a Pocket FDE case by ID using reviewed knowledge, version definitions and evidence; produce an owner hypothesis and questions.
---

# Analyze Case

Open either the repository root or `pocket-fde/` in your editor. File paths below are relative to the Git repository root; find it before running a command.

1. Ask for a case ID (for example, CASE-101), or a title, description, platform version and supplied evidence.
2. Locate the incident under `pocket-fde/cases/`, `cases/heldout/` or `cases/history/`. Hidden `ground_truth` and gate answers are evaluation references: exclude them from the investigation. Treat resolved history as prior experience, not proof of a new incident's cause.
3. Check `pocket-fde/world/ownership.yaml`, `config_flags.yaml`, `versions.yaml` and `observability.yaml`, plus relevant customer guides and approved Second Brain cards/notes. Pending and rejected learning must not support an answer.
4. Compare plausible mechanisms against supplied evidence and the customer's version. Cite the exact file or source ID for each factual claim. Distinguish the flag/mechanism owner from the UI or logging team.
5. Return an owner hypothesis, confidence with reasons, case-specific diagnostic questions in one round, available logs and enablement caveats, a conditional version-compatible fix, and a handover brief. Escalate when evidence is insufficient. Never invent observed checks, logs, flags or probability percentages.
6. Recommend capture of a resolved learning through `/capture-learning`; a human must approve it before reuse.

For the current Gemini-backed retrieval, grounding and measured token usage, use the web app's Analyze action with Keyword or Hybrid Search. This editor skill supplies investigation instructions; it does not automatically call the deployed API or execute customer changes.

## Restored original demonstration helper

From the repository root:

```sh
.venv/bin/python .claude/skills/analyze-case/analyze.py CASE-001
```

`analyze.py` and `index.py` retain Surya's early rule-based demonstration. Its confidence is an illustrative heuristic, not accuracy. It makes no LLM call and reports zero model tokens. It is not the evaluated Gemini web pipeline. No fixed latency, 100% accuracy or token-saving claim is made.
