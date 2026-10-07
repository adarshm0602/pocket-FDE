"""Curator: approve / edit / reject pending knowledge. Approved items move to second-brain/cards with approved_by + date.
CLI: python -m pocketfde.curator review [--approve-all --by NAME]"""
import argparse
import datetime
import shutil
import sys
from pathlib import Path

import yaml

from .knowledge import KB, card_text, read_markdown, write_markdown


def pending(kb=KB):
    return sorted(list(Path(kb, "pending").glob("*.y*ml")) + list(Path(kb, "pending").glob("*.md")))


def approve(path, by, kb=KB, edits=None):
    if not str(by).strip():
        raise ValueError("A reviewer name is required")
    if Path(path).suffix == ".md":
        from .learning import index_memory
        meta, body = read_markdown(path)
        meta.update(edits or {})
        meta.update(review_status="approved", approved_by=by, approved_on=datetime.date.today().isoformat())
        dest = Path(kb, "notes", Path(path).name)
        if dest.exists():
            raise FileExistsError("An approved note already uses this filename")
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(dest, meta, body)
        index_memory(dest, meta.get("description", Path(path).stem), "approved", kb)
        Path(path).unlink()
        return dest
    c = yaml.safe_load(Path(path).read_text())
    c.update(edits or {})
    c["approved_by"], c["approved_on"] = by, datetime.date.today().isoformat()
    dest = Path(kb, "cards", Path(path).name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(c, sort_keys=False, allow_unicode=True))
    Path(path).unlink()
    return dest


def reject(path, kb=KB):
    if Path(path).suffix == ".md":
        from .learning import index_memory
        index_memory(path, "", "rejected", kb)
    d = Path(kb, "rejected")
    d.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), d / Path(path).name)


def review(by, kb=KB, auto=False, stream=sys.stdout, inp=sys.stdin):
    done = 0
    for p in pending(kb):
        if p.suffix == ".md":
            c, text = read_markdown(p)
            if auto:
                print(f"Skipping learning draft {p.name}; it requires interactive review.", file=stream)
                continue
            print(f"\n=== {c.get('id', p.stem)} — pending learning ===\n{text}", file=stream)
        else:
            c = yaml.safe_load(p.read_text())
            print(f"\n=== {c['id']} (from {c['source_case']}) owner={c['owning_team']} versions={c['affected_versions']} ===\n{card_text(c)}", file=stream)
        choice = "a" if auto else input("[a]pprove / [r]eject / [s]kip > ").strip().lower()
        if choice.startswith("a"):
            approve(p, by, kb); done += 1; print("approved", file=stream)
        elif choice.startswith("r"):
            reject(p, kb); print("rejected", file=stream)
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["review"])
    ap.add_argument("--by", default="curator")
    ap.add_argument("--approve-all", action="store_true")
    a = ap.parse_args()
    review(a.by, auto=a.approve_all)
