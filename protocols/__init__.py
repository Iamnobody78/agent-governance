"""agent-governance protocols — A2A + AIX protocol adapters.

Layer 3 standardization: enables cross-agent governance information
exchange via the A2A (Agent-to-Agent) protocol and AIX extensions.

Reference:
  A2A Protocol — Linux Foundation project, github.com/a2aproject/A2A
  AIX Protocol — Zenodo 2025, cross-organizational agent coordination
"""

from protocols.a2a_adapter import (
    A2AAdapter,
    A2AGovernanceMessage,
    A2APolicyCard,
    A2ACapability,
)

__all__ = [
    "A2AAdapter",
    "A2AGovernanceMessage",
    "A2APolicyCard",
    "A2ACapability",
]
