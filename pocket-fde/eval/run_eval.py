"""Held-out evaluation: Baseline vs Pocket FDE (+ ablation without the closure gate).
Scoring is automatic (ID/string matching against hidden ground truth) except ONE clearly-labelled LLM-judge metric (root-cause match).
Usage: python eval/run_eval.py [--arms baseline ablation pocketfde] [--cases CASE-101 ...]"""
import argparse
import csv
import json
import math
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pocketfd import llm  # noqa: E402
from pocketfd.handover import Handover, accept_or_reject  # noqa: E402
from pocketfd.knowledge import Item, load_all, static_items  # noqa: E402
from pocketfd.known import FLAGS, OBS, OWN, flag_exists, flags_in, invented_names, stream_status, streams_in  # noqa: E402
from pocketfd.redact import leaks, log_outbound  # noqa: E402
from pocketfd.retrieval import Index  # noqa: E402
from pocketfd.router import Router  # noqa: E402
from pocketfd.triage import case_text, triage  # noqa: E402
from repos.flow import run as run_flow  # noqa: E402
from repos.sim import Config, Scenario  # noqa: E402

RES = ROOT / "eval" / "results"
OUT_PF = RES / "outbound_log.jsonl"
OUT_BASE = RES / "outbound_baseline.jsonl"
MAX_ROUNDS = 3
SCHEMA_BASE = """{"owning_team": "<team id>", "confidence": "high|medium|low", "reasoning": "", "hypotheses": [{"text": ""}],
 "questions": [{"text": "", "evidence": "<log or flag you want to see>"}], "logs_to_check": [], "flags_to_check": [], "recommended_flags": ["<config flags you recommend changing>"],
 "recommended_fix": "", "version_caveat": "", "handover": {"why_this_team": "", "checked_and_ruled_out": "", "version_and_config": "", "question_for_receiver": "", "suggested_next_action": ""},
 "escalate": false}"""
BASE_SYSTEM = "You are an expert support triage assistant for a multi-team GenAI assistant platform. Reply with JSON only."


# ------------------------------------------------------------------ arms
def baseline(case, qa_history, router):
    teams = ", ".join(f"{k} ({v['name']})" for k, v in OWN["teams"].items())
    qa = "".join(f"\nQ: {q}\nA: {a}" for q, a in qa_history or [])
    prompt = (f"Raw case (as reported):\n{case_text(case)}\n{('Answers received so far:' + qa) if qa else ''}\n\nTeams: {teams}\n"
              f"Decide which team owns this, what to ask next (all questions in one round), which logs/flags to check, and write a handover to that team.\nReturn JSON:\n{SCHEMA_BASE}")
    log_outbound("baseline", prompt, [], {}, path=OUT_BASE)   # raw: baseline has no redaction
    router.budget.step("baseline")
    r = llm.complete(prompt, BASE_SYSTEM)
    router.budget.charge(r)
    router.calls.append({"purpose": "baseline", "tier": "frontier", "in": r.input_tokens, "out": r.output_tokens, "latency_s": round(r.latency_s, 2)})
    out = llm.extract_json(r.text)
    owner = out.get("owning_team") if out.get("owning_team") in OWN["teams"] else None
    return {"case_id": case["id"], "owning_team": owner, "confidence": out.get("confidence"), "reasoning": out.get("reasoning", ""),
            "hypotheses": out.get("hypotheses", []), "questions": out.get("questions", []), "logs_to_check": out.get("logs_to_check", []),
            "flags_to_check": out.get("flags_to_check", []), "recommended_flags": out.get("recommended_flags", []), "recommended_fix": out.get("recommended_fix", ""), "version_caveat": out.get("version_caveat", ""),
            "handover": out.get("handover"), "escalate": bool(out.get("escalate")), "escalation_reason": "", "invented_names": [],
            "cost": {"steps": router.budget.steps, "tokens": router.budget.tokens, "calls": router.calls}}


def make_pocketfde(include_cards=True):
    items = load_all(include_pending=False) if include_cards else (static_items() + raw_note_items())
    ix = Index(items)
    def f(case, qa_history, router):
        router.outbound_log = OUT_PF
        return triage(case, ix, router, include_pending=False, qa_history=qa_history)
    return f


def raw_note_items():
    """Ablation: the repo holds the RAW (often vague) history notes instead of gate-produced cards."""
    out = []
    for p in sorted((ROOT / "cases/history").glob("*.json")):
        c = json.loads(p.read_text())
        out.append(Item(f"NOTE-{c['id']}", "note", f"{c['title']}. {c['description']} Resolution: {c['resolution_notes']} Teams touched: {', '.join(c['teams_touched'])}", versions=[c["version"]]))
    return out


ARMS = {"baseline": baseline, "ablation": make_pocketfde(False), "pocketfde": make_pocketfde(True)}


# ------------------------------------------------------------------ simulated responder (for the question-rounds metric)
def respond(case, gt, out):
    """Answers the agent's questions with REAL simulated evidence: log lines for streams that exist, flag values from the scenario."""
    sc = Scenario(**gt["scenario"])
    # the responder can switch on a masked log only if the agent said how (named the enable flag)
    text = json.dumps(out.get("questions", [])) + json.dumps(out.get("logs_to_check", []))
    enable = tuple(f for f in {x for x in flags_in(text)} if f.startswith("obs."))
    res = run_flow(Scenario(**{**gt["scenario"], "obs_enabled": tuple(gt["scenario"].get("obs_enabled", ())) + enable}))
    ans = []
    for q in out.get("questions", []):
        q = q if isinstance(q, dict) else {"text": str(q), "evidence": ""}
        ev = (q.get("evidence") or "") + " " + q.get("text", "")
        lines = [e["line"] for e in res.events if e["visible"] and e["stream"] in streams_in(ev)]
        flagv = [f"{f}={Config(sc.version, sc.overrides).get(f)}" for f in flags_in(ev) if f in FLAGS["flags"] and not f.startswith("obs.")]
        a = "\n".join(lines + flagv) or "That evidence is not available."
        ans.append((q.get("text", ""), a))
    return ans


# ------------------------------------------------------------------ scoring
def qtexts(out):
    parts = []
    for q in out.get("questions") or []:
        parts.append(q if isinstance(q, str) else f"{q.get('text','')} {q.get('evidence','')}")
    parts += [x if isinstance(x, str) else json.dumps(x) for x in out.get("logs_to_check") or []]
    parts += [str(x) for x in out.get("flags_to_check") or []]
    return " ".join(parts)


def topics_covered(gt, text):
    low = text.lower()
    return [t["topic"] for t in gt["key_questions_needed"] if any(k.lower() in low for k in t["any_of"])]


def evidence_covered(gt, text, version):
    names = flags_in(text) | streams_in(text)
    ok = []
    for e in gt["needed_evidence"]:
        valid = flag_exists(e, version) if e in FLAGS["flags"] else bool(stream_status(e, version) and (stream_status(e, version)["on_by_default"] or stream_status(e, version)["enable_flag"]))
        if e in names and valid:
            ok.append(e)
    return ok


def correct_owner(gt, out):
    acc = set(gt.get("acceptable_owners") or [gt["owning_team"]])
    if gt["expected_escalate"]:
        return bool(out.get("escalate")) and (out.get("owning_team") in acc or out.get("owning_team") is None)
    return out.get("owning_team") in acc


def simulate_bounces(gt, out):
    """0 if first route is right. Else 1 wrong hop, +1 more if the receiving team's handover check redirects to yet another wrong team (cap 3). Simulated, see summary."""
    if correct_owner(gt, out) or gt["expected_escalate"]:
        return 0
    h = out.get("handover") or {}
    ho = Handover(case_id=out["case_id"], from_team="support", to_team=out.get("owning_team") or "UNKNOWN",
                  why_this_team=h.get("why_this_team", ""), checked_and_ruled_out=h.get("checked_and_ruled_out", ""), trace_ids=["tr"], version_and_config=h.get("version_and_config", ""),
                  question_for_receiver=h.get("question_for_receiver", "?"), suggested_next_action=h.get("suggested_next_action", ""))
    d = accept_or_reject(ho)
    if not d.accepted and d.alternative_team == gt["owning_team"]:
        return 1
    return 2


def version_correct(gt, out, version):
    used = [str(f) for f in (out.get("recommended_flags") or []) + (out.get("flags_to_check") or [])]
    bad = [f for f in used if not flag_exists(f, version) or f in gt.get("invalid_fix_flags", [])]
    # note: for Pocket FDE the grounding validator has already stripped invalid flags; raw count is in grounding_issues
    return not bad, bad


def judge_root_cause(gt, out):
    """LLM-AS-JUDGE (fuzzy metric, labelled): does the top hypothesis/reasoning match the true root cause?"""
    hyp = (out.get("hypotheses") or [{}])[0]
    hyp = hyp.get("text", "") if isinstance(hyp, dict) else str(hyp)
    prompt = (f"True root cause: {gt['root_cause']}\n\nAgent's reasoning: {out.get('reasoning','')}\nAgent's top hypothesis: {hyp}\n\n"
              'Does the agent identify the same underlying root cause (not just the same team)? Reply JSON only: {"match": "yes|partial|no"}')
    try:
        r = llm.complete(prompt, "You grade incident triage answers strictly. JSON only.", model="haiku")
        return llm.extract_json(r.text).get("match", "no")
    except Exception:
        return "judge_error"


def outbound_leaks(path, case_ids_hint=None, since=0):
    n, items = 0, []
    if not path.exists():
        return 0, []
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("_t", 0) < since:
            continue
        found = leaks(rec["prompt_redacted"])
        n += len(found)
        items += found
    return n, items


# ------------------------------------------------------------------ run
def eval_case(arm, case_path):
    case = json.loads(case_path.read_text())
    gt = case.pop("ground_truth")
    fn = ARMS[arm]
    qa, rounds_out, covered, all_text = [], [], set(), ""
    t0 = time.time()
    first, rounds = None, MAX_ROUNDS + 1
    tot_tokens = tot_steps = 0
    budget_esc = False
    out = None
    try:
        for rnd in range(1, MAX_ROUNDS + 1):
            router = Router()   # one budget per triage run (= per round)
            out = fn(case, qa, router)
            tot_tokens += router.budget.tokens
            tot_steps += router.budget.steps
            if first is None:
                first = out
                first_steps, first_tokens = router.budget.steps, router.budget.tokens
            all_text += " " + qtexts(out)
            covered = set(topics_covered(gt, all_text))
            if len(covered) == len(gt["key_questions_needed"]):
                rounds = rnd
                break
            qa += respond(case, gt, out)
    except Exception as e:  # keep the run going; record the failure honestly
        return {"arm": arm, "case": case["id"], "error": repr(e)[:300]}
    r1_text = qtexts(first)
    v_ok, v_bad = version_correct(gt, first, case["version"])
    all_out_text = json.dumps({k: first.get(k) for k in ("reasoning", "hypotheses", "questions", "recommended_fix", "flags_to_check", "recommended_flags", "logs_to_check", "handover")}, default=str)
    inv = invented_names(all_out_text)
    return {
        "arm": arm, "case": case["id"], "version": case["version"], "expected_escalate": gt["expected_escalate"],
        "owner": first.get("owning_team"), "true_owner": gt["owning_team"], "routing_correct": correct_owner(gt, first),
        "escalated": bool(first.get("escalate")), "bounces": simulate_bounces(gt, first),
        "topics_round1": len(topics_covered(gt, r1_text)), "topics_total": len(gt["key_questions_needed"]), "rounds_to_cover_all": rounds if rounds <= MAX_ROUNDS else f">{MAX_ROUNDS}",
        "evidence_round1": len(evidence_covered(gt, r1_text, case["version"])), "evidence_total": len(gt["needed_evidence"]),
        "invented_names": len(inv), "invented_list": sorted(inv), "version_correct": v_ok, "version_bad_flags": v_bad,
        "caveat_given": bool(first.get("version_caveat")), "root_cause_judge": judge_root_cause(gt, first),
        "steps": first_steps, "tokens": first_tokens, "total_tokens_all_rounds": tot_tokens, "wall_s": round(time.time() - t0, 1),
        "budget_escalation": "budget" in (first.get("escalation_reason") or ""), "output": first,
    }


def summarize(rows):
    arms = list(dict.fromkeys(r["arm"] for r in rows))
    def agg(arm):
        rs = [r for r in rows if r["arm"] == arm and "error" not in r]
        n = len(rs) or 1
        er = [r for r in rs if not r["expected_escalate"]]
        rounds = [r["rounds_to_cover_all"] for r in rs]
        return {
            "n": len(rs), "routing": sum(r["routing_correct"] for r in rs), "bounces": sum(r["bounces"] for r in rs),
            "one_round": sum(1 for x in rounds if x == 1), "rounds_avg": round(sum((x if isinstance(x, int) else MAX_ROUNDS + 1) for x in rounds) / n, 2),
            "topics": sum(r["topics_round1"] for r in rs), "topics_t": sum(r["topics_total"] for r in rs),
            "evid": sum(r["evidence_round1"] for r in rs), "evid_t": sum(r["evidence_total"] for r in rs),
            "invented": sum(r["invented_names"] for r in rs), "version_ok": sum(r["version_correct"] for r in rs),
            "judge_yes": sum(1 for r in rs if r["root_cause_judge"] == "yes"), "judge_partial": sum(1 for r in rs if r["root_cause_judge"] == "partial"),
            "tokens": round(sum(r["tokens"] for r in rs) / n), "steps": round(sum(r["steps"] for r in rs) / n, 1),
            "esc": sum(r["escalated"] for r in rs), "esc_correct": sum(1 for r in rs if r["escalated"] == r["expected_escalate"]), "budget_esc": sum(r["budget_escalation"] for r in rs),
        }
    return {a: agg(a) for a in arms}


def write_outputs(rows):
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "results.json").write_text(json.dumps(rows, indent=2, default=str))
    flat = [{k: v for k, v in r.items() if k != "output"} for r in rows]
    keys = sorted({k for r in flat for k in r}, key=lambda k: (k not in ("arm", "case"), k))
    with open(RES / "per_case.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(flat)
    S = summarize(rows)
    # privacy: scan what was actually sent outbound (baseline = raw prompts, pocketfde/ablation = redacted)
    S["_privacy"] = {"pocketfde_outbound_calls": sum(1 for _ in open(OUT_PF)) if OUT_PF.exists() else 0, "pocketfde_leaks": outbound_leaks(OUT_PF)[0],
                     "baseline_outbound_calls": sum(1 for _ in open(OUT_BASE)) if OUT_BASE.exists() else 0, "baseline_leaks": outbound_leaks(OUT_BASE)[0]}
    (RES / "summary_numbers.json").write_text(json.dumps(S, indent=2))
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=["baseline", "ablation", "pocketfde"])
    ap.add_argument("--cases", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    for p in (OUT_PF, OUT_BASE):
        p.unlink(missing_ok=True)
    paths = [p for p in sorted((ROOT / "cases/heldout").glob("*.json")) if not a.cases or p.stem in a.cases]
    jobs = [(arm, p) for p in paths for arm in a.arms]
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda j: eval_case(*j), jobs))
    S = write_outputs(rows)
    print(json.dumps(S, indent=1))
    for r in rows:
        if "error" in r:
            print("ERROR", r["arm"], r["case"], r["error"])


if __name__ == "__main__":
    main()
