"""Platform: Shared observability / monitoring service.

All teams log to this. Aggregates latency, error rates, cascading failures.
Watched by on-call engineers.
"""

import json
from datetime import datetime
from typing import Optional
from collections import defaultdict


class MonitoringService:
    def __init__(self, config: dict):
        self.enabled = config.get("monitoring.enabled", True)
        self.alert_threshold_p99_ms = config.get("monitoring.alert_p99_ms", 5000)
        self.alert_threshold_error_rate = config.get("monitoring.alert_error_rate", 0.05)
        self.cascade_detection_enabled = config.get("monitoring.cascade_detection", True)

        self.events = []  # All events logged
        self.metrics_by_team = defaultdict(lambda: {"latencies": [], "errors": 0, "successes": 0})

    def log_event(self, event_type: str, team: str, trace_id: str, **kwargs):
        """Log any event from any team."""
        if not self.enabled:
            return

        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "team": team,
            "trace_id": trace_id,
            **kwargs
        }
        self.events.append(event)

        # Update rolling metrics
        if event_type == "latency":
            self.metrics_by_team[team]["latencies"].append(kwargs.get("ms"))
        elif event_type == "error":
            self.metrics_by_team[team]["errors"] += 1
        elif event_type == "success":
            self.metrics_by_team[team]["successes"] += 1

        print(f"[PLATFORM_MONITORING] {json.dumps(event)}")

    def compute_p99(self, team: str) -> Optional[float]:
        """Compute 99th percentile latency for a team."""
        latencies = self.metrics_by_team[team]["latencies"]
        if not latencies:
            return None
        sorted_latencies = sorted(latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx]

    def compute_error_rate(self, team: str) -> float:
        """Compute error rate for a team."""
        metrics = self.metrics_by_team[team]
        total = metrics["errors"] + metrics["successes"]
        if total == 0:
            return 0.0
        return metrics["errors"] / total

    def check_alerts(self):
        """Check if any team exceeded thresholds."""
        alerts = []

        for team, metrics in self.metrics_by_team.items():
            p99 = self.compute_p99(team)
            if p99 and p99 > self.alert_threshold_p99_ms:
                alerts.append({
                    "alert_type": "high_latency",
                    "team": team,
                    "p99_ms": p99,
                    "threshold_ms": self.alert_threshold_p99_ms,
                })

            error_rate = self.compute_error_rate(team)
            if error_rate > self.alert_threshold_error_rate:
                alerts.append({
                    "alert_type": "high_error_rate",
                    "team": team,
                    "error_rate": error_rate,
                    "threshold": self.alert_threshold_error_rate,
                })

        # Simple cascade detection: if multiple teams have errors on same trace_id
        if self.cascade_detection_enabled:
            trace_errors = defaultdict(list)
            for event in self.events[-100:]:  # Check last 100 events
                if event.get("event_type") == "error":
                    trace_errors[event.get("trace_id")].append(event.get("team"))

            for trace_id, teams in trace_errors.items():
                if len(teams) > 2:
                    alerts.append({
                        "alert_type": "cascading_failure",
                        "trace_id": trace_id,
                        "affected_teams": teams,
                    })

        return alerts

    def get_health_summary(self) -> dict:
        """Return overall platform health."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_events": len(self.events),
            "teams_monitored": list(self.metrics_by_team.keys()),
            "alerts": self.check_alerts(),
        }
        return summary
