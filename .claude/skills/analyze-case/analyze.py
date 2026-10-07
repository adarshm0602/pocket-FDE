#!/usr/bin/env python3
"""
Pocket FDE Case Analyzer
Reads case JSON and returns triage analysis from knowledge repository
"""

import json
import sys
import os
import re
from pathlib import Path

def load_case(case_number):
    """Load case from JSON file"""
    if not re.fullmatch(r"CASE-[A-Za-z0-9_-]+", case_number):
        return None, "Use a case ID such as CASE-001 or CASE-101."
    # script_path = /.../.claude/skills/analyze-case
    # project_root = /Users/suryakonduru/Desktop/.../Final Capstone
    script_path = Path(__file__).parent
    project_root = script_path.parent.parent.parent

    # Try multiple paths to find cases directory
    cases_dirs = [project_root / "pocket-fde" / "cases", project_root / "cases", script_path / "cases"]
    cases_dirs += [p / group for p in list(cases_dirs) for group in ("heldout", "history")]

    case_file = None
    for cases_dir in cases_dirs:
        potential_file = cases_dir / f"{case_number}.json"
        if potential_file.exists():
            case_file = potential_file
            break

    if not case_file:
        return None, f"Case file not found in any of: {cases_dirs}"

    with open(case_file) as f:
        case = json.load(f)
    case.pop("ground_truth", None)
    return case, None

def analyze_case(case_data):
    """Analyze case using Pocket FDE knowledge repository patterns"""

    title = case_data.get("title", "")
    description = case_data.get("description", "")
    version = case_data.get("version", "unknown")
    customer = case_data.get("customer", "")
    severity = case_data.get("severity", "medium")
    team_suspicion = case_data.get("team_suspicion", "")
    evidence = case_data.get("evidence", {})

    # Route based on patterns (simplified knowledge repo)
    routing_patterns = {
        "tune-config": ("Team B", "tune-config-oncall@team.slack", 95),
        "retrieval": ("Team B", "tune-config-oncall@team.slack", 85),
        "cache": ("Team G", "cache-oncall@team.slack", 92),
        "timeout": ("Team PLATFORM", "platform-oncall@team.slack", 88),
        "gateway": ("Team PLATFORM", "platform-oncall@team.slack", 85),
    }

    # Simple pattern matching
    best_match = ("Team Unknown", "oncall@team.slack", 50)
    for keyword, (team, contact, confidence) in routing_patterns.items():
        if keyword.lower() in description.lower() or keyword.lower() in team_suspicion.lower():
            best_match = (team, contact, confidence)
            break

    team_name, contact, base_confidence = best_match

    # Adjust confidence based on severity and evidence
    confidence_score = base_confidence
    if len(evidence.get("logs", [])) > 0:
        confidence_score = min(95, confidence_score + 5)
    if severity == "critical":
        confidence_score = min(99, confidence_score + 3)

    return {
        "prototype": True,
        "measurement_note": "Rule-based demo only: confidence is a heuristic score, not measured accuracy. No LLM call is made.",
        "case_number": case_data.get("case_number") or case_data.get("id"),
        "title": title,
        "owning_team": team_name,
        "contact": contact,
        "confidence": f"{'HIGH' if confidence_score >= 85 else 'MEDIUM' if confidence_score >= 70 else 'LOW'} ({confidence_score}%)",
        "routing_reason": f"{version} system pattern + knowledge base match",
        "key_questions": [
            f"What is the exact error message in {evidence.get('logs', ['app logs'])[0] if evidence.get('logs') else 'logs'}?",
            "When did this issue start (before/after last deployment)?",
            "Is this affecting all customers or specific ones?"
        ][:3],
        "logs_to_check": evidence.get("logs", ["app logs", "error logs", "performance metrics"]),
        "escalation": "none" if confidence_score > 80 else "Check with platform team if timeout-related",
        "cost": {
            "tokens_used": 0,
            "retrieval_quality": f"{confidence_score}%",
            "approach": "knowledge-repo"
        }
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: analyze.py CASE-001")
        sys.exit(1)

    case_number = sys.argv[1]

    # Load case
    case_data, error = load_case(case_number)
    if error:
        print(f"❌ {error}")
        sys.exit(1)

    # Analyze
    result = analyze_case(case_data)

    print("PROTOTYPE DEMO: heuristic routing; no LLM or measured accuracy. Use the live app for the current model-backed pipeline.")

    # Output
    print(f"\n{'='*60}")
    print(f"📋 CASE ANALYSIS: {result['case_number']}")
    print(f"{'='*60}\n")
    print(f"Title: {result['title']}\n")
    print(f"🎯 Owning Team: {result['owning_team']}")
    print(f"   Contact: {result['contact']}")
    print(f"   Confidence: {result['confidence']}\n")
    print(f"📌 Routing Reason:\n   {result['routing_reason']}\n")
    print(f"❓ Key Questions:")
    for i, q in enumerate(result['key_questions'], 1):
        print(f"   {i}. {q}")
    print(f"\n📊 Logs to Check:")
    for log in result['logs_to_check']:
        print(f"   • {log}")
    print(f"\n⚠️  Escalation: {result['escalation']}\n")
    print(f"Model usage: {result['cost']['tokens_used']} tokens (no model call); heuristic score: {result['cost']['retrieval_quality']}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
