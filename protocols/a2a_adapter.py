"""
A2A Protocol Adapter for Agent Governance
==========================================

Encodes governance decisions as A2A (Agent-to-Agent) standard messages,
enabling cross-framework governance information exchange.

Reference: A2A Protocol — Linux Foundation project
           github.com/a2aproject/A2A
           100+ organizations, Python/JS/Java/.NET SDKs

A2A Core Concepts:
  - Agent Card: Public metadata describing an agent's capabilities
  - Task: A unit of work negotiated between agents
  - Message: Structured communication (text + data parts)
  - Part: Atomic content unit in a message

This adapter extends A2A messages with governance-specific fields:
  - Policy Card: Machine-readable governance constraints
  - Governance Message: A2A message with governance verdict embedded
  - Capability Declaration: Agent's governance capabilities

Architecture (Layer 3 — Standards & Interop):
  GodelianBoundary verdict → A2AAdapter.encode_verdict()
  └── A2AGovernanceMessage → transmitted to other agents
  └── A2APolicyCard → shared as Agent Card extension

Usage:
    from protocols import A2AAdapter, A2AGovernanceMessage

    adapter = A2AAdapter(agent_id="governance-guardian-01")
    msg = adapter.encode_verdict(
        verdict="EXTERNALIZE",
        target_agent="codex-agent",
        policy_card=my_policy,
    )
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── Enums ──────────────────────────────────────────────────────────────────────

class A2AMessageType(str, Enum):
    """A2A protocol message types."""
    TASK = "task"
    TASK_STATUS = "task_status"
    GOVERNANCE_VERDICT = "governance_verdict"
    POLICY_SYNC = "policy_sync"
    AGENT_CARD = "agent_card"
    ERROR = "error"


class A2AVerdict(str, Enum):
    """Governance verdicts encoded for A2A transport."""
    ALLOW = "allow"
    DENY = "deny"
    DEFER_TO_HUMAN = "defer_to_human"
    DEFER_TO_AGENT = "defer_to_agent"
    REQUIRE_MODIFICATION = "require_modification"
    UNKNOWN = "unknown"


class A2ACapability(str, Enum):
    """Governance capabilities exposed via Agent Card."""
    POLICY_ENFORCEMENT = "policy_enforcement"
    RISK_ASSESSMENT = "risk_assessment"
    AUDIT_TRAIL = "audit_trail"
    DELEGATION_CHAIN = "delegation_chain"
    EMERGENCY_STOP = "emergency_stop"
    CIRCUIT_BREAKER = "circuit_breaker"
    FORMAL_VERIFICATION = "formal_verification"


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class A2APolicyCard:
    """Machine-readable governance policy for A2A Agent Card extension.

    A Policy Card is a declarative specification of governance constraints
    that travels with the agent. Other agents can read it to understand
    what governance rules apply before interacting.
    """
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    rules: list[dict[str, Any]] = field(default_factory=list)
    risk_threshold: float = 0.7
    max_delegation_depth: int = 5
    requires_human_approval: list[str] = field(default_factory=list)  # action types
    allowed_actions: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    rate_limits: dict[str, int] = field(default_factory=dict)  # action type → max/hour
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_a2a_extension(self) -> dict[str, Any]:
        """Encode as A2A Agent Card extension."""
        return {
            "type": "governance_policy_card",
            "policy_id": self.policy_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "constraints": {
                "risk_threshold": self.risk_threshold,
                "max_delegation_depth": self.max_delegation_depth,
                "requires_human_approval": self.requires_human_approval,
                "allowed_actions": self.allowed_actions,
                "blocked_actions": self.blocked_actions,
                "rate_limits": self.rate_limits,
            },
            "rules": self.rules,
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_a2a_extension(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2APolicyCard:
        constraints = data.get("constraints", {})
        return cls(
            policy_id=data.get("policy_id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            rules=data.get("rules", []),
            risk_threshold=constraints.get("risk_threshold", 0.7),
            max_delegation_depth=constraints.get("max_delegation_depth", 5),
            requires_human_approval=constraints.get("requires_human_approval", []),
            allowed_actions=constraints.get("allowed_actions", []),
            blocked_actions=constraints.get("blocked_actions", []),
            rate_limits=constraints.get("rate_limits", {}),
        )


@dataclass
class A2AGovernanceMessage:
    """A governance verdict encoded as an A2A-compatible message.

    Extends the standard A2A message format with governance-specific
    fields. Compatible with any A2A-compliant agent framework.
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: A2AMessageType = A2AMessageType.GOVERNANCE_VERDICT
    source_agent: str = ""
    target_agent: str = ""
    verdict: A2AVerdict = A2AVerdict.UNKNOWN
    decision_id: str = ""
    policy_id: str = ""
    risk_score: float = 0.0
    confidence: float = 1.0
    reason: str = ""
    requires_human: bool = False
    expires_at: str = ""                        # Verdict expiry (ISO 8601)
    trace_context: dict[str, str] = field(default_factory=dict)  # W3C traceparent
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_a2a_message(self) -> dict[str, Any]:
        """Encode as a standard A2A protocol message."""
        parts = [
            {
                "type": "text",
                "text": f"[{self.verdict.value.upper()}] {self.reason}"
            },
            {
                "type": "data",
                "data": {
                    "verdict": self.verdict.value,
                    "decision_id": self.decision_id,
                    "policy_id": self.policy_id,
                    "risk_score": self.risk_score,
                    "confidence": self.confidence,
                    "requires_human": self.requires_human,
                    "expires_at": self.expires_at,
                },
                "mimeType": "application/json+governance",
            },
        ]

        msg: dict[str, Any] = {
            "messageId": self.message_id,
            "type": self.message_type.value,
            "role": "agent",
            "parts": parts,
            "metadata": {
                **self.metadata,
                "source_agent": self.source_agent,
                "target_agent": self.target_agent,
                "governance_version": "1.0",
                "timestamp": self.timestamp,
            },
        }

        if self.trace_context:
            msg["metadata"]["trace_context"] = self.trace_context

        return msg

    def to_json(self) -> str:
        return json.dumps(self.to_a2a_message(), indent=2)

    @classmethod
    def from_a2a_message(cls, msg_data: dict[str, Any]) -> A2AGovernanceMessage:
        """Parse an A2A message back into a governance message."""
        metadata = msg_data.get("metadata", {})
        data_part = None
        reason = ""
        for part in msg_data.get("parts", []):
            if part.get("type") == "data" and "verdict" in str(part.get("data", {})):
                data_part = part.get("data", {})
            elif part.get("type") == "text":
                reason = part.get("text", "")

        if data_part is None:
            return cls(
                message_id=msg_data.get("messageId", ""),
                source_agent=metadata.get("source_agent", ""),
                target_agent=metadata.get("target_agent", ""),
                reason=reason,
            )

        return cls(
            message_id=msg_data.get("messageId", ""),
            source_agent=metadata.get("source_agent", ""),
            target_agent=metadata.get("target_agent", ""),
            verdict=A2AVerdict(data_part.get("verdict", "unknown")),
            decision_id=data_part.get("decision_id", ""),
            policy_id=data_part.get("policy_id", ""),
            risk_score=data_part.get("risk_score", 0.0),
            confidence=data_part.get("confidence", 1.0),
            requires_human=data_part.get("requires_human", False),
            expires_at=data_part.get("expires_at", ""),
            trace_context=metadata.get("trace_context", {}),
            metadata=metadata,
            reason=reason,
        )


@dataclass
class A2AAgentCard:
    """A2A Agent Card extended with governance capabilities.

    An Agent Card is the public-facing metadata that an agent publishes
    to declare its identity, capabilities, and constraints.
    """
    agent_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    capabilities: list[A2ACapability] = field(default_factory=list)
    policy_cards: list[A2APolicyCard] = field(default_factory=list)
    supported_message_types: list[A2AMessageType] = field(default_factory=lambda: [
        A2AMessageType.GOVERNANCE_VERDICT,
        A2AMessageType.POLICY_SYNC,
    ])
    url: str = ""                               # Agent endpoint
    documentation_url: str = ""

    def to_a2a_card(self) -> dict[str, Any]:
        """Encode as standard A2A Agent Card."""
        return {
            "agentId": self.agent_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "url": self.url,
            "documentationUrl": self.documentation_url,
            "capabilities": [c.value for c in self.capabilities],
            "supportedMessageTypes": [m.value for m in self.supported_message_types],
            "extensions": [
                {"type": "governance_policy_card", "policies": [p.to_a2a_extension() for p in self.policy_cards]}
            ],
            "governance": {
                "kyc_level": "full",            # Know Your Agent compliance
                "audit_log_url": f"{self.url}/audit",
                "formal_verification": any(
                    c == A2ACapability.FORMAL_VERIFICATION for c in self.capabilities
                ),
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_a2a_card(), indent=2)


# ── A2A Adapter ────────────────────────────────────────────────────────────────

class A2AAdapter:
    """Adapter for encoding governance decisions as A2A protocol messages.

    Bridges the gap between internal governance modules (GodelianBoundary,
    RealityBridge) and the external A2A protocol ecosystem.

    Key functions:
      1. Encode governance verdicts → A2A messages
      2. Decode A2A messages → governance verdicts
      3. Generate Agent Cards with governance extensions
      4. Policy Card management
    """

    def __init__(self, agent_id: str = "agent-governance-guardian"):
        self.agent_id = agent_id
        self._policy_cards: dict[str, A2APolicyCard] = {}
        self._message_history: list[A2AGovernanceMessage] = []

    # ── Verdict Encoding ────────────────────────────────────────────────────

    def encode_verdict(
        self,
        verdict: str,                          # "ALLOW" | "DENY" | "EXTERNALIZE" | ...
        target_agent: str = "",
        decision_id: str = "",
        risk_score: float = 0.0,
        confidence: float = 1.0,
        reason: str = "",
        policy_card: A2APolicyCard | None = None,
        requires_human: bool = False,
        expires_in_seconds: int = 3600,
    ) -> A2AGovernanceMessage:
        """Encode a governance verdict as an A2A message.

        Maps internal verdicts to A2A verdicts:
          - ALLOW, ACCEPT → ALLOW
          - DENY, REJECT, BLOCK → DENY
          - EXTERNALIZE → DEFER_TO_HUMAN or DEFER_TO_AGENT
          - MODIFY → REQUIRE_MODIFICATION
        """
        verdict_map = {
            "ALLOW": A2AVerdict.ALLOW,
            "ACCEPT": A2AVerdict.ALLOW,
            "PERMIT": A2AVerdict.ALLOW,
            "DENY": A2AVerdict.DENY,
            "REJECT": A2AVerdict.DENY,
            "BLOCK": A2AVerdict.DENY,
            "EXTERNALIZE": A2AVerdict.DEFER_TO_AGENT,
            "DEFER": A2AVerdict.DEFER_TO_HUMAN,
            "MODIFY": A2AVerdict.REQUIRE_MODIFICATION,
        }
        a2a_verdict = verdict_map.get(verdict.upper(), A2AVerdict.UNKNOWN)

        # EXTERNALIZE may require human based on risk
        if verdict.upper() == "EXTERNALIZE" and risk_score >= 0.8:
            a2a_verdict = A2AVerdict.DEFER_TO_HUMAN
            requires_human = True

        expires = datetime.now(timezone.utc).isoformat() if expires_in_seconds <= 0 else ""
        if expires_in_seconds > 0:
            from datetime import timedelta
            expires = (datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).isoformat()

        msg = A2AGovernanceMessage(
            source_agent=self.agent_id,
            target_agent=target_agent,
            verdict=a2a_verdict,
            decision_id=decision_id,
            policy_id=policy_card.policy_id if policy_card else "",
            risk_score=risk_score,
            confidence=confidence,
            reason=reason,
            requires_human=requires_human,
            expires_at=expires,
            trace_context={"source": "GodelianBoundary"},
        )

        self._message_history.append(msg)
        return msg

    def decode_verdict(self, a2a_message: dict[str, Any]) -> A2AGovernanceMessage:
        """Decode an A2A message back into a governance verdict."""
        return A2AGovernanceMessage.from_a2a_message(a2a_message)

    # ── Policy Card Management ──────────────────────────────────────────────

    def register_policy_card(self, policy_card: A2APolicyCard) -> None:
        """Register a governance policy card for A2A sharing."""
        self._policy_cards[policy_card.policy_id] = policy_card

    def get_policy_card(self, policy_id: str) -> A2APolicyCard | None:
        """Retrieve a registered policy card."""
        return self._policy_cards.get(policy_id)

    def sync_policy_card(self, policy_id: str, target_agent: str) -> A2AGovernanceMessage:
        """Create an A2A message to sync a policy card with another agent."""
        policy = self._policy_cards.get(policy_id)
        msg = A2AGovernanceMessage(
            message_type=A2AMessageType.POLICY_SYNC,
            source_agent=self.agent_id,
            target_agent=target_agent,
            policy_id=policy_id,
            metadata={"policy_card": policy.to_a2a_extension() if policy else {}},
        )
        return msg

    # ── Agent Card Generation ───────────────────────────────────────────────

    def generate_agent_card(
        self,
        name: str = "Agent Governance Guardian",
        description: str = "Cross-agent governance enforcement engine using A2A protocol",
        url: str = "",
        capabilities: list[A2ACapability] | None = None,
    ) -> A2AAgentCard:
        """Generate an A2A Agent Card with full governance extension."""
        if capabilities is None:
            capabilities = [
                A2ACapability.POLICY_ENFORCEMENT,
                A2ACapability.RISK_ASSESSMENT,
                A2ACapability.AUDIT_TRAIL,
                A2ACapability.DELEGATION_CHAIN,
                A2ACapability.EMERGENCY_STOP,
                A2ACapability.CIRCUIT_BREAKER,
            ]

        return A2AAgentCard(
            agent_id=self.agent_id,
            name=name,
            description=description,
            url=url,
            capabilities=capabilities,
            policy_cards=list(self._policy_cards.values()),
        )

    # ── Audit & Stats ───────────────────────────────────────────────────────

    def get_history(self, limit: int = 50) -> list[A2AGovernanceMessage]:
        """Get recent governance message history."""
        return self._message_history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get adapter statistics."""
        verdicts: dict[str, int] = {}
        for msg in self._message_history:
            verdicts[msg.verdict.value] = verdicts.get(msg.verdict.value, 0) + 1
        return {
            "agent_id": self.agent_id,
            "policy_cards_registered": len(self._policy_cards),
            "messages_processed": len(self._message_history),
            "verdict_distribution": verdicts,
        }
