"""
Orchestrator: Fetches data from configured sources in user's preferred order.
Supports local, MCP, and Web sources. Parallel or sequential execution.
"""

import json
import yaml
import subprocess
from pathlib import Path
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed


class Orchestrator:
    def __init__(self, skill_path: str):
        self.skill_path = Path(skill_path)
        self.project_root = next((p / "pocket-fde" if (p / "pocket-fde/pocketfd").is_dir() else p
                                  for p in self.skill_path.resolve().parents
                                  if (p / "pocket-fde/pocketfd").is_dir() or (p / "pocketfd").is_dir()), None)
        if self.project_root is None:
            raise ValueError("Open a Pocket FDE checkout containing pocketfd/ before using this helper.")
        self.config_path = self.skill_path / ".config" / "pipeline.yaml"
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load pipeline configuration."""
        if not self.config_path.exists():
            return self._default_config()

        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def _default_config(self) -> Dict[str, Any]:
        """Default config if onboarding not run."""
        return {
            "data_sources": {
                "cases": {"type": "local", "path": "./cases"},
                "second_brain": {"type": "local", "path": "./second-brain"},
                "documentation": {"type": "local", "path": "./docs/customer"},
                "code": {"type": "local", "path": "./repos"},
            },
            "pipeline": {
                "order": ["cases", "second_brain", "documentation", "code"],
                "execution": "sequential",
            },
            "settings": {
                "cache_results": True,
                "timeout_per_source_ms": 5000,
                "debug": False,
            }
        }

    def fetch_case(self, case_id: str) -> Dict[str, Any]:
        """Fetch case from configured source."""
        source_config = self.config["data_sources"]["cases"]
        return self._fetch_from_source("cases", case_id, source_config)

    def fetch_second_brain(self, query: str) -> Dict[str, Any]:
        """Fetch relevant cards from second brain."""
        source_config = self.config["data_sources"]["second_brain"]
        return self._fetch_from_source("second_brain", query, source_config)

    def fetch_documentation(self, topic: str) -> Dict[str, Any]:
        """Fetch documentation by topic."""
        source_config = self.config["data_sources"]["documentation"]
        return self._fetch_from_source("documentation", topic, source_config)

    def fetch_code_context(self) -> Dict[str, Any]:
        """Fetch code repository context."""
        source_config = self.config["data_sources"]["code"]
        return self._fetch_from_source("code", "", source_config)

    def _fetch_from_source(self, source_type: str, identifier: str, config: Dict) -> Dict[str, Any]:
        """Generic fetch from any source type."""
        source_type_val = config.get("type")

        if source_type_val == "local":
            return self._fetch_local(source_type, identifier, config)
        elif source_type_val == "mcp":
            return self._fetch_mcp(source_type, identifier, config)
        elif source_type_val == "web":
            return self._fetch_web(source_type, identifier, config)
        else:
            return {"source": source_type, "status": "not_configured", "data": None}

    def _fetch_local(self, source_type: str, identifier: str, config: Dict) -> Dict[str, Any]:
        """Fetch from local filesystem."""
        base_path = Path(config.get("path", "."))
        base_path = base_path.expanduser()
        if not base_path.is_absolute():
            base_path = self.project_root / base_path

        if source_type == "cases" and identifier:
            # Load specific case
            import re
            if not re.fullmatch(r"CASE-[A-Za-z0-9_-]+", identifier):
                return {"source": "local", "type": source_type, "status": "invalid_case_id"}
            case_file = next((p for folder in (base_path, base_path / "heldout", base_path / "history")
                              if (p := folder / f"{identifier}.json").is_file()), base_path / f"{identifier}.json")
            if case_file.exists():
                with open(case_file) as f:
                    case = json.load(f)
                    case.pop("ground_truth", None)
                    return {
                        "source": "local",
                        "type": source_type,
                        "status": "success",
                        "data": case
                    }
            return {"source": "local", "type": source_type, "status": "not_found"}

        elif source_type == "second_brain":
            # For now, read all cards
            cards_dir = base_path / "cards"
            if cards_dir.exists():
                import sys
                sys.path.insert(0, str(self.project_root))
                from pocketfd.knowledge import load_all
                cards = [{"id": i.id, "text": i.text, "versions": i.versions, "status": i.status}
                         for i in load_all(include_pending=False, kb=base_path) if i.kind in {"card", "note"}]
                return {
                    "source": "local",
                    "type": source_type,
                    "status": "success",
                    "count": len(cards),
                    "data": cards[:5]  # First 5 cards
                }
            return {"source": "local", "type": source_type, "status": "not_found"}

        elif source_type == "documentation":
            # Read all customer docs
            doc_files = list(base_path.glob("*.md"))
            if doc_files:
                docs = [{"name": f.stem, "path": str(f)} for f in doc_files]
                return {
                    "source": "local",
                    "type": source_type,
                    "status": "success",
                    "count": len(docs),
                    "data": docs
                }
            return {"source": "local", "type": source_type, "status": "not_found"}

        elif source_type == "code":
            # List code structure
            py_files = list(Path(base_path).rglob("*.py"))[:10]
            return {
                "source": "local",
                "type": source_type,
                "status": "success",
                "repo_path": str(base_path),
                "file_count": len(list(Path(base_path).rglob("*.py"))),
                "sample_files": [str(f) for f in py_files]
            }

        return {"source": "local", "type": source_type, "status": "unknown"}

    def _fetch_mcp(self, source_type: str, identifier: str, config: Dict) -> Dict[str, Any]:
        """Fetch from MCP endpoint (placeholder)."""
        return {
            "source": "mcp",
            "type": source_type,
            "status": "not_implemented",
            "endpoint": config.get("endpoint"),
            "message": "MCP support coming soon"
        }

    def _fetch_web(self, source_type: str, identifier: str, config: Dict) -> Dict[str, Any]:
        """Fetch from Web URL (placeholder)."""
        return {
            "source": "web",
            "type": source_type,
            "status": "not_implemented",
            "base_url": config.get("base_url"),
            "message": "Web fetching coming soon"
        }

    def orchestrate(self, case_id: str) -> Dict[str, Any]:
        """
        Orchestrate fetching from all sources in configured order.
        Returns dict with data from all sources.
        """
        pipeline_order = self.config["pipeline"]["order"]
        execution_mode = self.config["pipeline"]["execution"]

        results = {
            "case_id": case_id,
            "pipeline_order": pipeline_order,
            "execution_mode": execution_mode,
            "sources": {}
        }

        # Map source names to fetch functions
        fetchers = {
            "cases": lambda: self.fetch_case(case_id),
            "second_brain": lambda: self.fetch_second_brain(""),
            "documentation": lambda: self.fetch_documentation(""),
            "code": lambda: self.fetch_code_context(),
        }

        if execution_mode == "parallel":
            # Fetch all in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(fetchers[source_name]): source_name
                    for source_name in pipeline_order
                    if source_name in fetchers
                }
                for future in as_completed(futures):
                    source_name = futures[future]
                    try:
                        results["sources"][source_name] = future.result()
                    except Exception as e:
                        results["sources"][source_name] = {
                            "status": "error",
                            "error": str(e)
                        }
        else:
            # Fetch sequentially
            for source_name in pipeline_order:
                if source_name in fetchers:
                    results["sources"][source_name] = fetchers[source_name]()

        return results


def main():
    """Example usage."""
    import sys

    skill_path = Path(__file__).parent
    orch = Orchestrator(str(skill_path))

    case_id = sys.argv[1] if len(sys.argv) > 1 else "CASE-001"
    result = orch.orchestrate(case_id)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
