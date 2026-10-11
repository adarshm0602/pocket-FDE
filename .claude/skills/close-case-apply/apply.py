#!/usr/bin/env python3
"""Apply a reviewed close-case answers file. Run from the repository root.

Usage:
    python3 .claude/skills/close-case-apply/apply.py CASE-ID ANSWERS.json
    python3 .claude/skills/close-case-apply/apply.py CASE-ID ANSWERS.json --confirm

Without --confirm it only prints the resolution that would be written.
"""

import importlib.util
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


def load_close_case():
    """Import the existing close-case module so both skills share one set of writers"""
    path = Path(__file__).resolve().parent.parent / "close-case" / "__init__.py"
    spec = importlib.util.spec_from_file_location("close_case", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    case_id, answers_path = argv[1], argv[2]
    confirm = "--confirm" in argv[3:]

    if not Path("pocket-fde/cases").is_dir():
        sys.exit("Run this from the repository root (the folder that contains pocket-fde/).")

    cc = load_close_case()
    case = cc.load_case(case_id)
    if not case:
        sys.exit(1)

    answers = json.loads(Path(answers_path).read_text())
    resolution = build_resolution(case_id, answers)
    novel = bool(answers.get("novel_pattern", False))

    print(json.dumps(resolution, indent=2))
    print(f"\nNovel pattern (learnings card + MEMORY.md): {novel}")

    if not confirm:
        print("\nDry run only. Nothing was written. Re-run with --confirm after review.")
        return

    cc.save_case_resolution(case, resolution)
    cc.update_case_status(case, resolution)
    written = [
        f"pocket-fde/cases/history/{case_id}.json",
        f"pocket-fde/cases/{case_id}.json",
    ]

    if novel:
        card_path = cc.write_learnings_card(case, resolution)
        if card_path:
            cc.add_memory_entry(card_path, case, resolution)
            written += [str(card_path), "pocket-fde/MEMORY.md"]

    print("\nCASE CLOSED. Written:")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main(sys.argv)
