"""Tests for A2A Protocol Adapter for Agent Governance."""

import json
import pytest
from protocols.a2a_adapter import (
    A2AAdapter,
    A2AGovernanceMessage,
    A2APolicyCard,
    A2AAgentCard,
    A2AMessageType,
    A2AVerdict,
    A2ACapability,
)


class TestA2AVerdictEnum:
    """Test A2AVerdict enum."""

    def test_all_verdicts(self):
        verdicts = list(A2AVerdict)
        assert len(verdicts) >= 5
        assert A2AVerdict.ALLOW.value == "allow"
        assert A2AVerdict.DENY.value == "deny"


class TestA2ACapabilityEnum:
    """Test A2ACapability enum."""

    def test_all_capabilities(self):
        caps = list(A2ACapability)
        assert len(caps) >= 5
        assert A2ACapability.POLICY_ENFORCEMENT.value == "policy_enforcement"
        assert A2ACapability.AUDIT_TRAIL.value == "audit_trail"


class TestA2APolicyCard:
    """Test A2APolicyCard data structure."""

    def test_creation_defaults(self):
        card = A2APolicyCard()
        assert card.policy_id
        assert card.version == "1.0.0"
        assert card.risk_threshold == 0.7
        assert card.max_delegation_depth == 5

    def test_creation_full(self):
        card = A2APolicyCard(
            name="Security Policy",
            version="2.0.0",
            description="Strict security policy",
            rules=[{"action": "block_delete", "verdict": "deny"}],
            risk_threshold=0.8,
            max_delegation_depth=3,
            requires_human_approval=["delete_database", "drop_table"],
            allowed_actions=["read", "write", "execute"],
            blocked_actions=["delete_database", "sudo"],
            rate_limits={"api_calls": 100},
        )
        assert card.name == "Security Policy"
        assert card.blocked_actions == ["delete_database", "sudo"]
        assert card.requires_human_approval == ["delete_database", "drop_table"]
        assert card.rate_limits == {"api_calls": 100}

    def test_to_a2a_extension(self):
        card = A2APolicyCard(
            name="Test Policy",
            rules=[{"action": "test", "verdict": "allow"}],
            blocked_actions=["dangerous_op"],
        )
        ext = card.to_a2a_extension()
        assert ext["type"] == "governance_policy_card"
        assert ext["policy_id"] == card.policy_id
        assert ext["name"] == "Test Policy"
        constraints = ext["constraints"]
        assert constraints["blocked_actions"] == ["dangerous_op"]
        assert constraints["risk_threshold"] == 0.7

    def test_to_json(self):
        card = A2APolicyCard(name="JSON Test")
        json_str = card.to_json()
        data = json.loads(json_str)
        assert data["name"] == "JSON Test"

    def test_from_dict(self):
        data = {
            "name": "From Dict Policy",
            "version": "1.5.0",
            "constraints": {
                "risk_threshold": 0.9,
                "max_delegation_depth": 2,
                "requires_human_approval": ["op1"],
                "allowed_actions": ["read"],
                "blocked_actions": ["write"],
                "rate_limits": {"api": 50},
            },
            "rules": [],
        }
        card = A2APolicyCard.from_dict(data)
        assert card.name == "From Dict Policy"
        assert card.risk_threshold == 0.9
        assert card.max_delegation_depth == 2


class TestA2AGovernanceMessage:
    """Test A2AGovernanceMessage data structure."""

    def test_creation_defaults(self):
        msg = A2AGovernanceMessage()
        assert msg.message_id
        assert msg.message_type == A2AMessageType.GOVERNANCE_VERDICT
        assert msg.verdict == A2AVerdict.UNKNOWN

    def test_creation_full(self):
        msg = A2AGovernanceMessage(
            source_agent="guardian",
            target_agent="codex",
            verdict=A2AVerdict.DENY,
            decision_id="dec-001",
            policy_id="pol-001",
            risk_score=0.95,
            confidence=0.99,
            reason="Dangerous operation blocked",
            requires_human=True,
        )
        assert msg.source_agent == "guardian"
        assert msg.target_agent == "codex"
        assert msg.verdict == A2AVerdict.DENY
        assert msg.risk_score == 0.95

    def test_to_a2a_message(self):
        msg = A2AGovernanceMessage(
            source_agent="guardian",
            target_agent="codex",
            verdict=A2AVerdict.DENY,
            reason="Blocked by policy",
            risk_score=0.9,
        )
        a2a = msg.to_a2a_message()
        assert a2a["messageId"] == msg.message_id
        assert a2a["type"] == "governance_verdict"
        assert len(a2a["parts"]) == 2
        # Text part
        assert a2a["parts"][0]["type"] == "text"
        assert "DENY" in a2a["parts"][0]["text"]
        # Data part
        assert a2a["parts"][1]["type"] == "data"
        data = a2a["parts"][1]["data"]
        assert data["verdict"] == "deny"
        assert data["risk_score"] == 0.9
        assert a2a["metadata"]["source_agent"] == "guardian"

    def test_from_a2a_message(self):
        original = A2AGovernanceMessage(
            source_agent="guardian",
            target_agent="codex",
            verdict=A2AVerdict.ALLOW,
            risk_score=0.1,
            reason="Safe operation",
        )
        a2a_data = original.to_a2a_message()
        parsed = A2AGovernanceMessage.from_a2a_message(a2a_data)
        assert parsed.verdict == original.verdict
        assert parsed.risk_score == original.risk_score
        assert parsed.source_agent == original.source_agent

    def test_from_a2a_message_minimal(self):
        """Test parsing a minimal A2A message without governance data."""
        a2a_data = {
            "messageId": "msg-001",
            "type": "governance_verdict",
            "role": "agent",
            "parts": [{"type": "text", "text": "Hello"}],
            "metadata": {"source_agent": "agent-a"},
        }
        parsed = A2AGovernanceMessage.from_a2a_message(a2a_data)
        assert parsed.message_id == "msg-001"
        assert parsed.source_agent == "agent-a"

    def test_to_json(self):
        msg = A2AGovernanceMessage(
            source_agent="guardian",
            verdict=A2AVerdict.DENY,
        )
        json_str = msg.to_json()
        data = json.loads(json_str)
        assert data["metadata"]["source_agent"] == "guardian"


class TestA2AAgentCard:
    """Test A2AAgentCard data structure."""

    def test_creation(self):
        card = A2AAgentCard(
            agent_id="guardian-01",
            name="Governance Guardian",
            description="Cross-agent governance engine",
            capabilities=[A2ACapability.POLICY_ENFORCEMENT, A2ACapability.AUDIT_TRAIL],
        )
        assert card.agent_id == "guardian-01"
        assert len(card.capabilities) == 2

    def test_to_a2a_card(self):
        policy = A2APolicyCard(name="Security Policy")
        card = A2AAgentCard(
            agent_id="guardian-01",
            name="Guardian",
            capabilities=[A2ACapability.POLICY_ENFORCEMENT],
            policy_cards=[policy],
        )
        a2a_card = card.to_a2a_card()
        assert a2a_card["agentId"] == "guardian-01"
        assert a2a_card["name"] == "Guardian"
        assert "policy_enforcement" in a2a_card["capabilities"]
        assert len(a2a_card["extensions"]) == 1
        assert a2a_card["governance"]["kyc_level"] == "full"


class TestA2AAdapter:
    """Test A2AAdapter core functionality."""

    def test_initialization(self):
        adapter = A2AAdapter(agent_id="test-guardian")
        assert adapter.agent_id == "test-guardian"
        assert len(adapter._policy_cards) == 0
        assert len(adapter._message_history) == 0

    def test_encode_allow_verdict(self):
        adapter = A2AAdapter()
        msg = adapter.encode_verdict(
            verdict="ALLOW",
            target_agent="codex-agent",
            decision_id="dec-001",
            reason="Safe read operation",
        )
        assert msg.verdict == A2AVerdict.ALLOW
        assert msg.target_agent == "codex-agent"
        assert msg.source_agent == adapter.agent_id

    def test_encode_deny_verdict(self):
        adapter = A2AAdapter()
        msg = adapter.encode_verdict(
            verdict="DENY",
            target_agent="codex-agent",
            risk_score=0.95,
            reason="Dangerous action",
        )
        assert msg.verdict == A2AVerdict.DENY
        assert msg.risk_score == 0.95
        assert "Dangerous action" in msg.reason

    def test_encode_externalize_high_risk(self):
        """EXTERNALIZE with high risk should become DEFER_TO_HUMAN."""
        adapter = A2AAdapter()
        msg = adapter.encode_verdict(
            verdict="EXTERNALIZE",
            risk_score=0.9,
        )
        assert msg.verdict == A2AVerdict.DEFER_TO_HUMAN
        assert msg.requires_human is True

    def test_encode_externalize_low_risk(self):
        """EXTERNALIZE with low risk should become DEFER_TO_AGENT."""
        adapter = A2AAdapter()
        msg = adapter.encode_verdict(
            verdict="EXTERNALIZE",
            risk_score=0.3,
        )
        assert msg.verdict == A2AVerdict.DEFER_TO_AGENT
        assert msg.requires_human is False

    def test_encode_modify(self):
        adapter = A2AAdapter()
        msg = adapter.encode_verdict(
            verdict="MODIFY",
            reason="Needs sanitization",
        )
        assert msg.verdict == A2AVerdict.REQUIRE_MODIFICATION

    def test_decode_verdict(self):
        adapter = A2AAdapter()
        original = adapter.encode_verdict("ALLOW", target_agent="target-1")
        a2a_data = original.to_a2a_message()
        decoded = adapter.decode_verdict(a2a_data)
        assert decoded.verdict == A2AVerdict.ALLOW
        assert decoded.target_agent == "target-1"

    def test_register_and_get_policy_card(self):
        adapter = A2AAdapter()
        card = A2APolicyCard(name="Security Policy")
        adapter.register_policy_card(card)
        assert len(adapter._policy_cards) == 1
        retrieved = adapter.get_policy_card(card.policy_id)
        assert retrieved is card

    def test_sync_policy_card(self):
        adapter = A2AAdapter()
        card = A2APolicyCard(name="Sync Policy")
        adapter.register_policy_card(card)
        msg = adapter.sync_policy_card(card.policy_id, target_agent="codex")
        assert msg.message_type == A2AMessageType.POLICY_SYNC
        assert msg.target_agent == "codex"

    def test_generate_agent_card(self):
        adapter = A2AAdapter(agent_id="guardian-01")
        card = A2APolicyCard(name="Default Policy")
        adapter.register_policy_card(card)

        agent_card = adapter.generate_agent_card(
            name="Guardian",
            description="Governance engine",
        )
        assert agent_card.agent_id == "guardian-01"
        assert agent_card.name == "Guardian"
        assert len(agent_card.policy_cards) == 1

    def test_get_history(self):
        adapter = A2AAdapter()
        adapter.encode_verdict("ALLOW")
        adapter.encode_verdict("DENY")
        adapter.encode_verdict("MODIFY")
        history = adapter.get_history()
        assert len(history) == 3

    def test_get_stats(self):
        adapter = A2AAdapter()
        adapter.encode_verdict("ALLOW", risk_score=0.1)
        adapter.encode_verdict("DENY", risk_score=0.9)
        adapter.encode_verdict("ALLOW", risk_score=0.2)
        stats = adapter.get_stats()
        assert stats["agent_id"] == adapter.agent_id
        assert stats["messages_processed"] == 3
        assert stats["verdict_distribution"]["allow"] == 2
        assert stats["verdict_distribution"]["deny"] == 1

    def test_encode_with_policy_card(self):
        adapter = A2AAdapter()
        card = A2APolicyCard(name="Security Policy", policy_id="pol-sec-1")
        adapter.register_policy_card(card)
        msg = adapter.encode_verdict(
            verdict="DENY",
            policy_card=card,
            reason="Violated security policy",
        )
        assert msg.policy_id == "pol-sec-1"

    def test_encode_with_expiry(self):
        adapter = A2AAdapter()
        msg = adapter.encode_verdict(
            verdict="ALLOW",
            expires_in_seconds=3600,
        )
        assert msg.expires_at  # Should be set to a future timestamp
        assert "T" in msg.expires_at  # ISO 8601 format

    def test_unknown_verdict_default(self):
        adapter = A2AAdapter()
        msg = adapter.encode_verdict(verdict="SOME_UNKNOWN_VERDICT")
        assert msg.verdict == A2AVerdict.UNKNOWN
