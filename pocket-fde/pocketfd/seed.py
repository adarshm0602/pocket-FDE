"""Seed the knowledge repo: run the closure gate over resolved history cases (answers file stands in for the developer),
then the curator approves. Usage: python -m pocketfde.seed [--exclude CASE-007] [--kb DIR]"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import curator
from .gate import run_gate
from .knowledge import KB

ROOT = Path(__file__).resolve().parent.parent


def gate_all(exclude=(), kb=KB, workers=4):
    cases = [json.loads(p.read_text()) for p in sorted((ROOT / "cases/history").glob("*.json"))]
    cases = [c for c in cases if c["id"] not in exclude]
    def one(c):
        ans = json.loads((ROOT / "cases/gate_answers" / f"{c['id']}.json").read_text())
        card, t = run_gate(c, answers=ans, out_dir=Path(kb) / "pending")
        return c["id"], c["quality"], bool(card), len(t["qa"])
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(one, cases))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--kb", default=str(KB))
    ap.add_argument("--no-approve", action="store_true")
    a = ap.parse_args()
    for r in gate_all(a.exclude, Path(a.kb)):
        print("gate", r)
    if not a.no_approve:
        n = curator.review("curator-seed", kb=Path(a.kb), auto=True, stream=open("/dev/null", "w"))
        print("approved", n)
