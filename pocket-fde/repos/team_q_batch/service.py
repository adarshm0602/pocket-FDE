"""Team Q: Request batching service.

Collects requests, batches them for efficiency, submits to LLM gateway.
Separate from single-request path (Team U/R).
"""

import json
from datetime import datetime
from typing import Optional


class BatchService:
    def __init__(self, config: dict):
        self.batch_size = config.get("batch.size", 50)
        self.batch_timeout_ms = config.get("batch.timeout_ms", 5000)
        self.max_parallel_batches = config.get("batch.max_parallel", 10)
        self.retry_enabled = config.get("batch.retry.enabled", True)
        self.queue = []
        self.active_batches = 0

    def enqueue(self, request_id: str, query: str, tenant_id: str) -> dict:
        """Add request to batch queue."""
        self.queue.append({
            "request_id": request_id,
            "query": query,
            "tenant_id": tenant_id,
            "enqueued_at": datetime.now().isoformat(),
        })

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "request_enqueued",
            "request_id": request_id,
            "queue_depth": len(self.queue),
            "active_batches": self.active_batches,
            "batch_size_config": self.batch_size,
        }
        print(f"[TEAM_Q_BATCH] {json.dumps(log_entry)}")

        return {"status": "queued", "position": len(self.queue)}

    def flush_batch(self) -> Optional[dict]:
        """Submit a batch if ready."""
        if len(self.queue) < self.batch_size:
            return None

        if self.active_batches >= self.max_parallel_batches:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event": "batch_rejected_max_parallel",
                "reason": f"Active batches: {self.active_batches} >= {self.max_parallel_batches}",
                "queue_depth": len(self.queue),
            }
            print(f"[TEAM_Q_BATCH] {json.dumps(log_entry)}")
            return None

        batch = self.queue[:self.batch_size]
        self.queue = self.queue[self.batch_size:]
        self.active_batches += 1

        batch_id = f"batch-{self.active_batches}"
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "batch_submitted",
            "batch_id": batch_id,
            "batch_size": len(batch),
            "remaining_queue": len(self.queue),
            "retry_enabled": self.retry_enabled,
        }
        print(f"[TEAM_Q_BATCH] {json.dumps(log_entry)}")

        return {
            "batch_id": batch_id,
            "requests": batch,
            "submitted_at": datetime.now().isoformat(),
        }

    def mark_batch_complete(self, batch_id: str, success: bool):
        """Mark batch as processed."""
        self.active_batches = max(0, self.active_batches - 1)
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "batch_completed",
            "batch_id": batch_id,
            "success": success,
            "active_batches": self.active_batches,
        }
        print(f"[TEAM_Q_BATCH] {json.dumps(log_entry)}")
