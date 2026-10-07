# Retained web verification evidence

These records document observed development and release behavior. They are not independent real-world evaluations. Keep model identity, corpus revision, errors and incomplete requests when interpreting a result.

| Record | Purpose |
|---|---|
| [Automatic learning release](automatic-learning-release-20261007.json) | Current Second Brain release: 17 hosted checks, live CASE-101, isolated cloud review and public/mobile verification |
| [Full Flash selected-case check](full-flash-release-check-20261007.json) | Four selected development cases in both modes: six completed correct owner routes and two incomplete requests |
| [CASE-104 recheck](full-flash-case104-recheck-20261007.json) | Provider quota exhaustion during a subsequent check |
| [Earlier hosted final check](final-deployment-check-20261007.json) | Earlier Keyword CASE-104, disclosed Lite fallback, private saving and reload |
| [Diagnostic variant fixture](diagnostic-variants.json) | Offline inputs and expected outcomes required by `web.evaluate_variants`; excluded from retrieval and model input answers |

The [project report](../../../PROJECT_REPORT.md#6-validation-and-evidence) and [release verification](../../../submission/release-verification.md) explain the scope and limitations. Intermediate prompt/debug runs were removed during the approved cleanup. The original core evaluation tools and final historical results remain under `pocket-fde/eval/`; they measure a different workflow and release.

## Reproduce a development check

From the repository root, start the local app and privately connect a provider. These commands make billable model requests; record failures rather than silently dropping them:

```sh
.venv/bin/python pocket-fde/web/evaluate_baseline.py --retrieval surya
.venv/bin/python pocket-fde/web/evaluate_baseline.py --retrieval hybrid
PYTHONPATH=pocket-fde .venv/bin/python -m web.evaluate_variants --output /tmp/pocket-fde-variants.json --repeats 2
```

Baseline output uses date-named directories, ignored by Git. Deliberately retain reviewed evidence when needed; generated prompt logs and private data do not belong in the shared repository. Keep the model and corpus fixed for a comparison. No general Hybrid advantage, diagnostic accuracy estimate or collaboration benefit follows from the selected release checks.
