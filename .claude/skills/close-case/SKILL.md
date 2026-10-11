---
name: close-case
description: Close a Pocket FDE case from answers drafted from its evidence, shown to the human for approval before anything is written.
---

# Close Case (Approve-then-Apply)

Closes a case without typing every answer in the terminal. The human still reviews every answer: nothing is written until they approve the draft.

## Steps

0. **Identify the case from this chat.** Start from the conversation, not from the human retyping the ID.
   - Scan the chat for case IDs that were investigated or created with `/analyze-case` (or referenced in `/analyze`).
   - **None found:** ask for the case ID, then continue.
   - **One found:** state it ("Closing CASE-ID, correct?") and continue once the human confirms.
   - **Several found:** stop and ask which case to close, using AskUserQuestion with one option per case plus "none". Close one case at a time. Never combine evidence, answers or fixes from different cases in one draft, and keep each draft in its own scratchpad file, named `<CASE-ID>-answers.json`.

1. **Load the case.** Read `pocket-fde/cases/<CASE-ID>.json` and, if it exists, `pocket-fde/cases/gate_answers/<CASE-ID>.json`. Also read `pocket-fde/cases/history/<CASE-ID>.json` if present.
   - **Closed but still in `cases/`** (`status` is RESOLVED and the file is in `cases/`): do not re-draft. Go to the **Archive path** below.
   - **Already in `cases/history/` and not in `cases/`:** it is closed and archived. Tell the human and stop. Nothing to do.
   - **Not closed** (no RESOLVED status): follow steps 2 to 5. The close moves the case into `cases/history/`.
   - **File missing:** stop. Tell the human the case has no file and offer to create it with the `/analyze-case` template. Create it only after they agree.

   **Archive path** (closed case still in `cases/`):
   1. Dry run: `python3 .claude/skills/close-case/apply.py <CASE-ID> --archive` from the repository root. Show its output.
   2. Ask the human with AskUserQuestion to move it into `cases/history/`. Do not continue without a yes.
   3. Run the same command with `--confirm`. It merges the case into `cases/history/<CASE-ID>.json` and removes `cases/<CASE-ID>.json`.

2. **Draft the answers from the chat and the case file.** Use the conclusions reached in this conversation, cross-checked against the case file's `evidence.supplied` and `investigation` fields. Write an answers file to the scratchpad directory using only what the chat and evidence support. Fields:
   - `root_cause`, `owning_team`, `symptoms`, `detection_method`, `logs_to_check`
   - `fix`: `{"type", "details", "affected_versions", "fixed_in"}`. `type` is one of: Config change, Code fix, Parameter tuning, Workaround, Upgrade.
   - `ruled_out`, `pattern`, `confidence` (High, Medium or Low)
   - `novel_pattern` (true or false) and `ai_assisted` (true or false)

   If the evidence does not support a value, write `"not established"` and say so in the draft. Do not guess `fixed_in` or `affected_versions`.

3. **Get approval.** Show the draft to the human, field by field, and ask with AskUserQuestion: approve as written, or edit. Apply their edits. Do not continue without an explicit approval.

4. **Dry run.** Run `python3 .claude/skills/close-case/apply.py <CASE-ID> <answers-file>` from the repository root. Show its output.

5. **Apply.** Only after approval in step 3, run the same command with `--confirm`. It marks the case RESOLVED, writes the full record to `pocket-fde/cases/history/<CASE-ID>.json`, and removes `pocket-fde/cases/<CASE-ID>.json`, so closed cases live only in history. If `novel_pattern` is true, it also writes a learnings card and a `MEMORY.md` line. It never overwrites an existing card.

## Rules

- Never pass `--confirm` before the human has approved the draft.
- Ask about `novel_pattern` explicitly. Before answering yes, check `second-brain/cards/` and `MEMORY.md` for an existing card on the same case.
- **Existing card that covers the case:** if the human wants the case referenced from an existing card (for example, CARD-007), add `related_cases: [<CASE-ID>]` to that card after they approve. Do not create a learning card for a pattern that is not novel.
- Ask clarifying questions in the same AskUserQuestion round where possible, rather than writing "not established" for a value the human can answer.
- The script must run from the repository root; it refuses to run elsewhere.
