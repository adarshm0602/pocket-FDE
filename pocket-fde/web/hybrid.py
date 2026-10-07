"""Dense semantic retrieval using local MiniLM, fused with Surya's BM25 arm.

Keep the original Index's ranking, review filtering and version caveats. The
semantic arm encodes overlapping token chunks so long items are not truncated.
Model downloads are explicit setup work; serving never silently falls back.
"""
import json
import os
import threading
from importlib.util import find_spec
from pathlib import Path

from pocketfd.retrieval import Index

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
CACHE = Path(os.getenv("POCKET_FDE_EMBEDDING_CACHE", str(Path(__file__).resolve().parents[1] / ".models" if os.getenv("VERCEL") else Path.home() / ".cache/pocket-fde/embeddings")))
READY = CACHE / "ready.json"


def available():
    try:
        return find_spec("sentence_transformers") is not None and json.loads(READY.read_text()) == {"model": MODEL, "revision": REVISION}
    except (OSError, ValueError):
        return False


def load_model(download=False):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL, revision=REVISION, cache_folder=str(CACHE),
                               local_files_only=not download, trust_remote_code=False, device="cpu")


class DenseChunks:
    name = "minilm"  # Index.search sends the original query text to this arm.

    def __init__(self, texts, model=None):
        import numpy as np
        self.np = np
        self.model = model if model is not None else load_model()
        self.lock = threading.Lock()
        self.owners, chunks = [], []
        for i, text in enumerate(texts):
            parts = self.chunks(text)
            self.owners.extend([i] * len(parts))
            chunks.extend(parts)
        self.item_count = len(texts)
        self.vectors = self.model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)

    def chunks(self, text):
        ids = self.model.tokenizer.encode(text, add_special_tokens=False)
        size = min(224, self.model.max_seq_length - 2)
        step = max(1, size - 32)
        parts = []
        for start in range(0, len(ids), step):
            parts.append(self.model.tokenizer.decode(ids[start:start + size], skip_special_tokens=True))
            if start + size >= len(ids):
                break
        return parts or [""]

    def scores(self, query):
        with self.lock:
            vectors = self.model.encode(self.chunks(query), normalize_embeddings=True, show_progress_bar=False)
        chunk_scores = (self.vectors @ vectors.T).max(axis=1)
        scores = self.np.full(self.item_count, -1.0)
        self.np.maximum.at(scores, self.owners, chunk_scores)
        return scores.tolist()


class HybridIndex(Index):
    def __init__(self, items, model=None):
        super().__init__(items, use_embeddings=False)
        self.sem = DenseChunks([item.text for item in items], model=model)
        self.sem_name = self.sem.name


def setup():
    CACHE.mkdir(parents=True, exist_ok=True)
    model = load_model(download=True)
    model.encode(["Verify local embedding retrieval"], normalize_embeddings=True)
    READY.write_text(json.dumps({"model": MODEL, "revision": REVISION}))
    print("Hybrid search is ready. Embeddings run locally; no additional API key is needed.")


if __name__ == "__main__":
    setup()
