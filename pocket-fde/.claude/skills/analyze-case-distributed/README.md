# Distributed-source editor workflow

See [SKILL.md](SKILL.md) for setup and scope. `onboard.py` captures local source choices; `orchestrator.py` reads case records, approved YAML/Markdown knowledge, customer-document filenames and a Python code inventory. Relative paths are anchored to `pocket-fde/`, not the terminal working directory.

MCP/web fetches return `not_implemented`. Timeout/cache settings in the original config are not implemented controls. The context sample is not ranked retrieval, and source inspection is not the Gemini triage pipeline. Do not claim confirmed diagnoses, production log access or general portability from this helper.

The same files are exposed under the repository's `.claude/skills/` and `pocket-fde/.claude/skills/`. Existing transcripts, iteration workspaces and debug runs are not required by these skills.
