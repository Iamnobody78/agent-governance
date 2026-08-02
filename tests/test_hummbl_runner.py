"""Tests for HUMMBL Governance Bench Runner."""

import pytest
from benchmarks.hummbl_runner import (
    HummblRunner,
    HummblReport,
    HummblPrimitive,
    PrimitiveTest,
    PrimitiveReport,
    TestResult,
)


# ── Mock modules ────────────────────────────────────────────────────────────────

class MockSafeModule:
    """A module with comprehensive safety features."""

    def get_state(self):
        return {
            "stopped": False,
            "circuit_breaker": {"open": False, "failure_count": 3, "half_open": False},
            "failure_threshold": 5,
            "max_failures": 5,
            "cooldown": 60,
            "delegation_chain": [{"from": "A", "to": "B"}],
            "max_delegation_depth": 3,
            "allowed_actions": ["read", "write"],
            "blocked_actions": ["delete_db", "sudo"],
            "roles": {"admin": ["*"], "viewer": ["read"]},
            "data_provenance": True,
            "taint_propagation": True,
            "sensitive_fields": ["password", "ssn"],
            "resource_limits": {"max_cpu": 80, "max_memory_mb": 512},
            "network_scope": ["api.example.com"],
            "allowed_paths": ["/workspace/"],
            "sandbox": {"enabled": True},
            "baseline": {"avg_response_time": 50},
            "anomaly_detection": True,
            "drift_events": [],
            "auto_correction": True,
        }

    def audit_trail(self):
        return [
            {"action": "delegate", "from": "A", "to": "B", "timestamp": "..."},
            {"action": "execute", "result": "allowed", "owner": "agent-01"},
        ]

    def stop(self): pass
    def restart(self): pass
    def save_state(self): pass
    def revoke_delegation(self, id): pass


class MockUnsafeModule:
    """A module with minimal or no safety features."""

    def get_state(self):
        return {}

    def audit_trail(self):
        return []


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestHummblRunner:
    """Test core runner functionality."""

    def test_evaluate_safe_module(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "SafeModule")
        assert isinstance(report, HummblReport)
        assert report.module_name == "SafeModule"
        assert report.overall_score >= 60, f"Expected >=60, got {report.overall_score}"
        assert report.pass_rate >= 0.5

    def test_evaluate_unsafe_module(self):
        runner = HummblRunner()
        report = runner.evaluate(MockUnsafeModule(), "UnsafeModule")
        assert report.overall_score < 50, f"Expected <50, got {report.overall_score}"

    def test_all_primitives_present(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        for prim in HummblPrimitive:
            assert prim.value in report.primitive_reports, f"Missing {prim.value}"
            pr = report.primitive_reports[prim.value]
            assert pr.total_tests > 0, f"{prim.value} has no tests"

    def test_report_markdown(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        md = report.to_markdown()
        assert "HUMMBL Governance Bench" in md
        assert "Test" in md
        assert "Pass Rate" in md


class TestPrimitiveEmergencyStop:
    """Test Emergency Stop primitive checks."""

    def test_safe_module_has_stop(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        pr = report.primitive_reports[HummblPrimitive.EMERGENCY_STOP.value]
        assert pr.score > 0.5, f"Emergency stop score too low: {pr.score}"
        assert pr.passed >= 2

    def test_unsafe_module_no_stop(self):
        runner = HummblRunner()
        report = runner.evaluate(MockUnsafeModule(), "Test")
        pr = report.primitive_reports[HummblPrimitive.EMERGENCY_STOP.value]
        assert pr.score <= 0.5, f"Unsafe module should fail emergency stop"


class TestPrimitiveCircuitBreaker:
    """Test Circuit Breaker primitive checks."""

    def test_safe_circuit_breaker(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        pr = report.primitive_reports[HummblPrimitive.CIRCUIT_BREAKER.value]
        assert pr.passed >= 3, f"Circuit breaker: {pr.passed}/{pr.total_tests}"


class TestPrimitiveAuthorityBoundary:
    """Test Authority Boundary primitive checks."""

    def test_safe_authority(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        pr = report.primitive_reports[HummblPrimitive.AUTHORITY_BOUNDARY.value]
        assert pr.passed >= 3, f"Authority: {pr.passed}/{pr.total_tests}"

    def test_unsafe_authority(self):
        runner = HummblRunner()
        report = runner.evaluate(MockUnsafeModule(), "Test")
        pr = report.primitive_reports[HummblPrimitive.AUTHORITY_BOUNDARY.value]
        assert pr.failed >= 3


class TestPrimitiveTaintTracking:
    """Test Taint Tracking primitive checks."""

    def test_safe_taint(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        pr = report.primitive_reports[HummblPrimitive.TAINT_TRACKING.value]
        assert pr.passed >= 2


class TestPrimitiveExecutionBoundary:
    """Test Execution Boundary primitive checks."""

    def test_safe_boundary(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        pr = report.primitive_reports[HummblPrimitive.EXECUTION_BOUNDARY.value]
        assert pr.passed >= 2


class TestPrimitiveDriftDetection:
    """Test Drift Detection primitive checks."""

    def test_safe_drift(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        pr = report.primitive_reports[HummblPrimitive.DRIFT_DETECTION.value]
        assert pr.passed >= 2


class TestTestResultEnum:
    """Test Result enum values."""

    def test_values(self):
        assert TestResult.PASS.value == "pass"
        assert TestResult.FAIL.value == "fail"
        assert TestResult.SKIP.value == "skip"
        assert TestResult.ERROR.value == "error"


class TestRecommendations:
    """Test recommendation generation."""

    def test_recommendations_for_failing_module(self):
        runner = HummblRunner()
        report = runner.evaluate(MockUnsafeModule(), "Test")
        assert len(report.recommendations) > 0
        assert len(report.critical_failures) > 0

    def test_recommendations_markdown(self):
        runner = HummblRunner()
        report = runner.evaluate(MockSafeModule(), "Test")
        md = report.to_markdown()
        assert "Recommendations" in md
