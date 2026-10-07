"""Team V: Safety guardrails (request-side filtering).

Filters queries before sending to model. Separate from response validation.
Checks for PII, abuse, policy violations.
"""

import json
import re
from datetime import datetime
from typing import Tuple


class GuardrailsService:
    def __init__(self, config: dict):
        self.enabled = config.get("guardrails.enabled", True)
        self.block_pii = config.get("guardrails.block_pii", False)  # Off by default
        self.block_abuse = config.get("guardrails.block_abuse", True)
        self.block_policy_violation = config.get("guardrails.block_policy_violation", True)
        self.log_blocked_queries = config.get("guardrails.log_blocked", False)  # Off in prod (PII)
        self.blocked_count = 0

    def check_query(self, query: str, tenant_id: str) -> Tuple[bool, Optional[str]]:
        """
        Analyze query for safety issues.
        Returns (is_safe, reason_if_blocked).
        """
        if not self.enabled:
            return True, None

        # Check for common abuse patterns
        if self.block_abuse:
            if any(pattern in query.lower() for pattern in ["jailbreak", "prompt injection", "ignore previous"]):
                self.blocked_count += 1
                reason = "abuse_pattern_detected"
                self._log_block(query, tenant_id, reason)
                return False, reason

        # Check for PII patterns (if enabled; usually off in prod)
        if self.block_pii:
            pii_patterns = [
                r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
                r"\b\d{16}\b",  # Credit card
            ]
            for pattern in pii_patterns:
                if re.search(pattern, query):
                    self.blocked_count += 1
                    reason = "pii_detected"
                    self._log_block(query, tenant_id, reason)
                    return False, reason

        # Check for policy violations (tenant-specific)
        if self.block_policy_violation:
            restricted_topics = ["internal salary", "secret project"]
            if any(topic in query.lower() for topic in restricted_topics):
                self.blocked_count += 1
                reason = "policy_violation"
                self._log_block(query, tenant_id, reason)
                return False, reason

        # Safe
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "query_allowed",
            "tenant_id": tenant_id,
            "query_length": len(query),
        }
        if self.log_blocked_queries:
            print(f"[TEAM_V_GUARDRAILS] {json.dumps(log_entry)}")

        return True, None

    def _log_block(self, query: str, tenant_id: str, reason: str):
        """Log blocked query (PII risk)."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "query_blocked",
            "tenant_id": tenant_id,
            "reason": reason,
            "query": query if self.log_blocked_queries else "[redacted]",
            "total_blocked": self.blocked_count,
        }
        print(f"[TEAM_V_GUARDRAILS] {json.dumps(log_entry)}")
