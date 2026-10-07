---
name: onboard
description: Configure local case, knowledge, documentation and code locations for the restored distributed-source workflow.
---

# Configure Local Sources

Find the Git repository root. Inspect the existing `.claude/skills/analyze-case-distributed/.config/pipeline.yaml` before replacing it.

Ask the human for source locations and whether they want sequential or concurrent local reads. Default relative paths refer to the application folder `pocket-fde/`. Never populate the config with credentials or infer access to external services.

The human can run this interactive command from the repository root:

```sh
.venv/bin/python .claude/skills/analyze-case-distributed/onboard.py
```

MCP and web choices are proposed configuration only; their fetchers are not implemented. Explain that limitation before configuring them. Source-inventory configuration does not alter the deployed app's model, private storage or search indexes. Use `/analyze-case-distributed` to inspect the configured local sources afterward.
