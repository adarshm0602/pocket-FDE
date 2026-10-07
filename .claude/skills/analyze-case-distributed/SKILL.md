---
name: analyze-case-distributed
description: Inspect configured local case, approved knowledge, documentation and code sources before evidence-based incident investigation.
---

# Analyze Case with Distributed Sources

This restored skill provides local source configuration and inspection. MCP and web connectors remain unimplemented; onboarding them records a proposed endpoint, not a working integration. Portability to another platform has not been validated.

## Setup and inspect

Run these commands from the Git repository root:

```sh
.venv/bin/python .claude/skills/analyze-case-distributed/onboard.py
.venv/bin/python .claude/skills/analyze-case-distributed/orchestrator.py CASE-101
```

Onboarding writes `.config/pipeline.yaml` beside its script. The bundled configuration reads `pocket-fde/cases`, `second-brain`, `docs/customer` and `repos`. Relative source paths resolve against the application directory `pocket-fde/`, regardless of the terminal's current folder; absolute paths are accepted for explicitly configured local sources.

Sequential inspection follows configured source order. Parallel inspection runs source reads concurrently and records independent failures. The helper returns context inventories, not an LLM diagnosis or guaranteed relevance ranking. It exposes a sample of up to five approved cards/notes and documentation filenames; it does not search a production service. Hidden case `ground_truth` is excluded, and pending/rejected knowledge is excluded.

## Investigation

Use the returned sources with `/analyze-case` or `/analyze`. Verify actual file contents, ownership, version defaults and evidence availability; cite sources and distinguish hypotheses from confirmed facts. Do not infer a diagnosis from successful file reads or source counts. Do not use hidden evaluation answers, unrelated secrets, pending learning, or raw customer identifiers as reasoning context.

For the current measured model-backed triage, use the web application's Keyword or Hybrid Search. Its runtime and provider configuration are separate from this inventory helper.
