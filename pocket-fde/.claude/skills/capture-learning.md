# Capture Learning

The canonical skill and review policy are in [capture-learning/SKILL.md](capture-learning/SKILL.md).

Run `.venv/bin/python .claude/skills/capture-learning/capture.py` from the repository root. Learning is saved to the shared `pocket-fde/second-brain/pending/` folder and excluded from live search until human review. The script also supports `--list`, `--review DRAFT_NAME.md --by YOUR_NAME`, and `--reject`.
