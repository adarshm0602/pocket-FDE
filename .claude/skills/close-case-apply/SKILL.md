---
name: close-case-apply
description: Close a Pocket FDE case from answers drafted from its evidence, shown to the human for approval before anything is written. Reuses the close-case writers.
---

# Close Case (Approve-then-Apply)

Closes a case without typing every answer in the terminal. The human still reviews every answer: nothing is written until they approve the draft.

## Steps

1. **Load the case.** Read `pocket-fde/cases/<CASE-ID>.json` and, if it exists, `pocket-fde/cases/gate_answers/<CASE-ID>.json`. Also read `pocket-fde/cases/history/<CASE-ID>.json` if present, and warn the human if the case is already closed.

2. **Draft the answers.** Write an answers file to the scratchpad directory using only what the case evidence supports. Fields:
   - `root_cause`, `owning_team`, `symptoms`, `detection_method`, `logs_to_check`
   - `fix`: `{"type", "details", "affected_versions", "fixed_in"}`. `type` is one of: Config change, Code fix, Parameter tuning, Workaround, Upgrade.
   - `ruled_out`, `pattern`, `confidence` (High, Medium or Low)
   - `novel_pattern` (true or false) and `ai_assisted` (true or false)

   If the evidence does not support a value, write `"not established"` and say so in the draft. Do not guess `fixed_in` or `affected_versions`.

3. **Get approval.** Show the draft to the human, field by field, and ask with AskUserQuestion: approve as written, or edit. Apply their edits. Do not continue without an explicit approval.

4. **Dry run.** Run `python3 .claude/skills/close-case-apply/apply.py <CASE-ID> <answers-file>` from the repository root. Show its output.

5. **Apply.** Only after approval in step 3, run the same command with `--confirm`. It writes the case file, the history file, and, if `novel_pattern` is true, a learnings card and a `MEMORY.md` line. It never overwrites an existing card.

## Rules

- Never pass `--confirm` before the human has approved the draft.
- Ask about `novel_pattern` explicitly. Before answering yes, check `second-brain/cards/` and `MEMORY.md` for an existing card on the same case.
- The script must run from the repository root; it refuses to run elsewhere.
