---
name: feedback_identical_config_divergent_code
description: "When instances have identical config but different behavior, check deployed code"
source_case: CASE-S45G7
reported_version: v2
version_scope: "Diagnostic lesson from a v2 incident; verify version-specific implementation before applying a fix."
metadata:
  node_type: memory
  type: feedback
  learned_from: CASE-S45G7
  date: 2026-10-06
  originSessionId: 789b75a0-c513-4332-b6c3-a2ef97480353
  modified: 2026-10-06T16:10:12.213Z
---

## Rule
When two instances have identical configuration but different behavior, the root cause is often **instance-level code customization**, not config drift or environment variables.

**Why:** Config audits and environment variable checks are common troubleshooting paths, but they miss code-level divergence. In CASE-S45G7, both instances had the same `fine_tune_plugin_version` and config files, but inst567 had a customized `prepare()` method that broke plugin initialization.

**How to apply:**
1. After validating network connectivity ✓ and environment variables ✓
2. **Compare deployed code** (not just config) across instances
   - For Python plugins: check if methods are overridden or patched
   - For binary services: verify checksums/MD5 match
   - For containerized: ensure image SHAs are identical
3. Check git history or deployment logs: was there a one-off patch deployed to only one instance?

**Failure scenario:** Identical config, network verified, but plugin fails on inst567 while working on inst234 → likely instance-level code override that doesn't appear in config files.

**Success path:** Revert customized method to OOB version → plugin works again.
