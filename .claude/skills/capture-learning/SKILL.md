---
name: capture-learning
description: Capture a learning into the shared project as a draft pending human review
version: 1.1.0
---

# Capture Learning to Second Brain

Run the portable capture tool from the repository root:

```bash
.venv/bin/python .claude/skills/capture-learning/capture.py
```

It asks for the learning, a short description and detailed content (finish with `END`). It creates a unique Markdown draft in `pocket-fde/second-brain/pending/` and a **pending review** link in the shared `pocket-fde/MEMORY.md`. It never writes into a developer-specific home folder or overwrites a previous discovery.

New drafts are excluded from both live search modes. Do not approve learning on the user's behalf. The resolving developer or another human must read the draft and decide whether it belongs in shared knowledge.

## Human review

List pending Markdown drafts:

```bash
.venv/bin/python .claude/skills/capture-learning/capture.py --list
```

Review one, using its exact filename and your reviewer name:

```bash
.venv/bin/python .claude/skills/capture-learning/capture.py --review DRAFT_NAME.md --by YOUR_NAME
```

The tool shows the content and requires the human to type `APPROVE`. Approval records the reviewer and date, moves the file into `second-brain/notes/`, and updates the shared index. Both live search indexes refresh on the next request; no server restart is needed.

To reject instead, add `--reject` to the review command. Rejected learning is moved into `second-brain/rejected/` and removed from the shared memory index.

Document the supported versions in `affected_versions` only when established. An empty scope remains explicitly unconfirmed in search results and prompts; never infer version applicability from another incident. The existing curator's `--approve-all` option skips captured Markdown learning so it cannot bypass human review.

This workflow uses no LLM call or API key. Use it after discovering a cause, mapping ownership, or learning an integration pattern. Historical notes already committed to the reviewed cards/notes folders can be imported at the user's explicit request; new captures always begin as drafts.
