---
name: analyze
description: Answer Pocket FDE platform, flag, log, ownership and version questions from project sources, or investigate an incident.
---

# Analyze

Use this skill for incident triage, feature availability, flag defaults, log availability, ownership, errors and version differences.

- Identify the question and establish the relevant platform version. Ask for missing context rather than guessing.
- Check actual definitions in `pocket-fde/world/`, relevant sections of `pocket-fde/docs/customer/`, and approved cards/notes under `pocket-fde/second-brain/`. Cite the exact supporting file or source ID.
- Treat pending/rejected learning and hidden case ground truth as unavailable for answering. A historical match does not establish a new cause.
- For an incident, follow `/analyze-case`: compare mechanisms, ask diagnostic questions, give a conditional owner/fix and a handover, and acknowledge uncertainty.
- A log request means explain the known stream, version, production availability and documented enablement risk. This skill has no access to a real company's dashboards and must not claim to have fetched production logs.
- Do not copy tenant identifiers, credentials or raw sensitive logs to an external model. Prefer redacted relevant evidence and preserve internal/customer-safe distinctions.
- Do not execute a fix, send a customer update, approve a learning or close a case without the appropriate human instruction.

Paths are relative to the Git repository root. Open the repository root or `pocket-fde/`; both expose the same skill definitions.

`analyzer.py` is Surya's restored early intent/answer-template prototype. It is explicitly marked as a prototype and does not perform the deployed app's model reasoning or verify its example answers. Use source-based investigation above or the live web application for current behavior.
