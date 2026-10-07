"""Shared simulation core for the fictional GenAI-assistant platform.

Each team's "repo" under repos/ is a tiny Python module that reads flags via Config,
emits log lines in its own format through Logs, and talks to neighbours only through
contract-validated payloads. Scenario fields are the fault injection.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

WORLD = Path(__file__).resolve().parent.parent / "world"


def _load(name):
    return yaml.safe_load((WORLD / name).read_text())


FLAGS = _load("config_flags.yaml")["flags"]
OBS = _load("observability.yaml")["teams"]
TENANTS = _load("customers.yaml")["tenants"]

_CONTRACTS = {}


def contract(name):
    if name not in _CONTRACTS:
        doc = yaml.safe_load((WORLD / "contracts" / f"{name}.yaml").read_text())
        _CONTRACTS[name] = doc["components"]["schemas"]["Body"]["required"]
    return _CONTRACTS[name]


class HopError(Exception):
    def __init__(self, hop, code, message):
        super().__init__(f"{hop}: {code}: {message}")
        self.hop, self.code, self.message = hop, code, message


def validate(contract_name, payload, hop):
    missing = [k for k in contract(contract_name) if k not in payload]
    if missing:
        raise HopError(hop, "CONTRACT_MISMATCH", f"{contract_name} missing {missing}")


@dataclass
class Scenario:
    version: str                      # v1 | v2 | v3
    tenant_id: str = "t-acme"
    ui_mode: str = "interactive"      # interactive | oneway
    has_session: bool = True
    query: str = "How do I reset the device?"
    provider_latency_ms: int = 800
    secondary_latency_ms: int = 800
    tenant_rpm_load: int = 10
    overrides: dict = field(default_factory=dict)       # tenant-level flag overrides
    config_changes: list = field(default_factory=list)  # [{flag, old, new, when}] audit events
    relevant_doc_rank: int = 3
    adapter_present: object = None    # None -> from tenant
    source_metadata: object = None    # None -> from tenant
    cache_stale: bool = False
    obs_enabled: tuple = ()           # observability flags switched on
    trace_id: str = "tr-7f3a91"


class Config:
    def __init__(self, version, overrides):
        self.version, self.overrides = version, overrides

    def exists(self, flag):
        return flag in FLAGS and FLAGS[flag].get(self.version) is not None

    def get(self, flag):
        """Override wins, but only if the flag exists in this version (absent flags are ignored)."""
        if not self.exists(flag):
            return None
        return self.overrides.get(flag, FLAGS[flag][self.version])


class Ctx:
    def __init__(self, sc: Scenario):
        self.sc = sc
        self.cfg = Config(sc.version, sc.overrides)
        self.tenant = TENANTS[sc.tenant_id]
        self.events = []
        self.clock_ms = 0
        self.flags = {}               # answer-quality facts: stale, base_model, docs_ignored, ...
        self.hops = []

    def tick(self, ms):
        self.clock_ms += ms

    def ts(self):
        s, ms = divmod(36000000 + self.clock_ms, 1000)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"2025-03-12T{h:02d}:{m:02d}:{sec:02d}.{ms:03d}Z"

    def visible(self, team, stream):
        spec = OBS[team]["streams"].get(stream, {})
        if self.sc.version in spec.get("default_on", []):
            return True
        return spec.get("enable") in self.sc.obs_enabled

    def log(self, team, stream, level, line):
        self.events.append({"team": team, "stream": stream, "level": level, "ts": self.ts(),
                            "line": line, "visible": self.visible(team, stream)})

    def trail(self, team, msg):
        self.hops.append((team, msg))
