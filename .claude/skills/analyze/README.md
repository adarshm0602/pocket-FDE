# Analyze editor skill

The [skill instructions](SKILL.md) describe evidence-based platform questions and incident investigation using the project's real definitions and reviewed knowledge.

The restored `analyzer.py` preserves the original intent-classification prototype. Its handlers return example templates, not verified model answers. Returned results carry `prototype: true`; their confidence and example diagnoses are not accuracy measurements. It does not access live production logs.

The current web reasoning flow lives in `pocket-fde/pocketfd/triage.py` with `web/app.py` validation, `web/provider.py` model connections and selectable Keyword/Hybrid retrieval. Do not substitute prototype output for that pipeline in evaluation or a live demo.
