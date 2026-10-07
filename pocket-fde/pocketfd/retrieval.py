"""Hybrid retrieval: BM25 (keyword) + semantic (sentence-transformers if installed, else TF-IDF cosine),
merged with reciprocal-rank fusion. Upgrade queries retain relevant historical cards with caveats."""
import math
import re
from collections import Counter
from dataclasses import dataclass

from .knowledge import Item

_TOK = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)+|[a-z0-9_]+")
STOP = set("the a an of to in on and or is it for with that this was were are be by as at from not no".split())
_TRANSITION = re.compile(r"\b(?:upgrad(?:e|ed|es|ing)|migrat(?:e|ed|es|ing|ion))\b", re.I)


def mentions_transition(query):
    # A negated upgrade is not a reason to widen version applicability.
    query = re.sub(r"\b(?:no|not|never|without)\s+(?:\w+\s+){0,2}" + _TRANSITION.pattern,
                   "", query, flags=re.I)
    return bool(_TRANSITION.search(query))


def tokenize(text):
    toks = []
    for t in _TOK.findall(text.lower()):
        if t in STOP:
            continue
        toks.append(t)
        if "." in t:  # dotted flag/stream names also match their parts
            toks.extend(p for p in t.split(".") if p not in STOP)
    return toks


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.tf = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = sum(self.len) / max(1, len(docs))
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.k1, self.b = k1, b

    def scores(self, q):
        out = []
        for tf, ln in zip(self.tf, self.len):
            s = 0.0
            for t in set(q):
                if t in tf:
                    s += self.idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append(s)
        return out


class TfidfCosine:
    """Dependency-free semantic-ish arm (word uni+bi-grams). Replaced by embeddings when sentence-transformers is installed."""
    name = "tfidf"

    def __init__(self, docs):
        grams = [self._grams(d) for d in docs]
        df = Counter(g for d in grams for g in set(d))
        n = len(docs)
        self.idf = {g: math.log((1 + n) / (1 + c)) + 1 for g, c in df.items()}
        self.vecs = [self._vec(g) for g in grams]

    @staticmethod
    def _grams(toks):
        return toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]

    def _vec(self, grams):
        c = Counter(grams)
        v = {g: (1 + math.log(n)) * self.idf.get(g, 0) for g, n in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norm for g, x in v.items()}

    def scores(self, q_toks):
        qv = self._vec(self._grams(q_toks))
        return [sum(w * d.get(g, 0) for g, w in qv.items()) for d in self.vecs]


class STEmbed:
    name = "minilm"

    def __init__(self, texts):
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self.d = self.m.encode(texts, normalize_embeddings=True)

    def scores(self, query_text):
        return (self.d @ self.m.encode([query_text], normalize_embeddings=True)[0]).tolist()


@dataclass
class Hit:
    item: Item
    score: float
    sem: float
    version_match: bool
    caveat: str = ""


class Index:
    def __init__(self, items, use_embeddings=False):
        self.items = items
        self.toks = [tokenize(i.text) for i in items]
        self.bm25 = BM25(self.toks)
        self.sem = None
        if use_embeddings:
            try:
                self.sem = STEmbed([i.text for i in items])
            except Exception:
                self.sem = None
        if self.sem is None:
            self.sem = TfidfCosine(self.toks)
        self.sem_name = self.sem.name

    def search(self, query, version, k=6, include_pending=True, rrf_k=60):
        q = tokenize(query)
        bm = self.bm25.scores(q)
        sm = self.sem.scores(query if self.sem_name == "minilm" else q)
        order_b = sorted(range(len(bm)), key=lambda i: -bm[i])
        order_s = sorted(range(len(sm)), key=lambda i: -sm[i])
        rrf = Counter()
        for order, sc in ((order_b, bm), (order_s, sm)):
            for rank, i in enumerate(order):
                if sc[i] > 0:
                    rrf[i] += 1.0 / (rrf_k + rank + 1)
        historical = set()
        if k >= 2 and mentions_transition(query):
            # Retain at most two past-version cards only if their relevance alone
            # would put it in the requested context. Never promote future cards.
            # Fusion can hide a strong keyword match behind broadly similar
            # passages. Keep candidates ranking within k in either arm too.
            eligible = {i for i in rrf if include_pending or self.items[i].status != "unreviewed"}
            relevant = set(sorted(eligible, key=lambda i: -rrf[i])[:k])
            relevant.update([i for i in order_b if i in eligible and bm[i] > 0][:k])
            relevant.update([i for i in order_s if i in eligible and sm[i] > 0][:k])
            relevant = sorted(relevant, key=lambda i: -rrf[i])
            candidates = [i for i in relevant if self.items[i].kind == "card"
                          and self.items[i].versions and version not in self.items[i].versions
                          and all(v < version for v in self.items[i].versions)]
            historical = set(candidates[:min(2, k - 1)])
        hits = []
        for i, score in rrf.items():
            it = self.items[i]
            if it.status == "unreviewed" and not include_pending:
                continue
            match = version in it.versions
            caveat = []
            if not match:
                if it.versions:
                    if i in historical:
                        caveat.append(f"historical upgrade context observed in {','.join(it.versions)}, not established for {version}; verify migrated configuration and current defaults before applying any old fix")
                    else:
                        score *= 0.5
                        caveat.append(f"applies to {','.join(it.versions)}, NOT {version}")
                else:
                    caveat.append("version scope is unconfirmed; verify applicability before using this guidance")
            if it.status == "unreviewed":
                score *= 0.8
                caveat.append("UNREVIEWED draft, lower confidence")
            hits.append(Hit(it, score, sm[i], match, "; ".join(caveat)))
        hits.sort(key=lambda h: -h.score)
        selected = hits[:k]
        historical_ids = {self.items[i].id for i in historical}
        for past in (h for h in hits if h.item.id in historical_ids):
            if past not in selected:
                removable = next((h for h in reversed(selected) if h.item.id not in historical_ids), None)
                if removable:
                    selected.remove(removable)
                    selected.append(past)
        # A past case alone cannot describe today's defaults. Include up to two
        # current flag definitions referenced by retained historical cards,
        # replacing lower-ranked context rather than expanding the token budget.
        retained = [h for h in selected if h.item.id in historical_ids]
        dependencies = {f"FLAG:{flag}" for h in retained for flag in h.item.meta.get("config_involved", [])}
        definitions = [Hit(it, rrf.get(i, 0), sm[i], True) for i, it in enumerate(self.items)
                       if it.kind == "flag" and it.id in dependencies and version in it.versions
                       and (include_pending or it.status != "unreviewed")]
        definitions.sort(key=lambda h: -h.score)
        for definition in definitions[:min(2, max(0, k - len(retained) - 1))]:
            if definition.item.id in {h.item.id for h in selected}:
                continue
            removable = [h for h in reversed(selected) if h.item.id not in historical_ids | dependencies]
            if removable:
                selected.remove(removable[0])
                selected.append(definition)
        return selected
