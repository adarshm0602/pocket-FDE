"""Closure gate: a resolved case cannot be closed until it yields a structured case card.
1) find missing fields, 2) ask 3-5 targeted questions (LLM, from what is missing), 3) answers (prepared file in demo/eval, CLI otherwise),
4) write a card to second-brain/pending/ for the curator."""
import json
from pathlib import Path

import yaml

from . import llm
from .knowledge import KB
from .known import FLAG_NAMES, OWN, STREAM_NAMES

FIELDS = ["symptom", "affected_versions", "owning_team", "root_cause", "config_involved", "evidence_checked", "ruled_out", "fix", "detection_tip"]
PRIORITY = ["root_cause", "owning_team", "config_involved", "fix", "evidence_checked", "affected_versions", "detection_tip", "ruled_out"]
MIN_REQUIRED = ["owning_team", "affected_versions", "root_cause", "fix", "evidence_checked"]
SYSTEM = ("You help close resolved incident cases for a fictional GenAI platform. Teams: " + ", ".join(sorted(OWN["teams"])) +
          ". Versions: v1, v2, v3. Reply with JSON only. Never invent flag or log-stream names; use only names given to you.")


def _empty(v):
    return v in (None, "", [], {})


def draft_and_gaps(case, call=None):
    """LLM step 1: extract what the notes already say, list what is missing, and write 3-5 targeted questions (one per missing field)."""
    call = call or (lambda p: llm.complete(p, SYSTEM))
    prompt = f"""Resolved case:
id: {case['id']}  version: {case['version']}  teams touched: {case.get('teams_touched')}  bounces: {case.get('bounces')}
title: {case['title']}
description: {case['description']}
resolution notes: {case.get('resolution_notes')!r}

Fields of a case card: {FIELDS}.
1. Fill in ONLY fields that the notes/description support with SPECIFIC content (a named flag, log stream, mechanism or version). A restatement of vague wording (\"config issue fixed\", \"cleared cache\", \"restarted and it worked\") does NOT count as filled: set it to null and ask.
2. For every field still missing, write one targeted question to the resolving developer, specific to THIS case (not generic). Ask at most 5; prioritise in this order: {PRIORITY}.
Return JSON: {{"draft": {{field: value|null}}, "questions": [{{"field": "<field>", "question": "<text>"}}]}}
Known config flags: {sorted(FLAG_NAMES)}
Known log streams: {sorted(STREAM_NAMES)}"""
    r = call(prompt)
    data = llm.extract_json(r.text)
    draft = {k: data.get("draft", {}).get(k) for k in FIELDS}
    # Version scope is only known to the developer; the case's own version is NOT evidence about other versions. Always ask.
    draft["affected_versions"] = None
    qs = [q for q in data.get("questions", []) if q.get("field") in FIELDS and q["field"] != "affected_versions" and _empty(draft.get(q["field"]))]
    qs.insert(0, {"field": "affected_versions", "question": f"On which platform versions (v1, v2, v3) does this root cause occur and your fix apply? (This case was reported on {case['version']}; say if older/newer versions differ or lack the flag.)"})
    return draft, qs[:5]


def run_gate(case, answers=None, ask=None, call=None, out_dir=None, auto_fill_cap=5):
    """answers: dict field->value (demo/eval mode). ask: callable(question)->str (interactive). Returns (card_or_None, transcript)."""
    draft, qs = draft_and_gaps(case, call)
    transcript = []
    for q in qs:
        if answers is not None:
            a = answers.get(q["field"])
        elif ask is not None:
            a = ask(q["question"])
        else:
            a = None
        transcript.append({"field": q["field"], "question": q["question"], "answer": a})
        if not _empty(a):
            draft[q["field"]] = a
    # Required fields the LLM did not ask about: ask them directly so the gate cannot pass with a hole in them.
    asked = {t["field"] for t in transcript}
    for f in MIN_REQUIRED:
        if _empty(draft.get(f)) and f not in asked:
            q = f"Please provide '{f}' for {case['id']}; it is required before this case can be closed."
            a = answers.get(f) if answers is not None else (ask(q) if ask else None)
            transcript.append({"field": f, "question": q, "answer": a})
            if not _empty(a):
                draft[f] = a
    missing = [f for f in MIN_REQUIRED if _empty(draft.get(f))]
    if missing:
        return None, {"passed": False, "missing": missing, "qa": transcript}
    n = case["id"].split("-")[-1]
    card = {"id": f"CARD-{n}", "source_case": case["id"], **{f: draft.get(f) for f in FIELDS},
            "visibility": "internal", "confidence": "high" if len(qs) <= 2 else "medium", "approved_by": None}
    for f in ("affected_versions", "config_involved", "evidence_checked", "ruled_out"):
        if isinstance(card[f], str):
            card[f] = [card[f]]
    d = Path(out_dir) if out_dir else KB / "pending"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{card['id']}.yaml").write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True))
    return card, {"passed": True, "missing": [], "qa": transcript}
