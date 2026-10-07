# Pocket FDE application and core

This directory contains the deployed Python application and the fictional platform used to develop and test it. Start with the repository [README](../README.md) and [project report](../PROJECT_REPORT.md).

## Components

| Directory | Purpose |
|---|---|
| `web/` | Browser workspace, FastAPI APIs, providers, Hybrid search and durable storage |
| `pocketfd/` | Core triage, keyword retrieval, grounding, redaction, learning, closure gate and handover helpers |
| `second-brain/` | Bundled reviewed knowledge cards and notes |
| `docs/customer/` | Searchable customer guides for the fictional platform |
| `world/` | Version, ownership, observability, tenant and configuration definitions |
| `repos/` | Python platform simulator and team services |
| `cases/` | Incident inputs, historical cases and offline development answers |
| `tests/`, `web/tests/` | Regression checks |
| `eval/`, `web/evaluation/` | Core evaluation tools and retained release evidence |

## Browser application

Use the root quick start, then open http://127.0.0.1:8000. See [the application guide](web/README.md) and [deployment guide](web/DEPLOYMENT.md).

The live web modes exclude unreviewed knowledge. Successful analyses automatically draft provisional web learning for human review. The browser workflow uses Gemini or another selected provider, measured usage and at most one repair; it does not invoke the removed prototype analyzers.

## Optional local core workflows

The core also contains a closure gate for turning vague resolved-case notes into structured cards, a curator, handover accept/reject helpers and an original CLI evaluation harness. These are development tools, not additional deployed screens or external ticket actions.

The canonical local Markdown capture/review tool is at [`.claude/skills/capture-learning/`](../.claude/skills/capture-learning/SKILL.md). It is separate from web learning stored in private Blob. Local notes need explicit human review; getting those files into another deployment requires a code release.

Original core retrieval can explicitly include labeled pending knowledge for development. The deployed web app always excludes pending and rejected learning. Historical CLI results must not be presented as current web performance.

Run the complete suite from the repository root:

```sh
.venv/bin/python -m pytest pocket-fde/tests pocket-fde/web/tests -q
```
