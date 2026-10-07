"""Evaluate the live web API on held-out cases; hidden answers are used only for offline scoring.

Does not run the original Claude judge or overwrite Surya's saved evaluations.
"""
import argparse
import hashlib
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pocketfd.known import flag_exists, flags_in, streams_in
from pocketfd.redact import leaks


def score(case, response):
    gt, result = case["ground_truth"], response["result"]
    question_text = " ".join(q["text"] + " " + (q.get("evidence") or "") for q in result["questions"])
    matched = [t["topic"] for t in gt["key_questions_needed"] if any(k.lower() in question_text.lower() for k in t["any_of"])]
    evidence_text = question_text + " " + json.dumps(result["logs_to_check"]) + " " + " ".join(result["flags_to_check"])
    evidence_names = flags_in(evidence_text) | streams_in(evidence_text)
    fix_flags = flags_in(result["recommended_fix"]) | set(result["flags_to_check"])
    invalid_flags = sorted(f for f in fix_flags if not flag_exists(f, case["version"]) or f in gt.get("invalid_fix_flags", []))
    claim_text = result["reasoning"] + " " + result["recommended_fix"] + " " + " ".join(h.get("text", "") for h in result["hypotheses"])
    cited = {s.strip() for group in re.findall(r"\[([^\[\]]+)\]", claim_text) for s in group.split(",")}
    for hypothesis in result["hypotheses"]:
        cited.update(hypothesis.get("citations") or [])
    source_ids = set(result["retrieval"]["ids"]) | {f"CASE:{case['id']}"}
    owners = gt.get("acceptable_owners") or [gt["owning_team"]]
    return {"case": case["id"], "version": case["version"], "owner": result["owning_team"],
            "expected_owner": gt["owning_team"], "owner_correct": result["owning_team"] in owners or (gt["expected_escalate"] and result["owning_team"] is None),
            "escalated": result["escalate"], "expected_escalate": gt["expected_escalate"],
            "escalation_correct": result["escalate"] == gt["expected_escalate"],
            "questions": len(result["questions"]), "diagnostics_complete": result["diagnostics_complete"],
            "question_topics_covered": matched, "question_topics_expected": [t["topic"] for t in gt["key_questions_needed"]],
            "evidence_covered": [e for e in gt["needed_evidence"] if e in evidence_names], "evidence_expected": gt["needed_evidence"],
            "version_valid": not invalid_flags, "invalid_fix_flags": invalid_flags,
            "citations_present": bool(cited), "citations_known": bool(cited) and cited <= source_ids,
            "unretrieved_citations": sorted(cited - source_ids), "invented_names": result["invented_names"],
            "tokens": result["cost"]["tokens"], "latency_s": response["elapsed_s"],
            "repair_calls": sum(c["purpose"] == "repair" for c in result["cost"]["calls"]),
            "expected_root_cause": gt["root_cause"], "response": response}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--retrieval", choices=["surya", "hybrid"], default="surya")
    args = parser.parse_args()
    stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y%m%d-%H%M%S")
    directory = ROOT / "web/evaluation" / f"{stamp}-{args.retrieval}-gemini"
    directory.mkdir(parents=True)
    rows = []
    with httpx.Client(base_url=args.url, timeout=400) as client:
        status = client.get("/api/status").json()
        if not status["model"]["ready"]:
            raise SystemExit("No model is configured. Connect Gemini before running evaluation.")
        mode = next(m for m in status["retrieval_modes"] if m["id"] == args.retrieval)
        if not mode["ready"]:
            raise SystemExit("Hybrid search is not ready. Run Setup Hybrid Search.command first.")
        print(f"Model: {status['model']['model']}; retrieval: {mode['method']}", flush=True)
        for path in sorted((ROOT / "cases/heldout").glob("CASE-*.json")):
            if args.cases and path.stem not in args.cases:
                continue
            # Send ONLY the case ID. The API excludes ground truth from the model context.
            response = client.post("/api/analyze", json={"case_id": path.stem, "retrieval": args.retrieval})
            if response.status_code != 200:
                row = {"case": path.stem, "error": response.json().get("detail", "Request failed"), "status": response.status_code}
            elif response.json().get("knowledge_revision") != status["knowledge_revision"]:
                row = {"case": path.stem, "error": "Reviewed knowledge changed during this run; rerun for a consistent comparison.", "status": 409}
            else:
                row = score(json.loads(path.read_text()), response.json())
            rows.append(row)
            (directory / "results.json").write_text(json.dumps(rows, indent=2))
            if "error" in row:
                print(f"{path.stem}: HTTP {row['status']} — {row['error']}", flush=True)
            else:
                print(f"{path.stem}: owner {row['owner']} ({'correct' if row['owner_correct'] else 'wrong'}), {row['questions']} questions, topics {len(row['question_topics_covered'])}/{len(row['question_topics_expected'])}, {row['tokens']} tokens, {row['latency_s']}s", flush=True)
    good = [r for r in rows if "error" not in r]
    summary = {"model": status["model"]["model"], "retrieval": mode['method'], "retrieval_mode": args.retrieval,
               "embedding_model": good[0]["response"].get("embedding_model") if good else None,
               "embedding_revision": good[0]["response"].get("embedding_revision") if good else None,
               "cases": len(rows), "successful_calls": len(good),
               "owner_correct": sum(r["owner_correct"] for r in good), "escalation_correct": sum(r["escalation_correct"] for r in good),
               "diagnostics_complete": sum(r["diagnostics_complete"] for r in good),
               "question_topics_covered": sum(len(r["question_topics_covered"]) for r in good),
               "question_topics_expected": sum(len(r["question_topics_expected"]) for r in good),
               "evidence_covered": sum(len(r["evidence_covered"]) for r in good), "evidence_expected": sum(len(r["evidence_expected"]) for r in good),
               "version_valid": sum(r["version_valid"] for r in good), "citations_known": sum(r["citations_known"] for r in good),
               "total_tokens": sum(r["tokens"] for r in good), "median_latency_s": statistics.median(r["latency_s"] for r in good) if good else None,
               "retrieval_source_sha256": hashlib.sha256((ROOT / "pocketfd/retrieval.py").read_bytes()).hexdigest(),
               "knowledge_revision": status["knowledge_revision"], "knowledge_items": status["knowledge_items"],
               "knowledge_sources": status["knowledge_sources"],
               "scoring": "Offline ID/keyword matching. Question-topic scores use actual questions only, not log lists. Citations may reference retrieved items or supplied case facts. Known citation IDs do not prove factual entailment. Root-cause text is included for separate review; no hidden answer is sent to the analysis model. These synthetic cases are used for development, including prompt refinement, not an independent test set."}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2))
    lines = [f"# {mode['label']} — live Gemini evaluation", "", f"Model: `{summary['model']}`. Retrieval: {summary['retrieval']}.", "",
             "Synthetic held-out cases, one first-round run per case; any repair is included in tokens and latency. These results do not establish performance on real customer incidents.", "",
             "| Case | Owner | Owner correct | Questions | Question topics | Escalation correct | Tokens | Seconds |", "|---|---|---|---:|---|---|---:|---:|"]
    for row in rows:
        if "error" in row:
            lines.append(f"| {row['case']} | HTTP {row['status']} | — | — | — | — | — | — |")
        else:
            lines.append(f"| {row['case']} | {row['owner'] or 'Unassigned'} | {row['owner_correct']} | {row['questions']} | {len(row['question_topics_covered'])}/{len(row['question_topics_expected'])} | {row['escalation_correct']} | {row['tokens']} | {row['latency_s']} |")
    lines += ["", f"Successful calls: {len(good)}/{len(rows)}. Correct owners: {summary['owner_correct']}/{len(rows)}. Complete diagnostics: {summary['diagnostics_complete']}/{len(rows)}.",
              f"Question topics: {summary['question_topics_covered']}/{summary['question_topics_expected']}. Required evidence: {summary['evidence_covered']}/{summary['evidence_expected']}.",
              f"Version-valid fixes/flags: {summary['version_valid']}/{len(good)}. Outputs with only retrieved citation IDs: {summary['citations_known']}/{len(good)}.",
              f"Total tokens: {summary['total_tokens']}. Median latency: {summary['median_latency_s']}s.", "", summary["scoring"], "",
              "## Gaps", ""]
    for row in good:
        missing = set(row["question_topics_expected"]) - set(row["question_topics_covered"])
        if missing or not row["owner_correct"] or not row["escalation_correct"] or not row["citations_known"]:
            lines.append(f"- {row['case']}: missing question topics: {', '.join(sorted(missing)) or 'none'}; owner correct={row['owner_correct']}; escalation correct={row['escalation_correct']}; known citations={row['citations_known']}.")
    (directory / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "knowledge_sources"}, indent=2), flush=True)
    print(f"Report: {directory / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
