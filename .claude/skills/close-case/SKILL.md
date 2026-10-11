---
name: close-case
description: Capture structured learnings when closing a case to prevent vague resolutions
---

# Close Case: Capture Resolution Learnings

**Prevent case analysis from becoming vague by capturing structured learnings when resolving.**

## Quick Start

```bash
/close-case [CASE-ID]
```

Or without an ID, the skill will ask which case you're closing.

---

## How It Works: AI-Assisted MCQ Review

**The skill does NOT ask you to type answers from scratch.** Instead, it:

1. **Loads the case** from `cases/{CASE-ID}.json`
2. **Fetches AI analysis** from `cases/gate_answers/{CASE-ID}.json`
3. **For each field, shows:** 
   - 💡 AI's suggestion (from the analysis)
   - MCQ options:
     - ✅ **Accept AI suggestion** → Move on
     - ❌ **Provide custom answer** → Type your own
4. **Saves human-reviewed learnings** (marked as AI-assisted but human-conscious)

This keeps the knowledge **conscious and well-reviewed**, not just AI-generated.

---

## What It Captures

When you close a case, you review and confirm/override:

1. **Case Identification**
   - Case number (CASE-001, CASE-573544, etc.)
   - Case title (what was the symptom?)

2. **Root Cause Analysis**
   - What was the actual root cause?
   - Was it config, code, or infrastructure?
   - Which team owns the root cause?

3. **Symptoms & Detection**
   - What were the symptoms customers reported?
   - How would someone detect this issue in the future?
   - Which log streams showed the problem?

4. **Resolution & Fix**
   - What was the fix applied?
   - Was it a config change, code fix, or parameter tuning?
   - Any workarounds that should be documented?

5. **What Was Ruled Out**
   - What did you investigate but rule out?
   - Prevents future investigators from wasting time on dead ends

6. **Version Context**
   - Which versions were affected? (v1, v2, v3, all)
   - Was this fixed in a later version?
   - Version-specific workarounds?

7. **Learnings & Patterns**
   - What pattern does this belong to?
   - Similar cases? (e.g., "similar to CASE-001 but different layer")
   - One-time incident or systemic issue?

---

## Example: Closing CASE-001

```
/close-case CASE-001
```

**Skill prompts:**
```
Case: CASE-001 - One-Way UI returning empty answers
Customer: Acme Logistics (tenant t-umbrella)
Status: RESOLVED

Root Cause: tune.rewrite.mode=history_aware without session_id causes empty query rewrite
Owning Team: Team B (Tune/Config layer)

Symptoms: "not enough information" error in One-Way widget, but Chat UI works fine
Detection: Compare Interactive vs One-Way for same tenant; check g.rewrite had_session=false

Fix Applied: Set tenant override tune.rewrite.mode=single_shot
Fixed In: v2 (via config), v3 (default changed)

Ruled Out: 
- One-Way UI rendering bug
- LLM gateway issue
- Retrieval service failure

Pattern: Config-driven behavior difference between UI modes
Similar: Cases where v2 defaults don't fit all use cases
```

**Output:**
- Updates `cases/CASE-001.json` with resolution
- Creates `cases/history/CASE-001.json` with learned patterns
- Adds to `second-brain/cards/` for future reference
- Updates `MEMORY.md` if novel pattern discovered

---

## Output Files

Each closed case creates/updates:

1. **Case metadata** — `cases/CASE-001.json`
   - Updated with resolution status
   - Confidence level (high/medium/low)

2. **Case history** — `cases/history/CASE-001.json`
   - Diagnostic questions asked
   - Bounces between teams
   - Resolution quality (precise/vague)
   - Pattern tags

3. **Learnings card** — `second-brain/cards/` (if novel pattern)
   - Title: descriptive pattern name
   - Root cause pattern
   - Detection method
   - Similar cases (cross-references)

4. **Memory index** — Updated `MEMORY.md`
   - If learning applies to future cases

---

## Why This Matters

**Before:** "Case resolved, moved on. Details fade. Next analyst hits same issue."

**After:** "Case resolved with structured learnings. Next analyst finds:
- Exact root cause
- How to detect it
- Why other things don't matter
- Similar patterns to watch for
- Better diagnosis speed"

---

## When to Use

✅ After resolving a case  
✅ Before closing a ticket  
✅ Before handing off to another team  
✅ When the case resolution is non-obvious  
✅ When multiple teams were involved (capture handoff context)

❌ Don't use for open investigations (use `/analyze` instead)

---

## Tips

- **Be specific:** "Config misalignment" is vague; "tune.rewrite_mode default doesn't fit One-Way UI" is precise
- **Always rule out:** Preventing future rabbit holes saves time
- **Link patterns:** Similar to CASE-X helps analyzers see patterns
- **Quality matters:** Precise case learnings accelerate team onboarding

---

## Related Skills

- `/analyze` — Diagnose open cases
- `/analyze-case` — Quick case triage
- `/capture-learning` — Save arbitrary insights
- `/close-case` — This skill (save resolutions)

**Workflow:** Analyze → Triage → Resolve → Close Case → Learnings saved for future

