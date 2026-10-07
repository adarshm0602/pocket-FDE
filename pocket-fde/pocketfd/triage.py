"""Triage agent: retrieve -> redact -> one budgeted frontier step -> ground check (names/citations) -> Tier-0 enrichment -> handover brief.
Escalates (no guessing) when retrieval is weak, confidence is low, or the budget guard trips.
On escalation, prompts the developer to capture the solution for future use."""
import re

from . import llm
from .handover import Handover
from .known import FLAGS, OBS, OWN, VERSIONS, flag_exists, invented_names, stream_status
from .redact import Redactor
from .router import BudgetExceeded, Router

WEAK_SEM = 0.12   # no approved/unreviewed card above this cosine => retrieval is weak

SYSTEM = """You are Pocket FDE, an incident triage assistant for a fictional multi-team GenAI platform.
Hard rules:
- Use ONLY team ids, config flags and log stream names that appear in the provided context. Never invent any.
- Cite a source id in square brackets (e.g. [CARD-004], [FLAG:tune.top_k]) for every claim. If nothing supports a claim, say 'no supporting source'.
- Ask only for evidence that can actually exist for the customer's version (see EVIDENCE AVAILABILITY). If a log is off in prod, say how to enable it and its risk.
- Respect the customer's version: never recommend a flag that does not exist in that version; say what to do instead.
- If the evidence is insufficient, say so, set escalate=true and list what is needed. Do not guess an owner with high confidence. You may still provide a grounded owner hypothesis while escalating; a similar historical card does not confirm the cause.
- Ask ALL questions you need in ONE round (max 6).
Reply with JSON only."""

SCHEMA = """{
 "owning_team": "<team id from the list>",
 "confidence": "high|medium|low",
 "reasoning": "<2-4 sentences with [source ids]>",
 "hypotheses": [{"text": "", "citations": ["<source id>"], "confidence": "high|medium|low"}],
 "questions": [{"text": "<question to support engineer or customer>", "evidence": "<log stream or flag name it will reveal>"}],
 "logs_to_check": ["<known log stream>"],
 "flags_to_check": ["<known flag>"],
 "recommended_fix": "<fix valid for this version, with [source ids], or 'none yet'>",
 "version_caveat": "<what differs for this version, or ''>",
 "do_not_apply": ["<fix/flag that looks right but is invalid for this version>"],
 "handover": {"why_this_team": "", "checked_and_ruled_out": "", "version_and_config": "", "question_for_receiver": "", "suggested_next_action": ""},
 "escalate": false,
 "escalation_reason": ""
}"""


def availability_table(version):
    rows = []
    for team, t in OBS.items():
        for s, spec in t["streams"].items():
            if version in spec.get("default_on", []):
                rows.append(f"- {s} (team {team}): ON in prod for {version}")
            elif spec.get("enable"):
                rows.append(f"- {s} (team {team}): OFF in prod ({spec['off_reason']}); enable with {spec['enable']}, scope {spec.get('scope')}; risk: {spec['risk']}")
    return "\n".join(rows)


def flags_for(version):
    present = sorted(f for f in FLAGS["flags"] if flag_exists(f, version))
    absent = sorted(f for f in FLAGS["flags"] if not flag_exists(f, version))
    return present, absent


def case_text(case):
    ev = "\n".join(case.get("provided_evidence") or []) or "(none provided)"
    return f"title: {case['title']}\nversion: {case.get('version') or 'not provided'}  tier: {case.get('customer_tier')}\ndescription: {case['description']}\nlogs/evidence provided so far:\n{ev}"


def build_prompt(case, hits, qa_history, red):
    present, absent = flags_for(case["version"])
    chunks = []
    for h in hits:
        tag = []
        context_text = h.item.text
        if h.item.kind == "note":
            tag.append("LEARNING NOTE: cite this NOTE source ID; mentioned files and related notes are not separate retrieved sources")
            # Markdown's reference syntax must not masquerade as citation IDs.
            context_text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", context_text)
            context_text = re.sub(r"\[\[([^\]]+)\]\]", r"\1 (related reference)", context_text)
        if h.item.status == "unreviewed":
            tag.append("UNREVIEWED (lower confidence)")
        if not h.version_match:
            tag.append(f"VERSION CAVEAT: {h.caveat}")
        if h.item.meta.get("version_caveat"):
            tag.append(f"VERSION SCOPE: {h.item.meta['version_caveat']}")
        chunks.append(f"[{h.item.id}] {' | '.join(tag)}\n{red.redact(context_text)}")
    qa = ""
    if qa_history:
        qa = "\nEVIDENCE RETURNED SINCE YOUR LAST ROUND (answers to your questions):\n" + "\n".join(f"Q: {red.redact(q)}\nA: {red.redact(a)}" for q, a in qa_history) + "\n"
    return f"""CASE [CASE:{case['id']}] (customer identifiers are redacted):
{red.redact(case_text(case))}
{qa}
TEAMS: {', '.join(f'{k} ({v["name"]})' for k, v in OWN["teams"].items())}

EVIDENCE AVAILABILITY for {case['version']}:
{availability_table(case['version'])}

FLAGS THAT EXIST in {case['version']}: {', '.join(present)}
FLAGS THAT DO NOT EXIST in {case['version']} (never recommend): {', '.join(absent)}

RETRIEVED CONTEXT:
{chr(10).join(chunks)}

Return JSON exactly in this shape:
{SCHEMA}"""


def _hand(case, out, owner, red):
    h = out.get("handover") or {}
    traces = sorted(set(re.findall(r"\btr-[0-9a-f]+\b", case_text(case))))
    return Handover(case_id=case["id"], from_team="support", to_team=owner, why_this_team=h.get("why_this_team", ""),
                    checked_and_ruled_out=h.get("checked_and_ruled_out", ""), trace_ids=traces, version_and_config=h.get("version_and_config", ""),
                    question_for_receiver=h.get("question_for_receiver", ""), suggested_next_action=h.get("suggested_next_action", ""))


def _clean(out, version, retrieved_ids):
    """Tier-0 grounding: drop invented names, invalid-for-version flags, uncited ids. Returns (out, issues)."""
    issues = []
    text = " ".join(str(v) for v in out.values() if isinstance(v, (str, list, dict)))
    inv = invented_names(text)
    if inv:
        issues.append(f"invented names: {sorted(inv)}")
    bad_flags = [f for f in (out.get("flags_to_check") or []) if not flag_exists(f, version)]
    if bad_flags:
        issues.append(f"flags not valid for {version}: {bad_flags}")
        out["flags_to_check"] = [f for f in out["flags_to_check"] if f not in bad_flags]
    for h in out.get("hypotheses") or []:
        h["citations"] = [c for c in h.get("citations", []) if c in retrieved_ids]
        if not h["citations"]:
            h["unsupported"] = True
    return out, issues, inv


def diagnostic_questions(out, version):
    """Keep distinct, actionable questions that do not request nonexistent evidence."""
    from .known import flags_in, streams_in
    questions, seen = [], set()
    for q in out.get("questions") or []:
        if not isinstance(q, dict) or not isinstance(q.get("text"), str):
            continue
        text = q["text"].strip()
        evidence = (q.get("evidence") or "") + " " + text
        if not text or text.casefold() in seen:
            continue
        flags, streams = flags_in(evidence), streams_in(evidence)
        if not (flags or streams) and invented_names(evidence):
            continue
        if any(not flag_exists(f, version) for f in flags):
            continue
        if any(not (stream_status(s, version)["on_by_default"] or stream_status(s, version)["enable_flag"]) for s in streams):
            continue
        seen.add(text.casefold())
        questions.append({**q, "text": text})
    return questions[:6]


def citation_problems(out, source_ids, placeholders=()):
    """Check actual claim text and explicit citation lists, not JSON array brackets."""
    text = " ".join([out.get("reasoning", ""), out.get("recommended_fix", "")] +
                    [h.get("text", "") for h in out.get("hypotheses", []) if isinstance(h, dict)])
    def references(text):
        return {s.strip() for group in re.findall(r"\[([^\[\]]+)\]", text) for s in group.split(",")} - set(placeholders)
    # Generated privacy placeholders refer to masked identifiers, not evidence.
    # Only ignore placeholders actually present in this request's redactor.
    cited = references(text)
    for h in out.get("hypotheses", []):
        if isinstance(h, dict):
            cited.update(h.get("citations") or [])
    missing = set(cited) - set(source_ids)
    issues = [f"unsupported citation IDs: {sorted(missing)}"] if missing else []
    if out.get("reasoning") and not references(out["reasoning"]):
        issues.append("reasoning has no source citation")
    return issues


def triage(case, index, router: Router = None, include_pending=True, qa_history=None, k=8, min_questions=0, answer_validator=None):
    router = router or Router()
    red = Redactor()
    version = case["version"]
    router.budget.step("retrieve")
    hits = index.search(case_text(case), version, k=k, include_pending=include_pending)
    cards = [h for h in hits if h.item.kind in {"card", "note"}]
    weak = not any(h.sem >= WEAK_SEM for h in cards)
    ids = {h.item.id for h in hits}
    source_ids = ids | {f"CASE:{case['id']}"}
    result = {"case_id": case["id"], "retrieval": {"ids": [h.item.id for h in hits], "weak": weak, "sem_name": index.sem_name,
              "unreviewed_used": [h.item.id for h in hits if h.item.status == "unreviewed"]}}
    out, issues, inv = {}, [], set()
    answer_valid = False
    def parse_answer(text):
        parsed = llm.extract_json(text)
        return answer_validator(parsed) if answer_validator else parsed
    try:
        prompt = build_prompt(case, hits, qa_history, red)
        if min_questions:
            prompt += f"""\nDIAGNOSTIC QUESTION REQUIREMENT:
Return {min_questions}-6 distinct, case-specific questions in the questions array, in ONE round.
These are questions for a support engineer to confirm the hypothesis, even when the knowledge card strongly suggests a cause.
Ask about missing context (affected UI/tenants, session or version, onset/config changes), the distinguishing evidence, and a competing explanation where relevant.
Use only evidence available for this version. Do not repeat evidence already provided. Never pad with duplicate or unrelated questions.
Do not claim logs have been checked or alternatives ruled out unless that evidence is actually present in the case.
When chat and widget behavior differ, verify the comparison on the same query and tenant, not just the error logs.
Route to the team owning the underlying mechanism or configuration in the matching card, not merely the team displaying the error or recording the rejection. A logging gap does not establish the root cause of an incident.
Compare hypotheses against the distinguishing reported facts: intermittent versus consistent failures, load dependence, session behavior, onset and effective configuration. A generic error or chat/widget difference alone cannot select a cause. Explain why the leading mechanism fits better than a competing one; ask for evidence that could disprove it. A chat test outside the failing workload is not a matched comparison.
For intermittent failures concentrated in bulk or concurrent work, prioritize testing capacity/rate/latency mechanisms against static configuration problems. Ask whether the same widget request succeeds at low load and compare gateway events at failing timestamps. A version default alone does not explain why failures cluster during busy periods.
For upgrades, distinguish current defaults from effective tenant overrides. Historical cards are mechanism clues, not proof that an old-version defect or fix applies now. Check migrated overrides and configuration history against current-version defaults; if confirmed stale, restore the appropriate current default rather than blindly copying an old fix.
A fixed default does not rule out a migrated tenant override. Use the flag's owning team when the hypothesis is an incorrectly set or migrated configuration value. A valid configuration change exposing a downstream component defect belongs to the failing component, not automatically the team that changed the configuration.
Rank hypotheses by the specific incident pattern, not just whether they can produce the same generic error. Retrieved cards are alternatives to compare, not equally likely diagnoses. Select the best-supported mechanism's owner as a hypothesis with medium confidence when confirmation is missing; explain the uncertainty and needed evidence. Missing proof of the cause does not by itself erase a grounded owner hypothesis. Leave owning_team null only when no mechanism has a supported lead or the report lacks concrete symptoms. Never assign the UI owner just because the root cause is unknown.
Use conditional language for an unconfirmed cause and its fix. List only supplied checks under checked_and_ruled_out; do not copy checks performed in another incident. High confidence in a cause requires confirming case evidence, not just a matching card.
If the report has no concrete symptom, example query, timestamp or trace, leave owning_team null and escalate; a previous case for the same customer is not enough to diagnose this one.
Cite ONLY these source IDs: {', '.join(sorted(source_ids))}. Use [CASE:{case['id']}] for supplied case facts. Log names and labels such as [CASE] or [case description] are not source IDs.
Before returning JSON, check that the questions array contains at least {min_questions} useful questions. An empty array is an incomplete analysis.
"""
        r = router.call("triage", prompt, SYSTEM, chunk_ids=ids, redactor=red)
        invalid_answer = False
        try:
            out = parse_answer(r.text)
            answer_valid = True
        except (llm.LLMError, ValueError):
            invalid_answer = True
            issues.append("initial model response was incomplete or malformed")
        out, clean_issues, inv = _clean(out, version, source_ids)
        issues += clean_issues
        missing_questions = len(diagnostic_questions(out, version)) < min_questions
        bad_citations = citation_problems(out, source_ids, {p[1:-1] for p in red.mapping}) if min_questions else []
        if invalid_answer or inv or missing_questions or bad_citations:  # one budgeted repair, retaining the first answer if repair fails
            try:
                problems = []
                if invalid_answer:
                    problems.append("Your previous reply was not a valid complete JSON analysis. Follow the exact response shape and field types above.")
                if inv:
                    problems.append(f"Your previous answer used names that do not exist: {sorted(inv)}. Remove them.")
                if missing_questions:
                    problems.append(f"Your previous answer had fewer than {min_questions} usable diagnostic questions. Return {min_questions}-6 distinct questions that verify this case's cause using missing context and available evidence.")
                if bad_citations:
                    problems.append("Your previous answer has citation problems: " + "; ".join(bad_citations) + ". Cite only source IDs listed above, including the case source for supplied facts.")
                fix = router.call("repair", prompt + "\n\n" + " ".join(problems) + " Return the COMPLETE JSON analysis, including the questions array, using only known names.", SYSTEM, chunk_ids=ids, redactor=red)
                out2 = parse_answer(fix.text)
                out2, issues2, inv2 = _clean(out2, version, source_ids)
                out, issues, inv = out2, issues + ["repaired"] + issues2, inv2
                answer_valid = True
            except BudgetExceeded as e:
                issues.append(f"repair skipped: {e.reason}")
                out["escalate"] = True
                out["escalation_reason"] = f"budget guard stopped the repair step ({e.reason}); analysis is incomplete or contains unverified names"
            except (llm.LLMError, ValueError) as e:
                issues.append("repair failed; retained the first answer")
                out["escalate"] = True
                out["escalation_reason"] = "The model could not complete the verification step; a human should review the evidence."
    except BudgetExceeded as e:
        out = {"escalate": True, "escalation_reason": f"budget guard: {e.reason}", "confidence": "low"}
    except (llm.LLMError, ValueError) as e:
        out = {"escalate": True, "escalation_reason": f"model output unusable: {e}", "confidence": "low"}

    owner = out.get("owning_team") if out.get("owning_team") in OWN["teams"] else None
    escalate = bool(out.get("escalate")) or out.get("confidence") == "low" or weak or owner is None
    reason = out.get("escalation_reason") or ""
    if weak and "weak" not in reason:
        reason = (reason + " Retrieval is weak (no similar case card); treat the owner as a hypothesis only.").strip()
    # Tier 0: log status per version, from observability.yaml
    logs = []
    for s in out.get("logs_to_check") or []:
        st = stream_status(s, version)
        if st and (st["on_by_default"] or st["enable_flag"]):
            logs.append({"stream": s, "team": st["team"], "on_in_prod": st["on_by_default"], "enable_flag": st["enable_flag"],
                         "caveat": None if st["on_by_default"] else f"off in prod ({st['off_reason']}); risk: {st['risk']}"})
    qs = diagnostic_questions(out, version)
    diagnostics_complete = len(qs) >= min_questions
    remaining_citations = citation_problems(out, source_ids, {p[1:-1] for p in red.mapping}) if min_questions else []
    if remaining_citations:
        issues += remaining_citations
        escalate = True
        out["confidence"] = "low"
        out["recommended_fix"] = "No verified fix available; review the evidence and source references."
        reason = (reason + " Some claims have unsupported or missing source references. A human should review the evidence.").strip()
    if not diagnostics_complete:
        issues.append(f"incomplete diagnostics: {len(qs)} usable questions; at least {min_questions} required")
        escalate = True
        out["confidence"] = "low"
        reason = (reason + " The model did not return enough useful diagnostic questions. Collect more evidence before applying a fix.").strip()
    ho = _hand(case, out, owner or "UNKNOWN", red) if out.get("handover") or owner else None
    
    # On escalation, add a prompt to capture the solution
    capture_brief = ""
    if escalate:
        capture_brief = (f"\n\n**Please share the solution:** Once this case is resolved, run:\n"
                        f"```\n.venv/bin/python .claude/skills/capture-learning/capture.py\n```\n"
                        f"and answer the questions so we can save it for future incidents.")
    
    final = {**result, "owning_team": owner, "owner_contact": OWN["teams"][owner]["contact_role"] if owner else None, "confidence": out.get("confidence", "low"),
             "reasoning": out.get("reasoning", ""), "hypotheses": out.get("hypotheses", []), "questions": qs, "logs_to_check": logs,
             "flags_to_check": out.get("flags_to_check", []), "recommended_flags": out.get("recommended_flags", []),
             "recommended_fix": out.get("recommended_fix", ""), "version_caveat": out.get("version_caveat", ""), "do_not_apply": out.get("do_not_apply", []),
             "handover": ho.to_dict() if ho else None, "escalate": escalate, "escalation_reason": reason, "capture_brief": capture_brief,
             "diagnostics_complete": diagnostics_complete, "model_answer_valid": answer_valid, "grounding_issues": issues, "invented_names": sorted(inv), "cost": {"steps": router.budget.steps, "tokens": router.budget.tokens, "calls": router.calls}}
    return _restore(final, red)


def _restore(obj, red):
    if isinstance(obj, str):
        return red.restore(obj)
    if isinstance(obj, list):
        return [_restore(x, red) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k == "cost" else _restore(v, red)) for k, v in obj.items()}
    return obj
