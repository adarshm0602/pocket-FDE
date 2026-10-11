---
name: analyze-case
description: Investigate a Pocket FDE case by ID using reviewed knowledge, version definitions and evidence; produce an owner hypothesis and questions.
---

# Analyze Case

Open either the repository root or `pocket-fde/` in your editor. File paths below are relative to the Git repository root; find it before running a command.

1. Ask for a case ID (for example, CASE-101), or a title, description, platform version and supplied evidence. If the user gives details but no ID, ask once for the ID before continuing.
2. Locate the case under `pocket-fde/cases/` or `cases/history/`.
   - **Existing case:** use its file. Do not create a duplicate.
   - **Held-out case (`cases/heldout/`):** investigate it for evaluation only. Do not create or change a file for it.
   - **New case:** go to step 3 before any investigation.
3. **Create the case file at the start, not at the end.** As soon as a new ID and its details are known, write `pocket-fde/cases/<CASE-ID>.json` with the fields below, before checking any world files. Use `"not established"` for unknown values, and `version: null` when the version is unconfirmed (see `pocket-fde/cases/README.md`).

   ```json
   {
     "case_number": "CASE-ID",
     "title": "...",
     "description": "...",
     "version": "v1 | v2 | v3 | null",
     "customer": "... or not established",
     "status": "OPEN",
     "opened_at": "ISO timestamp",
     "evidence": {"supplied": ["exactly what the user provided"]},
     "investigation": {"owner_hypothesis": "...", "confidence": "...", "status": "INVESTIGATING"},
     "updates": []
   }
   ```

   - When the user corrects a field (for example, the version), change the field and append `{"at", "change"}` to `updates`. Do not silently overwrite the original `description` or `evidence.supplied`.
   - Record only what the user supplied under `evidence.supplied`. Findings from the investigation go in `investigation`.
   - Never write hidden `ground_truth`, gate answers or resolution fields into the file.
   - Tell the user the path after writing. The web catalog loads `cases/CASE-*.json`, so the new case will appear there too.
4. Check `pocket-fde/world/ownership.yaml`, `config_flags.yaml`, `versions.yaml` and `observability.yaml`, plus relevant customer guides and approved Second Brain cards/notes. Pending and rejected learning must not support an answer. Treat resolved history as prior experience, not proof of a new incident's cause.
5. Compare plausible mechanisms against supplied evidence and the customer's version. Cite the exact file or source ID for each factual claim. Distinguish the flag/mechanism owner from the UI or logging team.
6. Return an owner hypothesis, confidence with reasons, case-specific diagnostic questions in one round, available logs and enablement caveats, a conditional version-compatible fix, and a handover brief. Update the case file's `investigation` field with the same hypothesis and status. Escalate when evidence is insufficient. Never invent observed checks, logs, flags or probability percentages.
7. Recommend capture of a resolved learning through `/capture-learning`; a human must approve it before reuse. Closing the case is a separate step, done with `/close-case`. Writing the case file here does not close it.

For the current Gemini-backed retrieval, grounding and measured token usage, use the web app's Analyze action with Keyword or Hybrid Search. This editor skill supplies investigation instructions; it does not automatically call the deployed API or execute customer changes.

## Restored original demonstration helper

From the repository root:

```sh
.venv/bin/python .claude/skills/analyze-case/analyze.py CASE-001
```

`analyze.py` and `index.py` retain Surya's early rule-based demonstration. Its confidence is an illustrative heuristic, not accuracy. It makes no LLM call and reports zero model tokens. It is not the evaluated Gemini web pipeline. No fixed latency, 100% accuracy or token-saving claim is made.
