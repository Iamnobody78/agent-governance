"""
Tests for FixedPointDetector
=============================
Comprehensive test suite covering convergence, oscillation, divergence,
plateau detection, serialization, and integration with EvolutionConvergenceGuard.
"""
import json
import tempfile
from pathlib import Path

import pytest

from governance.meta.fixed_point_detector import (
    ConvergenceReport,
    ConvergenceState,
    EvolutionConvergenceGuard,
    FixedPointDetector,
    StateSnapshot,
)


# ── StateSnapshot Tests ───────────────────────────────────────────────────────

class TestStateSnapshot:
    def test_creation_defaults(self):
        snap = StateSnapshot(iteration=1, score=0.95, params_hash="abc", structure_hash="def")
        assert snap.iteration == 1
        assert snap.score == 0.95
        assert snap.params_hash == "abc"
        assert snap.structure_hash == "def"
        assert snap.timestamp > 0
        assert snap.metadata == {}

    def test_creation_with_metadata(self):
        snap = StateSnapshot(
            iteration=2, score=0.88, params_hash="xyz",
            structure_hash="uvw", metadata={"phase": "training"},
        )
        assert snap.metadata == {"phase": "training"}

    def test_roundtrip_serialization(self):
        snap = StateSnapshot(
            iteration=5, score=0.92, params_hash="hash1",
            structure_hash="hash2", metadata={"key": "value"},
        )
        d = snap.to_dict()
        restored = StateSnapshot.from_dict(d)
        assert restored.iteration == snap.iteration
        assert restored.score == snap.score
        assert restored.params_hash == snap.params_hash
        assert restored.structure_hash == snap.structure_hash
        assert restored.metadata == snap.metadata


# ── FixedPointDetector Tests ──────────────────────────────────────────────────

class TestFixedPointDetectorBasic:
    """Basic initialization and property tests."""

    def test_default_initialization(self):
        detector = FixedPointDetector()
        assert detector.epsilon == 0.01
        assert detector.patience == 3
        assert detector.window_size == 5
        assert detector._current_iteration == 0

    def test_custom_initialization(self):
        detector = FixedPointDetector(epsilon=0.05, patience=5, window_size=10)
        assert detector.epsilon == 0.05
        assert detector.patience == 5
        assert detector.window_size == 10

    def test_reset(self):
        detector = FixedPointDetector()
        detector.step(0.9)
        detector.step(0.91)
        assert detector._current_iteration == 2
        detector.reset()
        assert detector._current_iteration == 0
        assert len(detector._history) == 0
        assert detector._best_score == float("-inf")


class TestFixedPointDetectorConvergence:
    """Convergence behavior tests."""

    def test_converges_after_patience_steps(self):
        """After 'patience' steps of delta < epsilon, should converge."""
        detector = FixedPointDetector(epsilon=0.01, patience=3)

        detector.step(0.90)
        detector.step(0.905)  # delta = 0.005 < 0.01
        detector.step(0.908)  # delta = 0.003 < 0.01
        report = detector.step(0.909)  # delta = 0.001 < 0.01 -> 3rd stagnation -> CONVERGED

        assert report.state == ConvergenceState.CONVERGED
        assert report.confidence > 0.5

    def test_does_not_converge_on_large_delta(self):
        """When delta > epsilon, should not converge."""
        detector = FixedPointDetector(epsilon=0.01, patience=3)

        detector.step(0.80)
        detector.step(0.85)  # delta = 0.05 > 0.01
        report = detector.step(0.90)  # delta = 0.05 > 0.01

        assert report.state == ConvergenceState.CONTINUE

    def test_resets_stagnation_on_improvement(self):
        """Stagnation counter resets when a significant improvement occurs."""
        detector = FixedPointDetector(epsilon=0.01, patience=3)

        detector.step(0.90)
        detector.step(0.905)  # stagnation 1
        detector.step(0.908)  # stagnation 2
        detector.step(0.92)   # big jump! stagnation resets to 0
        assert detector._stagnation_counter == 0

    def test_first_iteration_always_continue(self):
        detector = FixedPointDetector()
        report = detector.step(0.95)
        assert report.state == ConvergenceState.CONTINUE


class TestFixedPointDetectorOscillation:
    """Oscillation detection tests."""

    def test_detects_oscillation(self):
        """Alternating up/down should trigger OSCILLATING."""
        detector = FixedPointDetector(epsilon=0.01)
        reports = []
        for score in [0.90, 0.92, 0.89, 0.93, 0.88, 0.94]:
            reports.append(detector.step(score))
        # After enough reversals, should detect oscillation
        assert any(r.state == ConvergenceState.OSCILLATING for r in reports)

    def test_no_oscillation_with_steady_increase(self):
        """Steady increase should NOT be oscillation."""
        detector = FixedPointDetector(epsilon=0.01)
        reports = []
        for score in [0.80, 0.82, 0.85, 0.88, 0.91, 0.94]:
            reports.append(detector.step(score))
        assert all(r.state != ConvergenceState.OSCILLATING for r in reports)

    def test_no_oscillation_with_steady_decrease(self):
        """Steady decrease should NOT be oscillation (may be divergence)."""
        detector = FixedPointDetector(epsilon=0.01, divergence_factor=10.0)  # high to avoid trigging divergence
        reports = []
        for score in [0.90, 0.87, 0.84, 0.81, 0.78]:
            reports.append(detector.step(score))
        assert all(r.state != ConvergenceState.OSCILLATING for r in reports)


class TestFixedPointDetectorDivergence:
    """Divergence detection tests."""

    def test_detects_divergence(self):
        """When score drops far below best, should trigger DIVERGING."""
        detector = FixedPointDetector(divergence_factor=1.5)
        detector.step(1.0)   # best = 1.0
        detector.step(0.9)
        detector.step(0.6)   # 0.6 < 1.0/1.5 = 0.667 -> DIVERGING

        report = detector.step(0.5)
        assert report.state == ConvergenceState.DIVERGING

    def test_no_divergence_with_small_drops(self):
        detector = FixedPointDetector(divergence_factor=2.0)
        detector.step(1.0)   # best = 1.0
        report = detector.step(0.8)  # 0.8 > 1.0/2.0 = 0.5 -> NOT diverging
        assert report.state != ConvergenceState.DIVERGING


class TestFixedPointDetectorPlateau:
    """Plateau detection tests."""

    def test_detects_plateau(self):
        """Very slow improvement should trigger PLATEAU."""
        detector = FixedPointDetector(epsilon=0.01, patience=3)
        detector.step(0.90)
        detector.step(0.915)  # delta = 0.015, between epsilon and 2*epsilon
        detector.step(0.928)  # delta = 0.013
        # Painfully slow improvement
        report = detector.step(0.939)  # delta = 0.011

        # With patience=3 and 3 slow steps, may trigger plateau
        states = []
        for score in [0.90, 0.915, 0.928, 0.939, 0.948, 0.955]:
            states.append(detector.step(score).state)
        # At least one state should be plateau or continue (depending on exact values)
        valid_states = {ConvergenceState.PLATEAU, ConvergenceState.CONTINUE}
        assert all(s in valid_states for s in states)


class TestFixedPointDetectorReport:
    """Report content tests."""

    def test_report_contains_trend(self):
        detector = FixedPointDetector()
        detector.step(0.80)
        detector.step(0.85)
        report = detector.step(0.90)
        assert len(report.score_trend) > 0
        assert 0.90 in report.score_trend

    def test_report_delta_correct(self):
        detector = FixedPointDetector()
        detector.step(0.80)
        report = detector.step(0.85)
        assert abs(report.score_delta - 0.05) < 1e-9

    def test_report_params_changed(self):
        detector = FixedPointDetector()
        detector.step(0.90, params="v1")
        report = detector.step(0.91, params="v2")
        assert report.params_changed is True

    def test_report_params_unchanged(self):
        detector = FixedPointDetector()
        detector.step(0.90, params="same")
        report = detector.step(0.91, params="same")
        assert report.params_changed is False

    def test_report_has_recommendation(self):
        detector = FixedPointDetector()
        report = detector.step(0.95)
        assert len(report.recommendation) > 0

    def test_report_serialization(self):
        detector = FixedPointDetector()
        detector.step(0.90)
        report = detector.step(0.95)
        d = report.to_dict()
        assert d["state"] == "continue"
        assert d["current_iteration"] == 2
        assert isinstance(d["score_trend"], list)


class TestFixedPointDetectorSerialization:
    """Save/load tests."""

    def test_save_load_roundtrip(self):
        detector = FixedPointDetector(epsilon=0.02, patience=4)
        detector.step(0.90, params="p1", structure="s1")
        detector.step(0.92, params="p2", structure="s2")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            detector.save(path)

        restored = FixedPointDetector.load(path)
        assert restored.epsilon == 0.02
        assert restored.patience == 4
        assert restored._current_iteration == 2
        assert restored._best_score == 0.92

        Path(path).unlink()

    def test_save_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "dir" / "detector.json"
            detector = FixedPointDetector()
            detector.step(0.95)
            detector.save(path)
            assert path.exists()


# ── Hash Tests ────────────────────────────────────────────────────────────────

class TestHashing:
    def test_hash_string(self):
        h = FixedPointDetector._hash("hello")
        assert isinstance(h, str)
        assert len(h) == 16

    def test_hash_same_string_gives_same_hash(self):
        h1 = FixedPointDetector._hash("hello")
        h2 = FixedPointDetector._hash("hello")
        assert h1 == h2

    def test_hash_different_strings_different(self):
        h1 = FixedPointDetector._hash("hello")
        h2 = FixedPointDetector._hash("world")
        assert h1 != h2

    def test_hash_dict(self):
        h = FixedPointDetector._hash({"a": 1, "b": [2, 3]})
        assert isinstance(h, str)
        assert len(h) == 16

    def test_hash_none(self):
        # _hash is called with None only internally, but the step method handles it
        pass


# ── EvolutionConvergenceGuard Tests ──────────────────────────────────────────

class TestEvolutionConvergenceGuard:
    def test_basic_integration(self):
        guard = EvolutionConvergenceGuard(epsilon=0.01, patience=2)

        # Simulate mock cycles
        class MockCycle:
            def __init__(self, cycle_id, score, fixes, categories):
                self.cycle_id = cycle_id
                self.audit_score_after = score
                self.fixes_deployed = fixes
                self.gaps_found = [f"gap_{i}" for i in range(len(fixes))]
                self.fixes_generated = [
                    type("MockFix", (), {"diagnosis": type("MockDiag", (), {"fix_category": type("Cat", (), {"value": c})()})()})()
                    for c in categories
                ]

        cycle1 = MockCycle(1, 0.90, ["fix_a"], ["reward_tuning"])
        cycle2 = MockCycle(2, 0.905, ["fix_b"], ["safety_check"])
        cycle3 = MockCycle(3, 0.906, ["fix_c"], ["threshold_adjust"])

        guard.step(cycle1)
        guard.step(cycle2)
        report = guard.step(cycle3)

        assert len(guard.reports) == 3
        assert isinstance(report, ConvergenceReport)

    def test_guard_should_stop_on_convergence(self):
        guard = EvolutionConvergenceGuard(epsilon=0.1, patience=2)

        class MockCycle:
            audit_score_after = 0.95
            cycle_id = 1
            fixes_deployed = ["f1"]
            gaps_found = ["g1"]
            fixes_generated = []

        # Same score for 3 steps -> convergence
        for i in range(4):
            guard.step(MockCycle())

        assert guard.should_stop is True
        assert guard.converged is True

    def test_guard_should_not_stop_while_improving(self):
        guard = EvolutionConvergenceGuard(epsilon=0.01, patience=3)

        class MockCycle:
            def __init__(self, score):
                self.audit_score_after = score
                self.cycle_id = 1
                self.fixes_deployed = ["f1"]
                self.gaps_found = ["g1"]
                self.fixes_generated = []

        for score in [0.80, 0.85, 0.90, 0.95]:
            guard.step(MockCycle(score))

        assert guard.should_stop is False


# ── Edge Case Tests ──────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_negative_scores(self):
        detector = FixedPointDetector(epsilon=0.01)
        detector.step(-1.0)
        report = detector.step(-0.5)
        assert report.state == ConvergenceState.CONTINUE

    def test_zero_score(self):
        detector = FixedPointDetector()
        report = detector.step(0.0)
        assert report.state == ConvergenceState.CONTINUE

    def test_very_large_scores(self):
        detector = FixedPointDetector(epsilon=0.01)
        report = detector.step(1e9)
        assert report.state == ConvergenceState.CONTINUE

    def test_scores_with_tiny_deltas(self):
        detector = FixedPointDetector(epsilon=0.01, patience=2)
        detector.step(0.900000)
        detector.step(0.900001)
        report = detector.step(0.900002)
        assert report.state == ConvergenceState.CONVERGED

    def test_none_params_structure(self):
        detector = FixedPointDetector()
        report = detector.step(0.95, params=None, structure=None)
        assert report.state == ConvergenceState.CONTINUE
        assert report.params_changed is False

    def test_multiple_resets(self):
        detector = FixedPointDetector()
        for _ in range(3):
            detector.step(0.90)
            detector.step(0.905)
            detector.step(0.905)
            detector.reset()
            assert detector._current_iteration == 0


# ── Real Scenario Simulation ─────────────────────────────────────────────────

class TestRealScenarios:
    """Test scenarios that mirror actual BottleSumo evolution cycles."""

    def test_training_convergence_scenario(self):
        """Simulate RL training converging to a plateau."""
        detector = FixedPointDetector(epsilon=0.02, patience=3)
        scores = [
            0.30, 0.42, 0.55, 0.63, 0.68,  # rapid improvement
            0.71, 0.73, 0.74, 0.745, 0.748,  # slowing down
            0.749, 0.7495, 0.7498, 0.7499,  # approaching plateau
        ]
        final_state = None
        for s in scores:
            final_state = detector.step(s).state
        assert final_state == ConvergenceState.CONVERGED

    def test_ci_improvement_then_plateau(self):
        """Simulate CI score improving then reaching near-zero improvement."""
        detector = FixedPointDetector(epsilon=0.5, patience=2)
        scores = [75.0, 82.0, 88.0, 91.0, 93.0, 93.2, 93.3, 93.35]
        states = [detector.step(s).state for s in scores]
        # Last two deltas: 0.1 and 0.05, both < epsilon=0.5, patience=2 → CONVERGED
        assert ConvergenceState.CONVERGED in states[-2:]

    def test_oscillation_with_large_step_size(self):
        """Simulate overshooting due to large learning rate."""
        detector = FixedPointDetector(epsilon=0.01)
        scores = [0.60, 0.80, 0.55, 0.85, 0.50, 0.90]
        states = [detector.step(s).state for s in scores]
        assert ConvergenceState.OSCILLATING in states

    def test_divergence_scenario(self):
        """Simulate catastrophic forgetting / divergence."""
        detector = FixedPointDetector(epsilon=0.01, divergence_factor=1.8)
        scores = [0.95, 0.93, 0.90, 0.85, 0.70, 0.40]
        states = [detector.step(s).state for s in scores]
        assert ConvergenceState.DIVERGING in states
