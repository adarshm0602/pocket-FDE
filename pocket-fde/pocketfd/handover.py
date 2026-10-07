"""Standard cross-team handover + receiving-side accept/reject (Tier 0: deterministic, uses ownership.yaml and flag/stream owners)."""
from dataclasses import dataclass, field, asdict

from .known import FLAGS, OWN, flags_in, streams_in

REQUIRED = ["why_this_team", "checked_and_ruled_out", "trace_ids", "version_and_config", "question_for_receiver", "suggested_next_action"]


@dataclass
class Handover:
    case_id: str
    from_team: str
    to_team: str
    why_this_team: str = ""
    checked_and_ruled_out: str = ""
    trace_ids: list = field(default_factory=list)
    version_and_config: str = ""
    question_for_receiver: str = ""
    suggested_next_action: str = ""
    bounces: int = 0

    def missing(self):
        return [f for f in REQUIRED if not getattr(self, f)]

    def to_dict(self):
        return asdict(self)


@dataclass
class Decision:
    accepted: bool
    reason: str
    alternative_team: str = ""
    bounces: int = 0


def _owner_votes(text):
    """Weighted votes for which team the evidence points at. Flags (the cause) weigh 2, log streams (where it was observed) weigh 1."""
    votes = {}
    for flag in flags_in(text):
        owner = FLAGS["flags"][flag]["owner"] if flag in FLAGS["flags"] else None
        for t in _split_owner(owner):
            votes[t] = votes.get(t, 0) + 2
    for s in streams_in(text):
        for team, streams in OWN["log_streams"].items():
            if s in streams:
                votes[team] = votes.get(team, 0) + 1
    return votes


def _split_owner(owner):
    if not owner:
        return []
    return [t for t in owner.replace("(ambiguous)", "").replace("+", " ").split() if t in OWN["teams"]]


def accept_or_reject(h: Handover):
    miss = h.missing()
    if miss:
        h.bounces += 1
        return Decision(False, f"Insufficient handover: missing {', '.join(miss)}. Resubmit with these filled in.", h.from_team, h.bounces)
    evidence = " ".join([h.why_this_team, h.checked_and_ruled_out, h.version_and_config, h.suggested_next_action])
    votes = _owner_votes(evidence)
    if not votes:
        h.bounces += 1
        return Decision(False, "No evidence points at any team boundary (no known flag or log stream cited). Add the log lines or flags that show where it fails.", h.from_team, h.bounces)
    best = max(votes, key=votes.get)
    if votes.get(h.to_team, 0) >= votes[best]:
        return Decision(True, f"Accepted: evidence points at {h.to_team} boundary (votes {votes}).", "", h.bounces)
    h.bounces += 1
    amb = next((a for a in OWN["ambiguous"] if a["default_route"] == best or best in a["candidates"]), None)
    return Decision(False, f"Rejected: cited evidence points at {best} ({OWN['teams'][best]['name']}), not {h.to_team} (votes {votes}). Route to {OWN['teams'][best]['contact_role']}.", best, h.bounces)
