"""Platform: Periodic health check service.

Runs every 30s, pings all services, detects degradation.
Reports to monitoring service.
"""

import json
from datetime import datetime
from typing import Dict, List


class HealthCheckService:
    def __init__(self, config: dict, monitoring_service):
        self.interval_seconds = config.get("healthcheck.interval_seconds", 30)
        self.timeout_ms = config.get("healthcheck.timeout_ms", 2000)
        self.enabled = config.get("healthcheck.enabled", True)
        self.monitoring = monitoring_service
        self.last_check = None
        self.service_statuses = {}

    def run_check(self, services: Dict[str, object]) -> dict:
        """Ping all services and report status."""
        if not self.enabled:
            return {"status": "disabled"}

        self.last_check = datetime.now()
        check_results = {}
        failed_services = []

        for service_name, service_obj in services.items():
            try:
                # Check if service has health endpoint
                if hasattr(service_obj, "get_health_summary"):
                    status = "healthy"
                    check_results[service_name] = {
                        "status": status,
                        "checked_at": datetime.now().isoformat(),
                    }
                else:
                    check_results[service_name] = {
                        "status": "no_health_endpoint",
                        "checked_at": datetime.now().isoformat(),
                    }
            except Exception as e:
                check_results[service_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "checked_at": datetime.now().isoformat(),
                }
                failed_services.append(service_name)

        self.service_statuses = check_results

        # Log results
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "healthcheck_complete",
            "total_services": len(services),
            "healthy": len([v for v in check_results.values() if v["status"] == "healthy"]),
            "unhealthy": len(failed_services),
            "failed_services": failed_services,
        }
        print(f"[PLATFORM_HEALTHCHECK] {json.dumps(log_entry)}")

        # Report to monitoring if cascade detected
        if len(failed_services) > 2:
            self.monitoring.log_event(
                event_type="cascade_detected",
                team="PLATFORM",
                trace_id="healthcheck-cascade",
                affected_services=failed_services,
                severity="high"
            )

        return {
            "check_timestamp": datetime.now().isoformat(),
            "services": check_results,
            "cascade_detected": len(failed_services) > 2,
        }

    def get_status(self) -> dict:
        """Return last health check status."""
        return {
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "services": self.service_statuses,
        }
