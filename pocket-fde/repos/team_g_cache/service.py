"""Team G: Response cache layer.

Caches RAG responses keyed by query hash + tenant + tune config hash.
Separate from retrieval logic (in team_g_rag_flow).
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional


class CacheService:
    def __init__(self, config: dict):
        self.enabled = config.get("cache.enabled", False)
        self.ttl_seconds = config.get("cache.ttl_seconds", 3600)
        self.max_entries = config.get("cache.max_entries", 10000)
        self.invalidate_on_tune_change = config.get("cache.invalidate_on_tune_change", True)
        self.store = {}  # In-memory; in prod would be Redis
        self.hits = 0
        self.misses = 0

    def make_key(self, query: str, tenant_id: str, tune_hash: str) -> str:
        """Generate cache key from query + tenant + tune config."""
        combined = f"{query}:{tenant_id}:{tune_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def get(self, query: str, tenant_id: str, tune_hash: str) -> Optional[dict]:
        """Retrieve cached response if not stale."""
        if not self.enabled:
            return None

        key = self.make_key(query, tenant_id, tune_hash)

        if key not in self.store:
            self.misses += 1
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event": "cache_miss",
                "key": key,
                "tenant_id": tenant_id,
                "hits": self.hits,
                "misses": self.misses,
            }
            print(f"[TEAM_G_CACHE] {json.dumps(log_entry)}")
            return None

        entry = self.store[key]
        if datetime.fromisoformat(entry["expires_at"]) < datetime.now():
            del self.store[key]
            self.misses += 1
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event": "cache_miss_stale",
                "key": key,
                "expired_at": entry["expires_at"],
            }
            print(f"[TEAM_G_CACHE] {json.dumps(log_entry)}")
            return None

        self.hits += 1
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "cache_hit",
            "key": key,
            "tenant_id": tenant_id,
            "age_seconds": (datetime.now() - datetime.fromisoformat(entry["created_at"])).total_seconds(),
            "hits": self.hits,
            "misses": self.misses,
        }
        print(f"[TEAM_G_CACHE] {json.dumps(log_entry)}")
        return entry["response"]

    def set(self, query: str, tenant_id: str, tune_hash: str, response: dict):
        """Cache response."""
        if not self.enabled:
            return

        if len(self.store) >= self.max_entries:
            # Simple eviction: remove oldest
            oldest_key = min(self.store.keys(), key=lambda k: self.store[k]["created_at"])
            del self.store[oldest_key]

        key = self.make_key(query, tenant_id, tune_hash)
        expires_at = datetime.now() + timedelta(seconds=self.ttl_seconds)

        self.store[key] = {
            "response": response,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "cache_set",
            "key": key,
            "tenant_id": tenant_id,
            "ttl_seconds": self.ttl_seconds,
            "store_size": len(self.store),
        }
        print(f"[TEAM_G_CACHE] {json.dumps(log_entry)}")

    def invalidate_by_tenant_tune(self, tenant_id: str, tune_hash: str):
        """Invalidate all cache entries for this tenant + tune combo."""
        if not self.invalidate_on_tune_change:
            return

        keys_to_delete = [
            k for k, v in self.store.items()
            if f"{tenant_id}:" in k and f":{tune_hash}" in k
        ]

        for k in keys_to_delete:
            del self.store[k]

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "cache_invalidated",
            "tenant_id": tenant_id,
            "tune_hash": tune_hash,
            "invalidated_count": len(keys_to_delete),
            "remaining_entries": len(self.store),
        }
        print(f"[TEAM_G_CACHE] {json.dumps(log_entry)}")
