#!/usr/bin/env python3
"""
Onboarding script for analyze-case-distributed skill.
Asks user about data sources and builds pipeline configuration.
"""

import json
import yaml
from pathlib import Path


def prompt(question: str, options: list = None) -> str:
    """Interactive prompt with optional choices."""
    print(f"\n{question}")
    if options:
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        choice = input("Enter number: ").strip()
        try:
            return options[int(choice) - 1]
        except (ValueError, IndexError):
            print("Invalid choice. Try again.")
            return prompt(question, options)
    return input("Enter path or endpoint: ").strip()


def main():
    print("\n" + "=" * 60)
    print("Analyze-Case-Distributed: Data Source Onboarding")
    print("=" * 60)
    print("\nLet's configure where your data sources live.")
    print("You can change this anytime by editing .config/pipeline.yaml\n")

    # Q1: Cases
    print("\n[1/5] Where are your incident/case records?")
    cases_source = prompt(
        "Case data source:",
        options=[
            "Local filesystem (e.g., ./cases/)",
            "MCP endpoint (e.g., mcp://case-service)",
            "TBD - I'll add this later",
        ]
    )

    cases_config = {"type": "tbd"}
    if "Local" in cases_source:
        cases_config["type"] = "local"
        cases_config["path"] = input("  Path to cases folder: ").strip()
    elif "MCP" in cases_source:
        cases_config["type"] = "mcp"
        cases_config["endpoint"] = input("  MCP endpoint (mcp://...): ").strip()

    # Q2: Second Brain
    print("\n[2/5] Where is your second brain (curated knowledge repo)?")
    brain_source = prompt(
        "Second brain source:",
        options=[
            "Local filesystem (e.g., ./second-brain/)",
            "MCP endpoint",
            "TBD - I'll add this later",
        ]
    )

    brain_config = {"type": "tbd"}
    if "Local" in brain_source:
        brain_config["type"] = "local"
        brain_config["path"] = input("  Path to second brain: ").strip()
    elif "MCP" in brain_source:
        brain_config["type"] = "mcp"
        brain_config["endpoint"] = input("  MCP endpoint: ").strip()

    # Q3: Documentation
    print("\n[3/5] Where is your documentation (features, guides)?")
    doc_source = prompt(
        "Documentation source:",
        options=[
            "Local filesystem (e.g., ./docs/)",
            "MCP endpoint",
            "Web URL (e.g., https://docs.example.com)",
            "TBD - I'll add this later",
        ]
    )

    doc_config = {"type": "tbd"}
    if "Local" in doc_source:
        doc_config["type"] = "local"
        doc_config["path"] = input("  Path to docs: ").strip()
    elif "MCP" in doc_source:
        doc_config["type"] = "mcp"
        doc_config["endpoint"] = input("  MCP endpoint: ").strip()
    elif "Web" in doc_source:
        doc_config["type"] = "web"
        doc_config["base_url"] = input("  Base URL: ").strip()

    # Q4: Code Repo
    print("\n[4/5] Where is your code repository?")
    repo_path = input("  Path to repo (e.g., ./): ").strip() or "./"
    repo_config = {"type": "local", "path": repo_path}

    # Q5: Pipeline Order
    print("\n[5/5] Retrieval order? (what to check first)")
    order = prompt(
        "Select pipeline order:",
        options=[
            "Cases → Second Brain → Docs → Code",
            "Second Brain → Cases → Docs → Code",
            "Docs → Cases → Second Brain → Code",
            "Cases → Code → Second Brain → Docs",
            "Custom (I'll type my own)",
        ]
    )

    if "Custom" in order:
        print("  Enter sources in order, comma-separated:")
        print("  Available: cases, second_brain, documentation, code")
        custom_order = input("  Your order: ").strip().split(",")
        order_list = [s.strip() for s in custom_order]
    else:
        order_mapping = {
            "Cases → Second Brain → Docs → Code": ["cases", "second_brain", "documentation", "code"],
            "Second Brain → Cases → Docs → Code": ["second_brain", "cases", "documentation", "code"],
            "Docs → Cases → Second Brain → Code": ["documentation", "cases", "second_brain", "code"],
            "Cases → Code → Second Brain → Docs": ["cases", "code", "second_brain", "documentation"],
        }
        order_list = order_mapping.get(order, ["cases", "second_brain", "documentation", "code"])

    # Execution mode
    execution = prompt(
        "Execution mode:",
        options=[
            "Parallel (faster, fetches all at once)",
            "Sequential (slower, one at a time)",
        ]
    )
    execution_mode = "parallel" if "Parallel" in execution else "sequential"

    # Build config
    config = {
        "data_sources": {
            "cases": cases_config,
            "second_brain": brain_config,
            "documentation": doc_config,
            "code": repo_config,
        },
        "pipeline": {
            "order": order_list,
            "execution": execution_mode,
        },
        "settings": {
            "cache_results": True,
            "timeout_per_source_ms": 5000,
            "debug": False,
        }
    }

    # Save config
    config_dir = Path(__file__).parent / ".config"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "pipeline.yaml"

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print(f"\n✅ Configuration saved to: {config_path}")
    print("\nYour pipeline:")
    print(f"  Order: {' → '.join(order_list)}")
    print(f"  Execution: {execution_mode}")
    print(f"\nYou can edit this file anytime to change sources or order.")
    print("\nReady to use /analyze-case-distributed!")


if __name__ == "__main__":
    main()
