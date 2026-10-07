> Historical synthetic CLI run; not current hosted web performance. See [interpretation](../interpretation.md). Generated outbound prompt logs were removed during repository cleanup; retained aggregate results record the original observations.

# Evaluation summary: Pocket FD vs baseline (synthetic world, 8 held-out cases)

> **Read this first.** The platform, teams, cases and logs are synthetic. This shows the mechanism works on a controlled simulation, not that it will work on real, messy enterprise cases. n = 8 cases, one run each, one model; differences of one case are within noise. Scoring is automatic (ID/string matching against hidden ground truth) except where marked *LLM-judge*.

Conditions: **Baseline** = frontier model, raw case text, no retrieval, free-form handover (knows team names only). **Ablation** = Pocket FD pipeline over the *raw vague history notes* instead of gate-produced cards. **Pocket FD** = gate cards + hybrid retrieval + redaction + handover template + budget guard.

| Metric | Baseline | Ablation (no gate) | Pocket FD |
|---|---|---|---|
| 1. Routing accuracy (correct owner first; escalation counts for the 'insufficient evidence' case) | 1/8 | 4/8 | 6/8 |
| 2. Simulated bounces (wrong-team hops, lower is better) | 12 | 5 | 2 |
| 3a. Cases where all key questions were asked in ONE round | 2/8 | 3/8 | 5/8 |
| 3b. Avg rounds to cover all key questions (4 = not within 3) | 2.75 | 2.88 | 2.0 |
| 4a. Key-question topics covered in round 1 | 16/24 | 18/24 | 19/24 |
| 4b. Needed evidence correctly requested in round 1 (valid for the version) | 1/25 | 24/25 | 19/25 |
| 5. Invented flags/logs (hallucinations, after any repair/validator) | 24 | 0 | 0 |
| 6. Version-correct (no flag invalid for the customer's version) | 0/8 | 8/8 | 8/8 |
| *LLM-judge*: top hypothesis matches true root cause (yes / partial) | 1 / 7 | 4 / 2 | 6 / 0 |
| 7a. Tokens per case (round 1) | 5534 | 8902 | 9198 |
| 7b. Steps per case (round 1) | 1.0 | 2.0 | 2.0 |
| 7c. Escalations (of which budget-guard) | 0 (0) | 8 (0) | 3 (1) |

**8. Privacy (from the outbound logs):** Pocket FD made 34 external calls with **0 raw identifiers** found in them (`outbound_log.jsonl`); the baseline made 18 calls with **49 raw identifiers** (customer names, emails, IPs) sent as-is (`outbound_baseline.jsonl`). Redaction is regex + a customer list; free-text person names are not detected.

## Per case

| Case | True owner | Baseline owner (esc) | Ablation (no gate) owner (esc) | Pocket FD owner (esc) | bounces base/abla/pock | topics r1 base/abla/pock |
|---|---|---|---|---|---|---|
| CASE-101 | B | U ✗ (no) | B ✓ (esc) | B ✓ (no) | 2/0/0 | 1/3/1/3/2/3 |
| CASE-102 | B | B ✓ (no) | G ✗ (esc) | None ✗ (esc) | 0/1/2 | 1/3/2/3/0/3 |
| CASE-103 | PLATFORM | Q ✗ (no) | Q ✗ (esc) | PLATFORM ✓ (no) | 2/2/0 | 2/3/2/3/2/3 |
| CASE-104 | G | V ✗ (no) | G ✓ (esc) | G ✓ (no) | 2/0/0 | 3/3/3/3/3/3 |
| CASE-105 | Q | U ✗ (no) | Q ✓ (esc) | Q ✓ (no) | 2/0/0 | 2/3/3/3/3/3 |
| CASE-106 | E | B ✗ (no) | E ✓ (esc) | E ✓ (esc) | 2/0/0 | 2/3/3/3/3/3 |
| CASE-107 | G | B ✗ (no) | B ✗ (esc) | G ✓ (no) | 2/2/0 | 3/3/2/3/3/3 |
| CASE-108 | B (escalate) | B ✗ (no) | E ✗ (esc) | E ✗ (esc) | 0/0/0 | 2/3/2/3/3/3 |

## Where Pocket FD did NOT win (auto-detected)

- CASE-102: baseline routed correctly (B) but Pocket FD did not (None).
- CASE-102: baseline covered more key-question topics in round 1 (1 vs 0).
- CASE-102: ablation covered more key-question topics in round 1 (2 vs 0).
- CASE-102: ablation requested more needed evidence (4 vs 0).
- CASE-104: ablation requested more needed evidence (4 vs 3).
