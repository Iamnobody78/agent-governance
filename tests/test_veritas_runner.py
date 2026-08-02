"""Tests for VeritasBench Governability Assessment Runner."""

import pytest
from benchmarks.veritas_runner import (
    VeritasRunner,
    VeritasReport,
    VeritasDimension,
    MaturityLevel,
    DimensionScore,
    assess_module,
    assess_all_modules,
)


# ── Mock governance module for testing ──────────────────────────────────────────

class MockGovernanceModule:
    """A mock module with varying levels of governability for testing."""

    def __init__(self, features: dict | None = None):
        self._features = features or {}
        self._decisions: list[dict] = []
        self._audit: list[dict] = []

    def get_state(self) -> dict:
        state = {"decisions": self._decisions}
        state.update(self._features)
        return state

    def audit_trail(self) -> list[dict]:
        return self._audit


class MockGovernableModule(MockGovernanceModule):
    """A module with full governability features."""

    def __init__(self):
        super().__init__({
            "thresholds": {"risk": 0.7, "confidence": 0.8},
            "reality_bridge": {"active": True},
            "agent_id": "governor-01",
            "policies": {"default": "strict"},
            "violations": [],
            "policy_version": "1.0.0",
            "operation_types": ["CREATE", "READ", "UPDATE", "DELETE"],
        })
        self._decisions = [
            {"timestamp": "2026-01-01T00:00:00Z", "reason": "test decision", "action": "test"}
        ]
        self._audit = [
            {"action": "evaluate", "result": "allowed", "owner": "guardian", "timestamp": "..."}
        ]

    def stop(self): pass
    def restart(self): pass
    def override(self, decision_id: str): pass


class MockMinimalModule(MockGovernanceModule):
    """A module with minimal governability features."""

    def __init__(self):
        super().__init__({})


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestVeritasRunner:
    """Test VeritasRunner core functionality."""

    def test_evaluate_governable_module(self):
        module = MockGovernableModule()
        runner = VeritasRunner()
        report = runner.evaluate(module, "TestGovernable")
        assert isinstance(report, VeritasReport)
        assert report.module_name == "TestGovernable"
        assert report.overall_score >= 50  # Should score well due to full features

    def test_evaluate_minimal_module(self):
        module = MockMinimalModule()
        runner = VeritasRunner()
        report = runner.evaluate(module, "TestMinimal")
        assert report.overall_score < 50  # Should score poorly

    def test_report_is_governable(self):
        module = MockGovernableModule()
        runner = VeritasRunner()
        report = runner.evaluate(module)
        assert report.is_governable

    def test_report_markdown(self):
        module = MockGovernableModule()
        runner = VeritasRunner()
        report = runner.evaluate(module, "Test")
        md = report.to_markdown()
        assert "VeritasBench" in md
        assert "Test" in md
        assert "Auditability" in md
        assert "Controllability" in md
        assert "Accountability" in md
        assert "Policy Enforcement" in md


class TestDimensionScores:
    """Test individual dimension scoring."""

    def test_auditability_with_data(self):
        module = MockGovernableModule()
        runner = VeritasRunner()
        state = module.get_state()
        audit = module.audit_trail()
        ds = runner._check_auditability(state, audit)
        assert ds.score > 0.4
        assert len(ds.details) > 0

    def test_auditability_empty(self):
        module = MockMinimalModule()
        runner = VeritasRunner()
        state = module.get_state()
        audit = module.audit_trail()
        ds = runner._check_auditability(state, audit)
        assert ds.score < 0.5
        assert len(ds.gaps) > 0

    def test_controllability_with_features(self):
        module = MockGovernableModule()
        runner = VeritasRunner()
        ds = runner._check_controllability(module.get_state(), module)
        assert ds.score >= 0.6
        assert "Emergency stop" in str(ds.details)
        assert "Action override" in str(ds.details)

    def test_controllability_minimal(self):
        module = MockMinimalModule()
        runner = VeritasRunner()
        ds = runner._check_controllability(module.get_state(), module)
        assert ds.score < 0.4

    def test_accountability_with_identity(self):
        module = MockGovernableModule()
        runner = VeritasRunner()
        ds = runner._check_accountability(module.get_state(), module.audit_trail())
        assert ds.score >= 0.4
        assert "Agent identity" in str(ds.details)

    def test_policy_enforcement(self):
        module = MockGovernableModule()
        runner = VeritasRunner()
        ds = runner._check_policy_enforcement(module.get_state(), module)
        assert ds.score >= 0.6
        assert "Explicit policy" in str(ds.details)


class TestMaturityMapping:
    """Test maturity level from score mapping."""

    @pytest.mark.parametrize("score,expected", [
        (0.9, MaturityLevel.OPTIMIZING),
        (0.8, MaturityLevel.OPTIMIZING),
        (0.7, MaturityLevel.MEASURED),
        (0.6, MaturityLevel.MEASURED),
        (0.5, MaturityLevel.MANAGED),
        (0.4, MaturityLevel.MANAGED),
        (0.3, MaturityLevel.DEFINED),
        (0.2, MaturityLevel.DEFINED),
        (0.1, MaturityLevel.INITIAL),
    ])
    def test_maturity_from_score(self, score, expected):
        runner = VeritasRunner()
        assert runner._maturity_from_score(score) == expected


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_assess_module(self):
        report = assess_module(MockGovernableModule(), "QuickTest")
        assert isinstance(report, VeritasReport)
        assert report.module_name == "QuickTest"

    def test_assess_all_modules(self):
        modules = {
            "governed": MockGovernableModule(),
            "minimal": MockMinimalModule(),
        }
        reports = assess_all_modules(modules)
        assert "governed" in reports
        assert "minimal" in reports
        assert reports["governed"].overall_score > reports["minimal"].overall_score


class TestDimensionWeights:
    """Test that dimension weights sum to 1.0."""

    def test_weights_sum_to_one(self):
        total = sum(VeritasRunner.DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}"
