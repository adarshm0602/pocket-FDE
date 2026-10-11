# Close Case Skill

**AI-Assisted, Human-Reviewed Case Closure**

Capture conscious, well-reviewed learnings when closing a case. The skill shows AI suggestions (MCQ) and lets you confirm or override each one.

## Usage

```bash
# Close a specific case
/close-case CASE-001

# Close a case (will prompt for case ID)
/close-case
```

## Workflow

1. **Run `/close-case CASE-001`**
2. **Skill loads:**
   - Case metadata from `cases/CASE-001.json`
   - AI analysis from `cases/gate_answers/CASE-001.json`
3. **For each field, you see:**
   - 💡 AI suggestion
   - ✅ Accept it / ❌ Override it
4. **Save conscious, human-reviewed learnings**

## What It Reviews

The skill shows AI suggestions for each field and asks you to review:

1. **Root Cause** — What actually caused the issue? (specific, not vague)
2. **Owning Team** — Which team owns this root cause?
3. **Symptoms** — What did customers report?
4. **Detection** — How to detect this in the future? (mentions log streams)
5. **Fix Applied** — Config change? Code fix? Parameter tuning?
6. **Ruled Out** — What didn't cause the issue? (prevents rabbit holes)
7. **Versions** — Which versions affected? Fixed in which version?
8. **Pattern** — What pattern does this belong to?
9. **Confidence** — High/Medium/Low
10. **Systemic** — One-time or recurring issue?

## Output

Saves structured resolution to:
- `pocket-fde/cases/history/{CASE-ID}.json` — Resolution details
- Updates case metadata with confidence/status
- Creates learnings for future reference

## Example

```
/close-case CASE-001

Case: CASE-001 - One-Way UI returning empty answers
Customer: Acme Logistics
Version: v2

Root Cause: tune.rewrite_mode=history_aware without session_id causes empty query
Owning Team: Team B (Tune/Config)

Symptoms: "not enough information" in One-Way widget, Chat UI works fine
Detection: Compare Interactive vs One-Way; check g.rewrite had_session=false

Fix: Set tenant override tune.rewrite_mode=single_shot
Fixed In: v2 (via config), v3 (default changed)

Ruled Out: One-Way UI bug, LLM issue, retrieval failure

Pattern: Config-driven behavior difference between UI modes
Confidence: High
Issue Type: Systemic (affects other tenants with same config)
```

## Benefits

**Before:** Case closed, details fade, next analyst hits same issue again  
**After:** Structured learning captured, next analyst finds exact root cause + detection method + log streams to check

## Integration

Works with other skills:
- `/analyze` → `/close-case` workflow
- Learnings feed into `/second-brain` for pattern recognition
- Prevents duplicate cases from happening
