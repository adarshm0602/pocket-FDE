---
name: compare-costs
description: Inspect estimated source-context size and measured evaluation usage without inventing model cost or token savings.
---

# Compare Costs

Read existing evaluation usage records and explain which model, cases, knowledge revision, retries/repairs and question rounds they cover. Separate measured tokens from source-size estimates. Synthetic development accuracy is not real-customer accuracy.

`pocket-fde/eval/code_context_cost.py` is an early what-if estimator based on roughly four characters per token and assumed triage/indexing costs. Its savings and breakeven figures are illustrative assumptions, not measured API usage or proof that indexing incurred LLM token charges. Do not present them as findings.

The fresh Gemini comparison used more first-analysis tokens for both application search modes than a plain-model no-retrieval baseline. That result does not measure a raw-code-exploration baseline. Never claim 2x savings, 100% accuracy or a fixed breakeven count without a matched, recorded evaluation.
