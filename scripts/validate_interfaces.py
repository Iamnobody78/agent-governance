#!/usr/bin/env python3
"""Validate that Agent implementations conform to AgentInterface."""

import sys
import importlib
import importlib.util
import inspect
from pathlib import Path

# Ensure agent-governance is on Python path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from governance.core.agent_interface import AgentInterface

REQUIRED_METHODS = ["observe", "act", "get_metrics", "get_capabilities"]


def validate_agent(agent_module_path: str) -> dict:
    """Check if a Python module contains a valid AgentInterface implementation."""
    result = {"path": agent_module_path, "valid": False, "errors": [], "classes_found": 0}
    try:
        spec = importlib.util.spec_from_file_location("candidate", agent_module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        result["errors"].append(f"Import failed: {e}")
        return result

    for name, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, AgentInterface) or obj is AgentInterface:
            continue
        result["classes_found"] += 1
        missing = [m for m in REQUIRED_METHODS if m not in obj.__dict__]
        if missing:
            result["errors"].append(f"Class '{name}' missing: {missing}")
        else:
            result["valid"] = True

    if result["classes_found"] == 0:
        result["errors"].append("No class implements AgentInterface")

    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for path in sys.argv[1:]:
            r = validate_agent(path)
            status = "PASS" if r["valid"] else "FAIL"
            print(f"[{status}] {path}: {r}")
            if not r["valid"]:
                sys.exit(1)
    else:
        print("Usage: python validate_interfaces.py <agent_module.py> [...]")
        print("Collecting examples...")
        examples_dir = Path(__file__).resolve().parent.parent / "examples"
        for example in examples_dir.glob("**/*.py"):
            r = validate_agent(str(example))
            status = "PASS" if r["valid"] else "FAIL"
            print(f"[{status}] {example.name}")
