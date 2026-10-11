"""
Close Case Skill - Capture structured learnings with AI-assisted MCQ review
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def load_case(case_id):
    """Load case from JSON file"""
    case_path = Path(f"pocket-fde/cases/{case_id}.json")
    if not case_path.exists():
        print(f"❌ Case {case_id} not found at {case_path}")
        return None

    with open(case_path) as f:
        return json.load(f)


def load_gate_answers(case_id):
    """Load gate answers (AI analysis) from JSON file"""
    gate_path = Path(f"pocket-fde/cases/gate_answers/{case_id}.json")
    if not gate_path.exists():
        return None

    with open(gate_path) as f:
        return json.load(f)


def mcq_review(field_name, ai_suggestion):
    """
    MCQ-style review: show AI suggestion first, let user confirm or override

    Returns: (selected_value, is_custom)
    """
    print(f"\n{'='*60}")
    print(f"🤖 {field_name.upper()}")
    print(f"{'='*60}")

    options = ["✅ Accept AI suggestion", "❌ Provide custom answer"]

    if ai_suggestion:
        print(f"\n💡 AI Suggestion:\n   {ai_suggestion}\n")
    else:
        print(f"\n⚠️  No AI suggestion available. Enter your answer.\n")
        return input(f"{field_name}: ").strip(), True

    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")

    choice = input("\nChoose (1-2): ").strip()

    if choice == "1":
        return ai_suggestion, False
    elif choice == "2":
        custom = input(f"\nEnter your {field_name.lower()}: ").strip()
        return custom, True
    else:
        print("Invalid choice. Try again.")
        return mcq_review(field_name, ai_suggestion)


def mcq_review_with_options(field_name, ai_suggestion, all_options):
    """
    MCQ review where user can pick from predefined options or enter custom
    """
    print(f"\n{'='*60}")
    print(f"🤖 {field_name.upper()}")
    print(f"{'='*60}")

    if ai_suggestion:
        print(f"\n💡 AI Suggestion: {ai_suggestion}\n")
    else:
        print(f"\n⚠️  No AI suggestion available.\n")

    print("Options:")
    for i, opt in enumerate(all_options, 1):
        prefix = "✅" if ai_suggestion and opt == ai_suggestion else "  "
        print(f"  {i}. {prefix} {opt}")
    print(f"  {len(all_options) + 1}. 📝 Enter custom answer")

    choice = input("\nChoose option (1-N): ").strip()

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(all_options):
            is_custom = (ai_suggestion and idx != all_options.index(ai_suggestion)) or not ai_suggestion
            return all_options[idx], is_custom
        elif idx == len(all_options):
            custom = input(f"Enter your {field_name.lower()}: ").strip()
            return custom, True
    except (ValueError, IndexError):
        pass

    print("Invalid choice. Try again.")
    return mcq_review_with_options(field_name, ai_suggestion, all_options)


def close_case(case_id=None):
    """Main close-case workflow with AI-assisted MCQ review"""

    print("\n" + "="*60)
    print("🔍 CLOSE CASE: AI-Assisted Conscious Learning Capture")
    print("="*60)

    # Get case ID if not provided
    if not case_id:
        case_id = input("\nEnter case ID (e.g., CASE-001): ").strip()

    # Load case and AI analysis
    case = load_case(case_id)
    if not case:
        return

    gate = load_gate_answers(case_id)

    print(f"\n📋 Case: {case_id}")
    print(f"   Title: {case.get('title', 'No title')}")
    print(f"   Customer: {case.get('customer', 'Unknown')}")
    print(f"   Version: {case.get('version', 'Unknown')}")
    print(f"   Severity: {case.get('severity', 'Unknown')}")

    if gate:
        print(f"\n✅ AI Analysis Found - Using as suggestions below")
    else:
        print(f"\n⚠️  No AI analysis available - Will ask questions directly")

    # ROOT CAUSE
    root_cause, _ = mcq_review(
        "Root Cause",
        gate.get("root_cause") if gate else None
    )

    # OWNING TEAM
    team_options = [
        "Team R (Interactive UI)", "Team U (One-Way UI)", "Team G (RAG Flow)",
        "Team B (Tune/Config)", "Team E (Fine-tune/Adapter)", "Team Q (LLM Gateway)",
        "Team V (Validation)", "Team P (Post-processing)", "PLATFORM"
    ]
    owning_team, _ = mcq_review_with_options(
        "Owning Team",
        f"Team {gate.get('owning_team', '?')} (...)" if gate else None,
        team_options
    )

    # SYMPTOMS
    symptoms, _ = mcq_review(
        "Symptoms",
        gate.get("symptom") if gate else None
    )

    # DETECTION METHOD & LOGS
    detection, _ = mcq_review(
        "Detection Method",
        gate.get("detection_tip") if gate else None
    )

    logs_to_check, _ = mcq_review(
        "Log Streams to Check",
        ", ".join(gate.get("evidence_checked", [])) if gate else None
    )

    # FIX DETAILS
    fix_type_options = ["Config change", "Code fix", "Parameter tuning", "Workaround", "Upgrade"]
    fix_type, _ = mcq_review_with_options(
        "Fix Type",
        ("Config change" if "tune" in root_cause.lower() else "Code fix") if gate else None,
        fix_type_options
    )

    fix_details, _ = mcq_review(
        "Fix Details",
        gate.get("fix") if gate else None
    )

    # RULED OUT
    ruled_out, _ = mcq_review(
        "What Was Ruled Out",
        "; ".join(gate.get("ruled_out", [])) if gate else None
    )

    # AFFECTED VERSIONS
    affected_versions, _ = mcq_review(
        "Affected Versions",
        ", ".join(gate.get("affected_versions", [])) if gate else None
    )

    # FIXED IN
    fixed_in, _ = mcq_review(
        "Fixed In",
        gate.get("fix", "").split("Fixed in")[1].strip() if gate and "Fixed in" in gate.get("fix", "") else None
    )

    # PATTERN
    pattern, _ = mcq_review(
        "Pattern/Category",
        gate.get("root_cause", "") if gate else None
    )

    # CONFIDENCE
    confidence_options = ["High", "Medium", "Low"]
    confidence, _ = mcq_review_with_options(
        "Confidence Level",
        "High",
        confidence_options
    )

    # Compile resolution
    resolution = {
        "case_number": case_id,
        "closed_at": datetime.now().isoformat(),
        "root_cause": root_cause,
        "owning_team": owning_team.split("(")[0].strip(),
        "symptoms": symptoms,
        "detection_method": detection,
        "logs_to_check": logs_to_check,
        "fix": {
            "type": fix_type,
            "details": fix_details,
            "affected_versions": affected_versions,
            "fixed_in": fixed_in
        },
        "ruled_out": ruled_out,
        "pattern": pattern,
        "confidence": confidence,
        "reviewed_by": "human",
        "ai_assisted": gate is not None
    }

    # Save resolution
    save_case_resolution(case, resolution)
    update_case_status(case, resolution)

    written = [
        f"pocket-fde/cases/history/{case_id}.json",
        f"pocket-fde/cases/{case_id}.json",
    ]

    novel = input("\nIs this a novel pattern worth a learnings card? (y/n): ").strip().lower() == "y"
    if novel:
        card_path = write_learnings_card(case, resolution)
        if card_path:
            add_memory_entry(card_path, case, resolution)
            written += [str(card_path), "pocket-fde/MEMORY.md"]

    print("\n" + "="*60)
    print("✅ CASE CLOSED - CONSCIOUS LEARNINGS CAPTURED")
    print("="*60)
    for path in written:
        print(f"📁 Saved to: {path}")
    print(f"👥 Team: {resolution['owning_team']}")
    print(f"🎯 Confidence: {resolution['confidence']}")
    print(f"🧠 Reviewed by: Human (AI-assisted: {resolution['ai_assisted']})")


def save_case_resolution(case, resolution):
    """Save case resolution to history"""

    history_dir = Path("pocket-fde/cases/history")
    history_dir.mkdir(parents=True, exist_ok=True)

    history_file = history_dir / f"{case['case_number']}.json"

    history = {}
    if history_file.exists():
        with open(history_file) as f:
            history = json.load(f)

    history.update({
        "case_number": case["case_number"],
        "title": case.get("title", ""),
        "customer": case.get("customer", ""),
        "version": case.get("version", ""),
        "resolution": resolution,
        "last_updated": datetime.now().isoformat()
    })

    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)


def update_case_status(case, resolution):
    """Mark the case file RESOLVED and attach the reviewed resolution"""

    case_path = Path(f"pocket-fde/cases/{case['case_number']}.json")
    case.update({
        "status": "RESOLVED",
        "closed_at": resolution["closed_at"],
        "resolution": resolution,
    })

    with open(case_path, "w") as f:
        json.dump(case, f, indent=2)


def write_learnings_card(case, resolution):
    """Write a learnings card to second-brain/cards/. Never overwrites an existing card."""

    card_name = f"{case['case_number'].lower().replace('-', '_')}_resolution"
    card_path = Path(f"pocket-fde/second-brain/cards/{card_name}.md")

    if card_path.exists():
        print(f"⚠️  Card already exists, not overwriting: {card_path}")
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


if __name__ == "__main__":
    case_id = sys.argv[1] if len(sys.argv) > 1 else None
    close_case(case_id)
