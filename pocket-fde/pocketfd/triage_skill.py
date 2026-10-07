"""Pocket FDE triage skill - run this directly or invoke from Claude Code."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pocketfd.knowledge import load_all
from pocketfd.retrieval import Index
from pocketfd.router import Router
from pocketfd.triage import triage

def run_triage(case_title, case_description, version, evidence=""):
    """Run Pocket FDE triage on a case. Returns the triage output."""
    case = {
        "id": "DEMO-CASE",
        "title": case_title,
        "version": version,
        "customer_tier": "enterprise",
        "description": case_description,
        "provided_evidence": evidence.split("\n") if evidence else [],
    }
    
    print("\n" + "=" * 80)
    print("POCKET FDE TRIAGE")
    print("=" * 80)
    print(f"\nCase: {case_title}")
    print(f"Version: {version}")
    print(f"Description: {case_description}\n")
    
    # Load knowledge repo and run triage
    ix = Index(load_all(include_pending=False))
    router = Router()
    out = triage(case, ix, router, include_pending=False)
    
    # Pretty print results
    print(f"Owner: {out['owning_team']} (contact: {out['owner_contact']})")
    print(f"Confidence: {out['confidence']}")
    print(f"Escalate: {out['escalate']}")
    
    if out['escalate']:
        print(f"\n⚠️  ESCALATION: {out['escalation_reason']}")
        if out['capture_brief']:
            print(f"\n{out['capture_brief']}")
    else:
        print(f"\nReasoning: {out['reasoning'][:400]}")
        print(f"\nTop questions (ONE round):")
        for i, q in enumerate(out['questions'][:3], 1):
            print(f"  {i}. {q['text'][:100]}")
        print(f"\nLogs to check:")
        for log in out['logs_to_check'][:3]:
            print(f"  - {log['stream']} (team {log['team']})" + (f" [OFF in prod: enable {log['caveat'][:50]}]" if log['caveat'] else ""))
    
    print(f"\nCost: {out['cost']['steps']} steps, {out['cost']['tokens']} tokens")
    print("=" * 80)
    
    return out


if __name__ == "__main__":
    # Example usage
    title = "One-Way widget returns odd answers, chat is fine"
    desc = "Acme Logistics: embedded One-Way UI returns 'not enough information' for simple questions. Chat UI answers the same questions fine. Started after last weekend's update."
    version = "v2"
    run_triage(title, desc, version)
