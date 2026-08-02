"""Tests for OpenTelemetry + GAAT Governance Telemetry Exporter."""

import json
import os
import pytest
import tempfile
from pathlib import Path
from telemetry.otel_exporter import (
    GovernanceTelemetry,
    GTSEvent,
    DecisionVerdict,
    PolicyCategory,
    get_telemetry,
    shutdown_telemetry,
)


class TestGTSEvent:
    """Test GTSEvent data structure."""

    def test_event_creation_defaults(self):
        event = GTSEvent()
        assert event.event_id
        assert event.timestamp
        assert event.verdict == DecisionVerdict.ALLOW
        assert event.policy_category == PolicyCategory.SECURITY

    def test_event_creation_full(self):
        event = GTSEvent(
            module="GodelianBoundary",
            operation="evaluate",
            verdict=DecisionVerdict.DENY,
            policy_category=PolicyCategory.SAFETY,
            policy_name="critical_action_block",
            agent_id="agent-01",
            session_id="sess-01",
            duration_ms=12.5,
            risk_score=0.95,
            confidence=0.98,
            reason="Blocked dangerous operation",
        )
        assert event.module == "GodelianBoundary"
        assert event.operation == "evaluate"
        assert event.verdict == DecisionVerdict.DENY
        assert event.risk_score == 0.95

    def test_to_otel_attributes(self):
        event = GTSEvent(
            module="TestModule",
            operation="test_op",
            verdict=DecisionVerdict.ALLOW,
            risk_score=0.3,
        )
        attrs = event.to_otel_attributes()
        assert attrs["governance.module"] == "TestModule"
        assert attrs["governance.operation"] == "test_op"
        assert attrs["governance.verdict"] == "allow"
        assert attrs["governance.risk_score"] == 0.3
        assert attrs["governance.event_id"] == event.event_id

    def test_to_log_format(self):
        event = GTSEvent(
            module="TestModule",
            operation="test_op",
            verdict=DecisionVerdict.ALLOW,
        )
        log_str = event.to_log_format()
        data = json.loads(log_str)
        assert data["module"] == "TestModule"
        assert data["op"] == "test_op"
        assert data["verdict"] == "allow"


class TestGovernanceTelemetry:
    """Test GovernanceTelemetry (file-based fallback mode)."""

    def test_initialization(self, tmp_path):
        log_file = str(tmp_path / "test_telemetry.log")
        tel = GovernanceTelemetry(
            service_name="test-service",
            log_file=log_file,
            enable_otel=False,  # No OTel SDK in test
            enable_file_fallback=True,
        )
        assert tel.service_name == "test-service"
        assert tel.enable_file_fallback is True
        assert tel._otel_ready is False  # No OTel available

    def test_record_policy_decision(self, tmp_path):
        log_file = str(tmp_path / "test_telemetry.log")
        tel = GovernanceTelemetry(
            service_name="test",
            log_file=log_file,
            enable_file_fallback=True,
        )
        event = tel.record_policy_decision(
            module="GodelianBoundary",
            operation="evaluate",
            verdict=DecisionVerdict.DENY,
            policy_name="security_policy",
            risk_score=0.9,
            reason="Blocked by policy",
        )
        assert isinstance(event, GTSEvent)
        assert event.verdict == DecisionVerdict.DENY
        assert event.policy_name == "security_policy"

        # Verify log file was written
        assert os.path.exists(log_file)
        content = Path(log_file).read_text(encoding="utf-8").strip()
        data = json.loads(content)
        assert data["verdict"] == "deny"
        assert data["module"] == "GodelianBoundary"

    def test_record_policy_violation(self, tmp_path):
        log_file = str(tmp_path / "test_violation.log")
        tel = GovernanceTelemetry(
            service_name="test",
            log_file=log_file,
            enable_file_fallback=True,
        )
        event = tel.record_policy_violation(
            module="SecurityGate",
            operation="validate_request",
            policy_name="secrets_protection",
            severity="critical",
            details="Hardcoded API key detected",
        )
        assert event.verdict == DecisionVerdict.DENY
        assert event.risk_score == 0.9
        assert "Hardcoded API key" in event.reason

    def test_record_policy_allow(self, tmp_path):
        log_file = str(tmp_path / "test_allow.log")
        tel = GovernanceTelemetry(
            service_name="test",
            log_file=log_file,
            enable_file_fallback=True,
        )
        event = tel.record_policy_allow(
            module="PermissionGate",
            operation="check_permission",
            reason="Action within allowed scope",
        )
        assert event.verdict == DecisionVerdict.ALLOW

    def test_multiple_decisions(self, tmp_path):
        """Test that multiple decisions are appended correctly."""
        log_file = str(tmp_path / "test_multi.log")
        tel = GovernanceTelemetry(
            service_name="test",
            log_file=log_file,
            enable_file_fallback=True,
        )
        for i in range(5):
            tel.record_policy_decision(
                module="Test",
                operation=f"op_{i}",
                verdict=DecisionVerdict.ALLOW if i % 2 == 0 else DecisionVerdict.DENY,
            )

        lines = Path(log_file).read_text(encoding="utf-8").strip().split('\n')
        assert len(lines) == 5

    def test_decision_span_context_manager(self, tmp_path):
        log_file = str(tmp_path / "test_span.log")
        tel = GovernanceTelemetry(
            service_name="test",
            log_file=log_file,
            enable_file_fallback=True,
        )
        with tel.decision_span("test_operation", "TestModule") as span:
            # Span is None without OTel SDK
            pass
        # Should not raise any errors

    def test_get_stats(self, tmp_path):
        log_file = str(tmp_path / "test_stats.log")
        tel = GovernanceTelemetry(
            service_name="test-stats",
            log_file=log_file,
            enable_file_fallback=True,
        )
        stats = tel.get_stats()
        assert stats["service"] == "test-stats"
        assert "uptime_seconds" in stats
        assert stats["file_fallback"] is True

    def test_shutdown(self, tmp_path):
        log_file = str(tmp_path / "test_shutdown.log")
        tel = GovernanceTelemetry(
            service_name="test",
            log_file=log_file,
            enable_file_fallback=True,
        )
        tel.shutdown()  # Should not raise


class TestGlobalTelemetry:
    """Test global telemetry singleton."""

    def setup_method(self):
        shutdown_telemetry()

    def teardown_method(self):
        shutdown_telemetry()

    def test_get_telemetry_creates_instance(self, tmp_path):
        log_file = str(tmp_path / "test_global.log")
        os.environ["GOVERNANCE_TELEMETRY_LOG"] = log_file

        tel = get_telemetry(service_name="global-test")
        assert tel is not None
        assert tel.service_name == "global-test"

        # Second call returns same instance
        tel2 = get_telemetry()
        assert tel2 is tel

    def test_reset_creates_new_instance(self, tmp_path):
        log_file = str(tmp_path / "test_reset.log")
        # Use a unique service name to avoid conflict with other tests
        os.environ["GOVERNANCE_TELEMETRY_LOG"] = f"{log_file}_reset"

        tel1 = get_telemetry(service_name="reset-test-1")
        tel2 = get_telemetry(service_name="reset-test-2", reset=True)
        assert tel2.service_name == "reset-test-2"

    def test_shutdown_clears_instance(self, tmp_path):
        log_file = str(tmp_path / "test_shutdown2.log")
        os.environ["GOVERNANCE_TELEMETRY_LOG"] = f"{log_file}_sd"
        tel = get_telemetry(service_name="sd-test")
        assert tel is not None
        shutdown_telemetry()
        tel2 = get_telemetry()
        assert tel2 is not tel  # New instance after shutdown


class TestDecisionVerdictEnum:
    """Test DecisionVerdict enum values."""

    def test_all_verdicts(self):
        verdicts = list(DecisionVerdict)
        assert len(verdicts) == 6
        assert DecisionVerdict.ALLOW.value == "allow"
        assert DecisionVerdict.DENY.value == "deny"
        assert DecisionVerdict.DEFER.value == "defer"


class TestPolicyCategoryEnum:
    """Test PolicyCategory enum values."""

    def test_all_categories(self):
        categories = list(PolicyCategory)
        assert len(categories) == 7
        assert PolicyCategory.SECURITY.value == "security"
        assert PolicyCategory.SAFETY.value == "safety"
