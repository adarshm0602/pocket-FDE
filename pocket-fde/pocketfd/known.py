"""Single source of truth for names that exist in the world. Used by triage and the hallucination metric."""
import re
from pathlib import Path

import yaml

WORLD = Path(__file__).resolve().parent.parent / "world"
_y = lambda n: yaml.safe_load((WORLD / n).read_text())

FLAGS = _y("config_flags.yaml")
OWN = _y("ownership.yaml")
OBS = _y("observability.yaml")["teams"]
TENANTS = _y("customers.yaml")["tenants"]

FLAG_NAMES = set(FLAGS["flags"]) | {r["old"] for r in FLAGS["renamed_or_removed"] if r["old"]}
STREAM_NAMES = {s for t in OBS.values() for s in t["streams"]}
TEAM_IDS = set(OWN["teams"])
VERSIONS = ["v1", "v2", "v3"]

# A "named thing" looks like: dotted flag (a.b.c) or log stream (x.y). Anything of that shape must be known.
_DOTTED = re.compile(r"\b[a-z][a-z_]*(?:\.[a-z_]+)+\b")


def flag_exists(flag, version):
    f = FLAGS["flags"].get(flag)
    return bool(f) and f.get(version) is not None


def stream_status(stream, version):
    """Returns dict(on_by_default, enable_flag, off_reason, risk, team) or None if the stream is unknown."""
    for team, t in OBS.items():
        s = t["streams"].get(stream)
        if s:
            return {"team": team, "on_by_default": version in s.get("default_on", []), "enable_flag": s.get("enable"),
                    "off_reason": s.get("off_reason"), "risk": s.get("risk"), "exists_in_version": bool(s.get("default_on")) or bool(s.get("enable")),
                    "introduced_here": version in s.get("default_on", []) or bool(s.get("enable"))}
    return None


def invented_names(text):
    """Dotted identifiers in text that are neither known flags nor known log streams (hallucination check)."""
    out = set()
    for m in _DOTTED.findall(text):
        if m in FLAG_NAMES or m in STREAM_NAMES:
            continue
        if m.endswith((".yaml", ".json", ".md", ".py", ".log")) or m.split(".")[0] in {"e", "i", "etc", "vs"}:
            continue
        out.add(m)
    return out


def flags_in(text):
    return {m for m in _DOTTED.findall(text) if m in FLAG_NAMES}


def streams_in(text):
    return {m for m in _DOTTED.findall(text) if m in STREAM_NAMES}
