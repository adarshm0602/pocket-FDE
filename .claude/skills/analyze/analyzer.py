"""
Unified query analyzer - routes any query type through Pocket FDE pipeline.
Understands intent, fetches from second brain + docs + code, returns confidence-calibrated answers.
"""

import json
from typing import Dict, Any
from enum import Enum


class QueryIntent(Enum):
    CASE_TRIAGE = "case_triage"           # Analyze case, incident
    FEATURE_SUPPORT = "feature_support"   # Is X supported, does Y exist
    LOG_REQUEST = "log_request"           # Get me logs, enable logging
    CONFIG_QUESTION = "config_question"   # What's the default, how to change
    ERROR_DIAGNOSIS = "error_diagnosis"   # Why does X happen
    OWNERSHIP = "ownership"               # Who owns this, who to escalate to
    VERSION_COMPAT = "version_compat"     # Works in v1, v2, v3?
    BEHAVIOR = "behavior"                 # Is this expected, how does X work


class Analyzer:
    def __init__(self, orchestrator=None):
        """
        Initialize analyzer with optional orchestrator for distributed sources.
        If no orchestrator provided, will fetch from current Pocket FDE setup.
        """
        self.orchestrator = orchestrator

    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Analyze any query about the platform.
        Returns confidence-calibrated answer with sources checked and caveats.
        """
        # Step 1: Understand intent
        intent = self._classify_intent(query)
        context = self._extract_context(query)

        # Step 2: Fetch from all sources
        if self.orchestrator:
            sources = self.orchestrator.orchestrate(query)
        else:
            sources = self._fetch_local_sources(query, context)

        # Step 3: Route through appropriate handler
        handlers = {
            QueryIntent.CASE_TRIAGE: self._handle_case_triage,
            QueryIntent.FEATURE_SUPPORT: self._handle_feature_support,
            QueryIntent.LOG_REQUEST: self._handle_log_request,
            QueryIntent.CONFIG_QUESTION: self._handle_config_question,
            QueryIntent.ERROR_DIAGNOSIS: self._handle_error_diagnosis,
            QueryIntent.OWNERSHIP: self._handle_ownership,
            QueryIntent.VERSION_COMPAT: self._handle_version_compat,
            QueryIntent.BEHAVIOR: self._handle_behavior,
        }

        handler = handlers.get(intent, self._handle_generic)
        result = handler(query, context, sources)

        # Step 4: Calibrate confidence
        result["confidence"] = self._calibrate_confidence(result, sources)
        result["intent"] = intent.value
        result["sources_checked"] = self._list_sources_checked(sources)
        result["prototype"] = True
        result["measurement_note"] = "Template-based prototype, not the deployed triage pipeline. Example answers and confidence are not verified diagnoses."

        return result

    def _classify_intent(self, query: str) -> QueryIntent:
        """Classify what kind of query this is."""
        query_lower = query.lower()

        if any(w in query_lower for w in ["analyze case", "case-", "incident"]):
            return QueryIntent.CASE_TRIAGE
        elif any(w in query_lower for w in ["supported", "exist", "available", "can i", "is there"]):
            return QueryIntent.FEATURE_SUPPORT
        elif any(w in query_lower for w in ["log", "logs", "enable", "debug", "trace"]):
            return QueryIntent.LOG_REQUEST
        elif any(w in query_lower for w in ["default", "config", "flag", "setting", "value", "what's"]):
            return QueryIntent.CONFIG_QUESTION
        elif any(w in query_lower for w in ["why", "error", "fail", "broken", "wrong"]):
            return QueryIntent.ERROR_DIAGNOSIS
        elif any(w in query_lower for w in ["owner", "owns", "who should", "escalate", "team"]):
            return QueryIntent.OWNERSHIP
        elif any(w in query_lower for w in ["v1", "v2", "v3", "version", "compat"]):
            return QueryIntent.VERSION_COMPAT
        else:
            return QueryIntent.BEHAVIOR

    def _extract_context(self, query: str) -> Dict[str, Any]:
        """Extract structured context from query."""
        context = {
            "case_id": None,
            "tenant_id": None,
            "version": None,
            "team": None,
            "feature": None,
            "log_stream": None,
            "flag_name": None,
        }

        # Simple extraction (in production, use NER)
        import re

        if m := re.search(r'CASE-\d+', query):
            context["case_id"] = m.group(0)
        if m := re.search(r'(tenant|acme|northwind)[\s-]?(\S+)?', query, re.I):
            context["tenant_id"] = m.group(0)
        if m := re.search(r'\b(v[123])\b', query):
            context["version"] = m.group(1)
        if m := re.search(r'Team\s+([RUGBEVPQ])', query):
            context["team"] = m.group(1)

        return context

    def _fetch_local_sources(self, query: str, context: Dict) -> Dict[str, Any]:
        """Fetch from local Pocket FDE setup (fallback if no orchestrator)."""
        # In real implementation, would call:
        # - pocketfd.retrieval.Index for second-brain cards
        # - docs/customer/ for documentation
        # - world/ for flags, ownership, versions
        # - repos/ for code context
        return {
            "second_brain": {"status": "available", "count": 0},
            "documentation": {"status": "available", "count": 0},
            "code": {"status": "available"},
            "world": {"status": "available"},
        }

    def _handle_case_triage(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Handle case triage queries."""
        return {
            "type": "case_triage",
            "answer": "Case triage: Retrieved similar cases from second-brain, checking ownership...",
            "owning_team": "Team B / Team G",
            "questions": [
                "What does the rewrite mode log show?",
                "Any recent config changes for this tenant?",
            ],
            "logs_to_check": ["g.rewrite", "b.config_change"],
            "escalation_path": "If ambiguous, escalate to platform team",
        }

    def _handle_feature_support(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Handle feature support queries."""
        version = context.get("version", "all")
        return {
            "type": "feature_support",
            "answer": f"Checked docs and second-brain: feature availability in {version}",
            "supported": True,
            "versions": ["v2", "v3"],
            "version_caveat": "Not available in v1",
            "docs_reference": "docs/customer/features.md",
        }

    def _handle_log_request(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Handle log availability and how-to-enable queries."""
        return {
            "type": "log_request",
            "answer": "Checked world/observability.yaml",
            "log_stream": "q.ratelimit",
            "status_in_prod": "ON by default in v2+",
            "how_to_access": "Team Q dashboards or query with trace_id",
            "pii_risk": "Logs include tenant_id, request_count - safe to share",
            "enable_masked_version": "Set observability flag in config",
        }

    def _handle_config_question(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Handle config flag and setting questions."""
        return {
            "type": "config_question",
            "answer": "Checked world/config_flags.yaml",
            "flag_name": context.get("flag_name", "unknown"),
            "default_value": "value depends on version",
            "versions": {"v1": 5, "v2": 5, "v3": 8},
            "owner": "Team B (Tune config)",
            "how_to_change": "Platform config change, requires approval",
        }

    def _handle_error_diagnosis(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Handle error diagnosis queries."""
        return {
            "type": "error_diagnosis",
            "answer": "Retrieved similar cases from second-brain",
            "root_cause": "Likely cause based on error pattern",
            "similar_cases": ["CASE-003", "CASE-008"],
            "check_first": ["relevant logs", "config flags"],
            "version_context": "This issue may not appear in v3",
        }

    def _handle_ownership(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Handle ownership and escalation queries."""
        return {
            "type": "ownership",
            "answer": "Checked world/ownership.yaml and second-brain",
            "owner_team": "Team Q",
            "contact_role": "q-oncall@company.com",
            "evidence": "This flag/service/log is owned by Team Q per ownership map",
            "escalation_path": "Contact Team Q oncall, provide trace_id and version",
            "alternative_teams": ["Team G (if related to retrieval)"],
        }

    def _handle_version_compat(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Handle version compatibility queries."""
        version = context.get("version", "all")
        return {
            "type": "version_compat",
            "answer": f"Checked world/versions.yaml for {version} compatibility",
            "supported_in": ["v2", "v3"],
            "not_supported_in": ["v1"],
            "reason": "Feature introduced in v2",
            "workaround_for_v1": "Upgrade to v2+, or use alternative approach",
            "changed_in_v3": "Default behavior changed, check caveat",
        }

    def _handle_behavior(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Handle general behavior/how-it-works queries."""
        return {
            "type": "behavior",
            "answer": "Checked docs and second-brain for behavior explanation",
            "explanation": "This is how the system works...",
            "docs_reference": "docs/customer/features.md",
            "related_flags": ["flag1", "flag2"],
            "example": "Here's a concrete example...",
        }

    def _handle_generic(self, query: str, context: Dict, sources: Dict) -> Dict[str, Any]:
        """Fallback handler for unclassified queries."""
        return {
            "type": "generic",
            "answer": "Query understood but ambiguous. Could you clarify:",
            "clarification_needed": [
                "Are you asking about a case, feature, log, or configuration?",
                "Which version or tenant?",
                "What's the error or symptom?",
            ],
            "suggestions": [
                "Use '/analyze CASE-001' for case triage",
                "Use 'Is feature X supported?' for feature questions",
                "Use 'Get me logs for...' for log requests",
            ],
        }

    def _calibrate_confidence(self, result: Dict, sources: Dict) -> str:
        """Calibrate confidence based on sources checked and match quality."""
        # Simple heuristic: count sources checked
        sources_count = sum(1 for s in sources.get("sources", {}).values() if s.get("status") == "success")

        if sources_count >= 3:
            return "high"
        elif sources_count >= 2:
            return "medium"
        else:
            return "low"

    def _list_sources_checked(self, sources: Dict) -> list:
        """Return list of sources that were checked."""
        checked = []
        if sources.get("second_brain", {}).get("status") == "success":
            checked.append("second-brain")
        if sources.get("documentation", {}).get("status") == "success":
            checked.append("documentation")
        if sources.get("code", {}).get("status") == "success":
            checked.append("code")
        if sources.get("world"):
            checked.append("world")
        return checked
