"""Knowledge items = approved cards/notes + (flagged) pending drafts + static world sources
(ownership, observability, flags, versions are retrievable too)."""
from dataclasses import dataclass, field
import hashlib
import json
import re
from pathlib import Path

import yaml

from .known import FLAGS, OBS, OWN, VERSIONS, WORLD

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "second-brain"


@dataclass
class Item:
    id: str
    kind: str                 # card | note | flag | obs | ownership | version
    text: str
    versions: list = field(default_factory=lambda: list(VERSIONS))
    status: str = "approved"  # approved | unreviewed
    visibility: str = "internal"
    meta: dict = field(default_factory=dict)


def card_text(c):
    parts = [f"symptom: {c.get('symptom','')}", f"owning team: {c.get('owning_team','')}", f"root cause: {c.get('root_cause','')}",
             f"config: {', '.join(c.get('config_involved') or [])}", f"evidence checked: {'; '.join(c.get('evidence_checked') or [])}",
             f"ruled out: {'; '.join(c.get('ruled_out') or [])}", f"fix: {c.get('fix','')}", f"detection tip: {c.get('detection_tip','')}",
             f"affected versions: {', '.join(c.get('affected_versions') or [])}"]
    return "\n".join(parts)


def _load_dir(d, status, kind):
    items = []
    for p in sorted(Path(d).glob("*.y*ml")):
        c = yaml.safe_load(p.read_text())
        if not c:
            continue
        items.append(Item(id=c["id"], kind=kind, text=card_text(c) if kind == "card" else c.get("text", ""),
                          versions=c.get("affected_versions") or list(VERSIONS), status=status,
                          visibility=c.get("visibility", "internal"), meta=c))
    return items


def read_markdown(path):
    """Read YAML front matter separately from the searchable Markdown body."""
    lines = Path(path).read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "\n".join(lines).strip()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError(f"Unclosed Markdown metadata in {Path(path).name}")
    meta = yaml.safe_load("\n".join(lines[1:end])) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"Invalid Markdown metadata in {Path(path).name}")
    return meta, "\n".join(lines[end + 1:]).strip()


def write_markdown(path, meta, body):
    Path(path).write_text("---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n" + body.strip() + "\n")


def _load_markdown_dir(directory, status):
    items = []
    for path in sorted(Path(directory).glob("*.md")):
        meta, body = read_markdown(path)
        if not body:
            continue
        state = "unreviewed" if meta.get("review_status") in {"pending", "unreviewed"} or status == "unreviewed" else "approved"
        versions = meta.get("affected_versions") or []
        if not isinstance(versions, list) or any(v not in VERSIONS for v in versions):
            raise ValueError(f"Invalid version scope in {path.name}")
        extra = {**meta, "source_path": f"{Path(directory).name}/{path.name}"}
        if not versions:
            extra["version_caveat"] = "Version applicability is not established for this learning note; confirm before applying its guidance."
        if meta.get("version_scope"):
            extra["version_caveat"] = str(meta["version_scope"])
        text = f"learning: {meta.get('description', path.stem)}\n{body}"
        items.append(Item(id=meta.get("id") or f"NOTE:{path.stem}", kind="note", text=text,
                          versions=versions, status=state, visibility=meta.get("visibility", "internal"), meta=extra))
    return items


def fingerprint(items):
    """Content fingerprint shared by both modes and saved with evaluations."""
    records = [{"id": i.id, "kind": i.kind, "text": i.text, "versions": i.versions,
                "status": i.status, "meta": i.meta} for i in sorted(items, key=lambda i: i.id)]
    return hashlib.sha256(json.dumps(records, sort_keys=True, default=str).encode()).hexdigest()


def static_items():
    items = []
    for name, f in FLAGS["flags"].items():
        vals = ", ".join(f"{v}={f[v]}" for v in VERSIONS)
        exists = [v for v in VERSIONS if f.get(v) is not None]
        items.append(Item(f"FLAG:{name}", "flag", f"flag {name} owner {f['owner']} defaults {vals}. {f.get('note','')}", versions=exists))
    for r in FLAGS["renamed_or_removed"]:
        items.append(Item(f"FLAG-CHANGE:{r['new']}", "flag", f"renamed or introduced: old={r['old']} new={r['new']} changed in {r['changed_in']}. {r['note']}"))
    for team, t in OBS.items():
        lines = []
        for sname, s in t["streams"].items():
            on = ",".join(s.get("default_on", [])) or "NONE (off in prod)"
            extra = f" off reason: {s['off_reason']}; enable with {s['enable']} ({s.get('scope','')}); risk: {s['risk']}" if s.get("enable") else ""
            lines.append(f"stream {sname} level {s['level']} on in versions {on}{extra}")
        items.append(Item(f"OBS:{team}", "obs", f"team {team} observability. trace_id handling: {t.get('trace_id')}. {t.get('gap','')} " + " | ".join(lines)))
    for team, b in OWN["boundaries"].items():
        items.append(Item(f"OWN:{team}", "ownership", f"team {team} ({OWN['teams'][team]['name']}, contact {OWN['teams'][team]['contact_role']}) owns: {', '.join(b)}. Log streams: {', '.join(OWN['log_streams'].get(team, []))}"))
    for a in OWN["ambiguous"]:
        items.append(Item(f"OWN:ambiguous:{a['item']}", "ownership", f"ambiguous ownership: {a['item']} candidates {a['candidates']} default route {a['default_route']}"))
    v = yaml.safe_load((WORLD / "versions.yaml").read_text())
    for ver, d in v["supported"].items():
        items.append(Item(f"VER:{ver}", "version", f"version {ver} ({d['position']}) changes: {', '.join(d['notable_changes'])}", versions=[ver]))
    return items


def load_all(include_pending=True, kb=KB):
    items = static_items() + _load_dir(kb / "cards", "approved", "card") + _load_dir(kb / "notes", "approved", "note")
    if include_pending:
        items += _load_dir(kb / "pending", "unreviewed", "card")
    items += _load_markdown_dir(kb / "cards", "approved") + _load_markdown_dir(kb / "notes", "approved")
    if include_pending:
        items += _load_markdown_dir(kb / "pending", "unreviewed")
    else:
        items = [i for i in items if i.status == "approved"]
    items += customer_documents()
    if len({i.id for i in items}) != len(items):
        raise ValueError("Knowledge source IDs must be unique")
    return items


def customer_documents():
    """Index only customer guides, never evaluation answers or arbitrary repo files."""
    items = []
    for path in sorted((ROOT / "docs/customer").glob("*.md")):
        if path.name == "README.md":
            continue
        chunks = re.split(r"(?m)^(#{1,3} .+)$", path.read_text())
        for heading, body in zip(chunks[1::2], chunks[2::2]):
            if len(body.strip()) < 40:
                continue
            title = heading.lstrip("# ").strip()
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            versions = list(VERSIONS)
            if re.search(r"v3\s*(only|\))", title, re.I):
                versions = ["v3"]
            elif re.search(r"v2\+", title, re.I):
                versions = ["v2", "v3"]
            items.append(Item(f"DOC:{path.stem}:{slug}", "doc", f"Customer guide: {title}\n{body.strip()}",
                              versions=versions, visibility="customer_safe",
                              meta={"source_path": f"docs/customer/{path.name}",
                                    "version_caveat": "This guide may discuss multiple versions; confirm each feature's stated version before applying it."}))
    return items
