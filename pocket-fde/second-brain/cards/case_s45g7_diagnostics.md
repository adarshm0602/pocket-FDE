---
name: case_s45g7_diagnostics
description: "CASE-S45G7 resolved: prepare() override broke plugin initialization; compare deployed code"
source_case: CASE-S45G7
reported_version: v2
version_scope: "Observed in a v2 incident; applicability to other versions has not been established."
metadata:
  node_type: memory
  type: project
  case_number: CASE-S45G7
  updated: 2026-10-06T15:45:00Z
  originSessionId: 789b75a0-c513-4332-b6c3-a2ef97480353
  modified: 2026-10-06T16:10:04.745Z
---

## CASE-S45G7: Fine-tune Plugin Instance Mismatch — ROOT CAUSE RESOLVED

### Root Cause
**prepare() method was customized/overridden in inst567**
- File: [team_e_finetune/service.py](../../repos/team_e_finetune/service.py)
- Method: `prepare(ctx, payload)`
- Issue: Instance-level code customization diverged from out-of-box (OOB) implementation
- Fix: Reverted to OOB version
- Result: ✅ Plugin initialized successfully, inference requests completed normally

### Why This Was Hard to Detect
- Both instances had **identical config files** (fine_tune_plugin_version, plugin_mode, backend_service_url)
- Validated that **network connectivity was not the issue**
- The divergence was at the **code level**, not the configuration level
- Standard config audits would miss instance-level code customizations

### Key Lesson
**Config parity is necessary but not sufficient.** When instances have identical config but different behavior:
1. Validate network connectivity ✓
2. Validate environment variables ✓
3. **Validate deployed code matches OOB** ← This was the missing check

For plugin-based systems, compare actual method implementations across instances, not just config.

**Related:** [[reference_codebases]] — team_e_finetune is the fine-tune plugin codebase
