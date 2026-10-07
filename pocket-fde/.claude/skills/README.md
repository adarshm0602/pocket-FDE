# Pocket FDE editor skills

These are project deliverables alongside the live web workspace. Open the Git repository root or its `pocket-fde/` folder in an assistant-enabled editor. Standard `<name>/SKILL.md` directories make the instructions discoverable in both layouts.

| Skill | Purpose |
|---|---|
| [analyze](analyze/SKILL.md) | Platform, configuration, logs, ownership and version questions |
| [analyze-case](analyze-case/SKILL.md) | Evidence-based incident investigation by case ID |
| [analyze-case-distributed](analyze-case-distributed/SKILL.md) | Configured local source inspection before investigation |
| [onboard](onboard/SKILL.md) | Configure those local source locations |
| [triage-incident](triage-incident/SKILL.md) | New-incident triage instructions |
| [capture-solution](capture-solution/SKILL.md) | Structure a resolved incident for human review |
| [capture-learning](capture-learning/SKILL.md) | Canonical portable Markdown draft/review tool |
| [compare-costs](compare-costs/SKILL.md) | Interpret measured usage separately from estimates |

Surya's early helper implementations are retained with clear prototype labels. The case demo uses heuristic rules, the generic analyzer uses example templates, and distributed inspection is a local inventory helper; none is the evaluated Gemini web pipeline. There are no verified prototype accuracy, probability, latency or token-saving guarantees. MCP/web connectors remain planned.

The `capture-learning/capture.py` implementation is canonical at the outer repository root. Its pending-first workflow and explicit human approval are preserved. When the editor is opened inside `pocket-fde/`, follow the nested skill's link to that canonical tool and run its commands from the Git root.

Generated `.skill` bundles contain the analyze-case skill and its demonstration helpers. They are kept consistent with these source files. Live deployment code, knowledge fixtures and deployment configuration are not changed by restoring editor files.
