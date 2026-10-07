"""Builds eval/results/summary.md from results.json (+ eval/interpretation.md, written by hand after reading the numbers)."""
import json
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"
INTERP = Path(__file__).resolve().parent / "interpretation.md"
LABEL = {"baseline": "Baseline", "ablation": "Ablation (no gate)", "pocketfde": "Pocket FDE"}


def pct(a, b):
    return f"{a}/{b}"


def main():
    rows = json.loads((RES / "results.json").read_text())
    S = json.loads((RES / "summary_numbers.json").read_text())
    arms = [a for a in LABEL if a in S]
    L = ["# Evaluation summary: Pocket FDE vs baseline (synthetic world, 8 held-out cases)", "",
         "> **Read this first.** The platform, teams, cases and logs are synthetic. This shows the mechanism works on a controlled simulation, not that it will work on real, messy enterprise cases. n = 8 cases, one run each, one model; differences of one case are within noise. "
         "Scoring is automatic (ID/string matching against hidden ground truth) except where marked *LLM-judge*.", "",
         "Conditions: **Baseline** = frontier model, raw case text, no retrieval, free-form handover (knows team names only). "
         "**Ablation** = Pocket FDE pipeline over the *raw vague history notes* instead of gate-produced cards. **Pocket FDE** = gate cards + hybrid retrieval + redaction + handover template + budget guard.", ""]
    hdr = "| Metric | " + " | ".join(LABEL[a] for a in arms) + " |"
    L += [hdr, "|---|" + "---|" * len(arms)]
    def row(name, f):
        L.append(f"| {name} | " + " | ".join(f(S[a]) for a in arms) + " |")
    row("1. Routing accuracy (correct owner first; escalation counts for the 'insufficient evidence' case)", lambda s: pct(s["routing"], s["n"]))
    row("2. Simulated bounces (wrong-team hops, lower is better)", lambda s: str(s["bounces"]))
    row("3a. Cases where all key questions were asked in ONE round", lambda s: pct(s["one_round"], s["n"]))
    row("3b. Avg rounds to cover all key questions (4 = not within 3)", lambda s: str(s["rounds_avg"]))
    row("4a. Key-question topics covered in round 1", lambda s: pct(s["topics"], s["topics_t"]))
    row("4b. Needed evidence correctly requested in round 1 (valid for the version)", lambda s: pct(s["evid"], s["evid_t"]))
    row("5. Invented flags/logs (hallucinations, after any repair/validator)", lambda s: str(s["invented"]))
    row("6. Version-correct (no flag invalid for the customer's version)", lambda s: pct(s["version_ok"], s["n"]))
    row("*LLM-judge*: top hypothesis matches true root cause (yes / partial)", lambda s: f"{s['judge_yes']} / {s['judge_partial']}")
    row("7a. Tokens per case (round 1)", lambda s: str(s["tokens"]))
    row("7b. Steps per case (round 1)", lambda s: str(s["steps"]))
    row("7d. Escalation correct (escalated iff the case needs it; 1 of 8 does)", lambda s: pct(s["esc_correct"], s["n"]))
    row("7c. Escalations (of which budget-guard)", lambda s: f"{s['esc']} ({s['budget_esc']})")
    p = S.get("_privacy", {})
    L += ["", f"**8. Privacy (from the outbound logs):** Pocket FDE made {p.get('pocketfde_outbound_calls')} external calls with **{p.get('pocketfde_leaks')} raw identifiers** found in them "
          f"(`outbound_log.jsonl`); the baseline made {p.get('baseline_outbound_calls')} calls with **{p.get('baseline_leaks')} raw identifiers** (customer names, emails, IPs) sent as-is (`outbound_baseline.jsonl`). "
          "Redaction is regex + a customer list; free-text person names are not detected.", "", "## Per case", "",
          "| Case | True owner | " + " | ".join(f"{LABEL[a]} owner (esc)" for a in arms) + " | bounces " + "/".join(a[:4] for a in arms) + " | topics r1 " + "/".join(a[:4] for a in arms) + " |", "|---|---|" + "---|" * (len(arms) + 2)]
    cases = sorted({r["case"] for r in rows})
    def get(a, c):
        return next((r for r in rows if r["arm"] == a and r["case"] == c), None)
    for c in cases:
        cells, bo, tp = [], [], []
        true = ""
        for a in arms:
            r = get(a, c)
            if not r or "error" in r:
                cells.append("ERROR"); bo.append("-"); tp.append("-"); continue
            true = r["true_owner"] + (" (escalate)" if r["expected_escalate"] else "")
            cells.append(f"{r['owner']}{' ✓' if r['routing_correct'] else ' ✗'} ({'esc' if r['escalated'] else 'no'})")
            bo.append(str(r["bounces"])); tp.append(f"{r['topics_round1']}/{r['topics_total']}")
        L.append(f"| {c} | {true} | " + " | ".join(cells) + " | " + "/".join(bo) + " | " + "/".join(tp) + " |")
    # honest losses
    L += ["", "## Where Pocket FDE did NOT win (auto-detected)", ""]
    losses = []
    for c in cases:
        p_, b_, a_ = get("pocketfde", c), get("baseline", c), get("ablation", c)
        if not p_ or "error" in p_:
            losses.append(f"- {c}: Pocket FDE run errored: {p_ and p_.get('error')}")
            continue
        for other, name in ((b_, "baseline"), (a_, "ablation")):
            if not other or "error" in other:
                continue
            if other["routing_correct"] and not p_["routing_correct"]:
                losses.append(f"- {c}: {name} routed correctly ({other['owner']}) but Pocket FDE did not ({p_['owner']}).")
            if other["topics_round1"] > p_["topics_round1"]:
                losses.append(f"- {c}: {name} covered more key-question topics in round 1 ({other['topics_round1']} vs {p_['topics_round1']}).")
            if other["evidence_round1"] > p_["evidence_round1"]:
                losses.append(f"- {c}: {name} requested more needed evidence ({other['evidence_round1']} vs {p_['evidence_round1']}).")
            if other["version_correct"] and not p_["version_correct"]:
                losses.append(f"- {c}: {name} was version-correct, Pocket FDE was not ({p_['version_bad_flags']}).")
            if other["tokens"] < p_["tokens"]:
                pass  # cost differences are reported in the table, not as losses
    L += losses or ["- none detected"]
    errs = [r for r in rows if "error" in r]
    if errs:
        L += ["", "## Run errors (excluded from the table)"] + [f"- {r['arm']} {r['case']}: {r['error']}" for r in errs]
    if INTERP.exists():
        L += ["", INTERP.read_text().strip()]
    (RES / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L)[:6000])


if __name__ == "__main__":
    main()
