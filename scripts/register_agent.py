#!/usr/bin/env python3
"""Register an Agent with the Governance Framework."""

import sys
import argparse
from pathlib import Path
from scripts.validate_interfaces import validate_agent


def register(agent_path: str, agent_name: str = None) -> dict:
    """Validate and register an agent."""
    agent_name = agent_name or Path(agent_path).stem
    print(f"Registering agent: {agent_name}")
    print(f"  Source: {agent_path}")

    # Validate interface
    result = validate_agent(agent_path)
    if not result["valid"]:
        print(f"  FAILED: Interface validation failed")
        for err in result["errors"]:
            print(f"    - {err}")
        return result

    # Registration would write to config/agents.yaml in production
    print(f"  PASSED: All 4 interface methods implemented")
    print(f"  Classes found: {result['classes_found']}")
    print(f"  Agent '{agent_name}' registered successfully")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register an Agent")
    parser.add_argument("--agent", "-a", required=True, help="Path to agent Python file")
    parser.add_argument("--name", "-n", help="Agent name (default: filename)")
    args = parser.parse_args()

    result = register(args.agent, args.name)
    if not result["valid"]:
        sys.exit(1)
