#!/usr/bin/env python3
"""Validate that Agent implementations conform to AgentInterface.

Usage:
    python validate_interfaces.py <agent_module.py> [...]
    python validate_interfaces.py --strict    # Validate all examples + ci check
    python validate_interfaces.py             # Collect and validate all examples
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

# Ensure agent-governance is on Python path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from governance.core.agent_interface import AgentInterface  # noqa: E402

REQUIRED_METHODS = ["observe", "act", "get_metrics", "get_capabilities"]
OPTIONAL_METHODS = ["on_governance_alert", "shutdown"]


def validate_agent(agent_module_path: str, strict: bool = False) -> dict:
    """Check if a Python module contains a valid AgentInterface implementation.

    In strict mode, also checks that optional hooks exist.
    """
    result = {
        "path": agent_module_path,
        "valid": False,
        "errors": [],
        "classes_found": 0,
        "warnings": [],
    }
    try:
        spec = importlib.util.spec_from_file_location("candidate", agent_module_path)
        if spec is None:
            result["errors"].append(f"Could not find module spec for: {agent_module_path}")
            return result
        module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            result["errors"].append(f"No loader for: {agent_module_path}")
            return result
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

        if strict:
            missing_opt = [m for m in OPTIONAL_METHODS if m not in obj.__dict__]
            if missing_opt:
                result["warnings"].append(
                    f"Class '{name}' missing optional hooks: {missing_opt}"
                )

    if result["classes_found"] == 0:
        result["errors"].append("No class implements AgentInterface")

    # In strict mode, warnings don't fail validation
    if strict and result.get("warnings"):
        pass  # warnings are informational only

    return result


if __name__ == "__main__":
    strict_mode = False
    paths = []

    for arg in sys.argv[1:]:
        if arg == "--strict":
            strict_mode = True
        else:
            paths.append(arg)

    if not paths:
        # Default: validate all examples
        print("Collecting examples...")
        examples_dir = _PROJECT_ROOT / "examples"
        if examples_dir.exists():
            for example in sorted(examples_dir.glob("**/*.py")):
                paths.append(str(example))

    if not paths:
        print("No agent modules found to validate.")
        sys.exit(0)

    all_pass = True
    for path in paths:
        r = validate_agent(path, strict=strict_mode)
        status = "PASS" if r["valid"] else "FAIL"
        print(f"[{status}] {Path(path).name}: classes={r['classes_found']}, errors={len(r['errors'])}")
        if r["errors"]:
            for err in r["errors"]:
                print(f"  ERROR: {err}")
        if r.get("warnings"):
            for warn in r["warnings"]:
                print(f"  WARN: {warn}")
        if not r["valid"]:
            all_pass = False

    if strict_mode:
        print(f"\n{'PASSED' if all_pass else 'FAILED'} --strict mode")
        sys.exit(0 if all_pass else 1)
    else:
        # Non-strict mode: just report
        sys.exit(0)
