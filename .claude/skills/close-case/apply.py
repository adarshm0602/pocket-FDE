#!/usr/bin/env python3
"""Apply a reviewed close-case answers file. Run from the repository root.

Usage:
    python3 .claude/skills/close-case/apply.py CASE-ID ANSWERS.json
    python3 .claude/skills/close-case/apply.py CASE-ID ANSWERS.json --confirm
    python3 .claude/skills/close-case/apply.py CASE-ID --archive
    python3 .claude/skills/close-case/apply.py CASE-ID --archive --confirm

Closing a case writes its full record to cases/history/ and removes it from cases/.
--archive moves a case that is already RESOLVED (but still in cases/) into history
without re-drafting its answers. Without --confirm nothing is written.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

REQUIRED = [
    "root_cause", "owning_team", "symptoms", "detection_method", "logs_to_check",
    "fix", "ruled_out", "pattern", "confidence",
]
FIX_KEYS = ["type", "details", "affected_versions", "fixed_in"]
CONFIDENCE = {"High", "Medium", "Low"}


def load_case(case_id):
    """Load the case file, or exit if it is missing"""
    case_path = Path(f"pocket-fde/cases/{case_id}.json")
    if not case_path.exists():
        sys.exit(f"Case {case_id} not found at {case_path}")
    return json.loads(case_path.read_text())


def build_resolution(case_id, answers):
    missing = [k for k in REQUIRED if k not in answers]
    if missing:
        sys.exit(f"Answers file is missing: {', '.join(missing)}")
    fix = answers["fix"]
    if not isinstance(fix, dict) or any(k not in fix for k in FIX_KEYS):
        sys.exit(f"'fix' must contain: {', '.join(FIX_KEYS)}")
    if answers["confidence"] not in CONFIDENCE:
        sys.exit("'confidence' must be High, Medium or Low")

    return {
        "case_number": case_id,
        "closed_at": datetime.now().isoformat(),
        "root_cause": answers["root_cause"],
        "owning_team": answers["owning_team"],
        "symptoms": answers["symptoms"],
        "detection_method": answers["detection_method"],
        "logs_to_check": answers["logs_to_check"],
        "fix": {k: fix[k] for k in FIX_KEYS},
        "ruled_out": answers["ruled_out"],
        "pattern": answers["pattern"],
        "confidence": answers["confidence"],
        "reviewed_by": "human",
        "ai_assisted": bool(answers.get("ai_assisted", False)),
    }


def archive_case(case):
    """Move a closed case into cases/history/. The full record goes to history and the cases/ copy is removed."""
    history_dir = Path("pocket-fde/cases/history")
    history_dir.mkdir(parents=True, exist_ok=True)

    history_file = history_dir / f"{case['case_number']}.json"
    record = json.loads(history_file.read_text()) if history_file.exists() else {}
    record.update(case)
    record["last_updated"] = datetime.now().isoformat()
    history_file.write_text(json.dumps(record, indent=2))

    Path(f"pocket-fde/cases/{case['case_number']}.json").unlink()
    return history_file


def mark_resolved(case, resolution):
    """Attach the reviewed resolution and mark the case RESOLVED"""
    case.update({
        "status": "RESOLVED",
        "closed_at": resolution["closed_at"],
        "resolution": resolution,
    })
    return case


def archive_closed_case(case_id, confirm):
    """Archive a case that is already RESOLVED but still sits in cases/. No answers are needed."""
    case_path = Path(f"pocket-fde/cases/{case_id}.json")
    if not case_path.exists():
        sys.exit(f"{case_id} is not in pocket-fde/cases/. Nothing to archive.")
    case = json.loads(case_path.read_text())
    if case.get("status") != "RESOLVED" or "resolution" not in case:
        sys.exit(f"{case_id} is not closed (status: {case.get('status', 'none')}). Use the normal close flow with an answers file.")

    print(f"Would move pocket-fde/cases/{case_id}.json to pocket-fde/cases/history/{case_id}.json")
    print(f"Resolution closed_at: {case['resolution'].get('closed_at', 'unknown')}")
    if not confirm:
        print("\nDry run only. Nothing was written. Re-run with --confirm to move it.")
        return

    archive_case(case)
    print(f"\nARCHIVED. Written: pocket-fde/cases/history/{case_id}.json (removed from pocket-fde/cases/)")


def write_learnings_card(case, resolution):
    """Write a learnings card to second-brain/cards/. Never overwrites an existing card."""
    card_name = f"{case['case_number'].lower().replace('-', '_')}_resolution"
    card_path = Path(f"pocket-fde/second-brain/cards/{card_name}.md")

    if card_path.exists():
        print(f"Card already exists, not overwriting: {card_path}")
        return None

    fix = resolution["fix"]
    scope = fix["affected_versions"] or "not established"
    description = f"{case['case_number']} resolved: {resolution['root_cause']}"
    version_scope = f"Affected versions: {scope}. Fixed in: {fix['fixed_in'] or 'not established'}."

    body = f"""---
name: {card_name}
description: {json.dumps(description)}
source_case: {case['case_number']}
reported_version: {case.get('version', 'unknown')}
version_scope: {json.dumps(version_scope)}
metadata:
  node_type: memory
  type: project
  case_number: {case['case_number']}
  updated: {resolution['closed_at']}
---

## {case['case_number']}: {case.get('title', '')}

### Root Cause
{resolution['root_cause']}

### Symptoms
{resolution['symptoms']}

### Detection
{resolution['detection_method']}

### Logs to Check
{resolution['logs_to_check']}

### Fix ({fix['type']})
{fix['details']}

### Ruled Out
{resolution['ruled_out']}

### Pattern
{resolution['pattern']}

Confidence: {resolution['confidence']}
"""

    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(body)
    return card_path


def add_memory_entry(card_path, case, resolution):
    """Append a pointer to the new card in the shared MEMORY.md index"""
    memory_path = Path("pocket-fde/MEMORY.md")
    relative = card_path.relative_to("pocket-fde").as_posix()
    hook = resolution["root_cause"].replace("\n", " ")
    line = f"- [{case['case_number']} resolution]({relative}) — {hook}\n"

    existing = memory_path.read_text() if memory_path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    memory_path.write_text(existing + line)


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    case_id, second = argv[1], argv[2]
    confirm = "--confirm" in argv[2:]

    if not Path("pocket-fde/cases").is_dir():
        sys.exit("Run this from the repository root (the folder that contains pocket-fde/).")

    if second == "--archive":
        archive_closed_case(case_id, confirm)
        return

    case = load_case(case_id)
    answers = json.loads(Path(second).read_text())
    resolution = build_resolution(case_id, answers)
    novel = bool(answers.get("novel_pattern", False))

    print(json.dumps(resolution, indent=2))
    print(f"\nNovel pattern (learnings card + MEMORY.md): {novel}")

    if not confirm:
        print("\nDry run only. Nothing was written. Re-run with --confirm after review.")
        return

    case = mark_resolved(case, resolution)
    history_file = archive_case(case)
    written = [str(history_file), f"pocket-fde/cases/{case_id}.json (removed)"]

    if novel:
        card_path = write_learnings_card(case, resolution)
        if card_path:
            add_memory_entry(card_path, case, resolution)
            written += [str(card_path), "pocket-fde/MEMORY.md"]

    print("\nCASE CLOSED AND ARCHIVED. Written:")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main(sys.argv)
