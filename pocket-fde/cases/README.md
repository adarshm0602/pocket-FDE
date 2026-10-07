# Incident fixtures

The browser catalog loads `CASE-*.json` files in this directory and `heldout/`. It normalizes the original and imported formats into incident facts. Historical cases and gate answers support the optional core evaluation workflow; they are not copied wholesale into model requests.

## Browser incident fields

A new case can use this normalized format:

```json
{
  "id": "CASE-NEW",
  "title": "Embedded widget returns empty answers",
  "description": "The widget fails on simple questions while the main chat works.",
  "version": "v2",
  "customer_tier": "standard",
  "provided_evidence": ["g.retrieval shows zero returned chunks"]
}
```

Use a unique case ID and v1, v2 or v3 when established. `version: null` preserves unknown scope: source inspection is available, but a person must confirm the version before analysis. Customer tier is `standard` or `enterprise`.

For original imported files, `case_number` maps to `id` and `evidence.logs` maps to supplied evidence. The catalog also exposes recorded instance/configuration observations and validated findings. Hidden `ground_truth`, scenario causes and resolution fields remain offline. Editing a case in the UI submits that investigation's edited facts; it does not rewrite the fixture.

## Current catalog

- CASE-001–003: three original demonstration incidents.
- CASE-S45G7 and CASE-573544: imported incident replays, with original IDs and version uncertainty preserved.
- CASE-101–108: eight synthetic development cases with hidden reference answers.

Resolved-case replays may retrieve existing historical learning. The development cases have been used for refinement and must not be presented as unseen real-world validation.

`build_cases.py`, `history/` and `gate_answers/` preserve the simulator-backed core fixtures. Do not regenerate them during normal application setup: running the generator rewrites fixture data. To investigate without changing repository files, use the application's custom-issue form.
