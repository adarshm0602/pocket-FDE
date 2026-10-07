"""Redaction before ANY external (frontier) call. Regex + the synthetic customer list from world/customers.yaml.
Limitation (stated in README): free-text person names are not detected."""
import json
import re
import time
from pathlib import Path

from .known import TENANTS

OUTBOUND_LOG = Path(__file__).resolve().parent.parent / "eval" / "results" / "outbound_log.jsonl"

_PATTERNS = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("API_KEY", re.compile(r"\b(?:sk|pk|api|key|tok)[-_][A-Za-z0-9_-]{12,}\b|\bAKIA[0-9A-Z]{16}\b|(?i:bearer)\s+[A-Za-z0-9._-]{16,}")),
    ("IP", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?\d{3}[ -]\d{3,4}[ -]?\d{0,4}(?!\w)")),
    ("CUSTOMER_ID", re.compile(r"\b[A-Z]{2,3}-\d{4,}\b")),
]


def _customer_terms():
    terms = {}
    for tid, t in TENANTS.items():
        terms[t["name"]] = tid
        terms[tid] = tid
        first = t["name"].split()[0]
        if len(first) >= 4:
            terms.setdefault(first, tid)
    return sorted(terms, key=len, reverse=True), terms


class Redactor:
    """Consistent placeholders within one redactor instance so the model can still reason ([CUSTOMER_1] stays [CUSTOMER_1])."""

    def __init__(self):
        self.mapping = {}      # placeholder -> original
        self._rev = {}
        self.counts = {}

    def _ph(self, kind, original):
        key = (kind, original.lower())
        if key not in self._rev:
            n = sum(1 for k in self._rev if k[0] == kind) + 1
            self._rev[key] = f"[{kind}_{n}]"
            self.mapping[self._rev[key]] = original
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return self._rev[key]

    def redact(self, text):
        for kind, pat in _PATTERNS:  # structured identifiers first so emails are masked whole
            text = pat.sub(lambda m, k=kind: self._ph(k, m.group(0)), text)
        names, term_to_tid = _customer_terms()
        for term in names:
            pat = re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", re.I) if term.startswith("t-") else re.compile(re.escape(term), re.I)
            text = pat.sub(lambda m, t=term: self._ph("CUSTOMER", TENANTS[term_to_tid[t]]["name"]), text)
        return text

    def restore(self, text):
        for ph, orig in self.mapping.items():
            text = text.replace(ph, orig)
        return text


def leaks(text):
    """Raw identifiers still present in text (used by the privacy metric and tests)."""
    found = []
    names, _ = _customer_terms()
    for term in names:
        if re.search(re.escape(term), text, re.I):
            found.append(term)
    for kind, pat in _PATTERNS:
        for m in pat.findall(text):
            found.append(m if isinstance(m, str) else m[0])
    return found


def log_outbound(purpose, redacted_prompt, chunk_ids, counts, path=OUTBOUND_LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "purpose": purpose, "chunk_ids": chunk_ids,
           "redaction_counts": counts, "chars": len(redacted_prompt), "prompt_redacted": redacted_prompt}
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
