"""Repeat fresh synthetic incident variants against both live search modes.

Expected answers stay offline. Fixtures are never added to the knowledge corpus.
"""
import argparse
import hashlib
import json
from pathlib import Path

import httpx

from web.evaluate_baseline import ROOT, score

INCIDENT_FIELDS = {"id", "title", "description", "version", "customer_tier", "provided_evidence"}


def incident_payload(case):
    return {key: value for key, value in case.items() if key in INCIDENT_FIELDS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=2)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    cases = json.loads((ROOT / "web/evaluation/diagnostic-variants.json").read_text())
    rows = []
    with httpx.Client(base_url=args.url, timeout=400) as client:
        status = client.get("/api/status").raise_for_status().json()
        if not status["model"]["ready"] or not all(m["ready"] for m in status["retrieval_modes"]):
            raise SystemExit("Connect a model and prepare both retrieval modes first.")
        artifact = {"model": status["model"]["model"], "knowledge_revision": status["knowledge_revision"],
                    "knowledge_items": status["knowledge_items"], "repeats": args.repeats,
                    "source_sha256": {name: hashlib.sha256((ROOT / "pocketfd" / name).read_bytes()).hexdigest()
                                      for name in ("retrieval.py", "triage.py")},
                    "web_source_sha256": {name: hashlib.sha256((ROOT / "web" / name).read_bytes()).hexdigest()
                                          for name in ("app.py", "provider.py")},
                    "fixture_sha256": hashlib.sha256((ROOT / "web/evaluation/diagnostic-variants.json").read_bytes()).hexdigest(),
                    "limitations": "Synthetic analogues of development cases, not independent accuracy evidence. Owner is a hypothesis until supplied logs establish cause. Citation-ID checks do not prove entailment.",
                    "results": rows}
        for repeat in range(args.repeats):
            for case in cases:
                # Alternate which mode goes first to reduce ordering effects.
                for mode in (("surya", "hybrid") if repeat % 2 == 0 else ("hybrid", "surya")):
                    response = client.post("/api/analyze", json={"incident": incident_payload(case), "retrieval": mode})
                    data = response.json()
                    if response.status_code != 200:
                        row = {"case": case["id"], "repeat": repeat + 1, "mode": mode,
                               "status": response.status_code, "error": data.get("detail", "Request failed")}
                    else:
                        if data["knowledge_revision"] != status["knowledge_revision"] or data["model"] != artifact["model"]:
                            raise SystemExit("Model or knowledge changed during comparison; rerun.")
                        row = {"repeat": repeat + 1, "mode": mode, **score(case, data)}
                    rows.append(row)
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
                    if "error" in row:
                        print(f"{case['id']} round {repeat + 1} {mode}: HTTP {row['status']} {row['error']}", flush=True)
                    else:
                        print(f"{case['id']} round {repeat + 1} {mode}: owner={row['owner']}, expected={row['expected_owner']}, questions={row['questions']}, escalate={row['escalated']}", flush=True)


if __name__ == "__main__":
    main()
