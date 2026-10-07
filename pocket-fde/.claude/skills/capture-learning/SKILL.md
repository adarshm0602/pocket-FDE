---
name: capture-learning
description: Capture shared Pocket FDE learning as a pending draft with explicit human review.
---

# Capture Learning

The canonical tool and review rules live at the outer Git repository root:
[Read the canonical skill](../../../../.claude/skills/capture-learning/SKILL.md).

Find the Git root before running its commands; do not create a second capture implementation under `pocket-fde/`. Use `.venv/bin/python .claude/skills/capture-learning/capture.py` from that root. A new learning always starts as pending and must be excluded from retrieval until a human reviews it. Never approve a learning on the human's behalf. Preserve version-scope uncertainty and the canonical tool's explicit `APPROVE` confirmation.

Web Second Brain submissions are a separate, shared cloud workflow. This local tool does not write to that cloud collection.
