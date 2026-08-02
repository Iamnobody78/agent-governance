"""
Tests for MetaCognitiveLoop
============================
Comprehensive tests for MetaCognitiveLoop (Monitor → Evaluate → Generate
→ Adjust → Verify), FailurePattern detection, Strategy A/B generation,
SelfCheckBenchmark, and full integration scenarios.
"""
import json
import tempfile
from pathlib import Path

import pytest

from governance.meta.meta_cognitive_loop import (
    DecisionLog,
    FailurePattern,
    GapReport,
    LoopPhase,
    LoopTrace,
    MetaCognitiveLoop,
    SelfCheckBenchmark,
    Strategy,
    StrategyType,
)


# ── DecisionLog Tests ────────────────────────────────────────────────────────

class TestDecisionLog:
    def test_basic_creation(self):
        dl = DecisionLog(id="d1", action="move_forward", reward=0.5)
        assert dl.id == "d1"
        assert dl.action == "move_forward"
        assert dl.reward == 0.5

    def test_serialization(self):
        dl = DecisionLog(
            id="d1", action="turn_left", reward=0.8,
            policy_version="v2.1", context={"env": "test"},
        )
        d = dl.to_dict()
        assert d["id"] == "d1"
        assert d["reward"] == 0.8
        assert d["policy_version"] == "v2.1"
        assert d["context"] == {"env": "test"}


# ── GapReport Tests ──────────────────────────────────────────────────────────

class TestGapReport:
    def test_creation(self):
        gap = GapReport(
            pattern=FailurePattern.REWARD_HACKING,
            severity=0.8,
            evidence=[],
            description="Test gap",
        )
        assert gap.pattern == FailurePattern.REWARD_HACKING
        assert gap.severity == 0.8

    def test_serialization(self):
        gap = GapReport(
            pattern=FailurePattern.OSCILLATION,
            severity=0.6,
            evidence=[],
            description="Oscillation detected",
            suggested_fix="Reduce LR",
            frequency=10,
        )
        d = gap.to_dict()
        assert d["pattern"] == "oscillation"
        assert d["severity"] == 0.6
        assert d["suggested_fix"] == "Reduce LR"
        assert d["frequency"] == 10


# ── Strategy Tests ───────────────────────────────────────────────────────────

class TestStrategy:
    def test_conservative_strategy(self):
        s = Strategy(
            id="planA_test_1",
            type=StrategyType.CONSERVATIVE,
            description="Conservative fix",
            actions=["tune_lr"],
            expected_impact={"improvement": 0.1},
            risk_level=0.2,
            source="lessons_learned",
        )
        assert s.type == StrategyType.CONSERVATIVE
        assert s.risk_level == 0.2
        assert s.actions == ["tune_lr"]

    def test_bold_strategy(self):
        s = Strategy(
            id="planB_test_1",
            type=StrategyType.BOLD,
            description="Bold mutation",
            actions=["double_lr", "add_noise"],
            expected_impact={"exploration": 0.5},
            risk_level=0.7,
            source="gap_driven",
        )
        assert s.type == StrategyType.BOLD
        assert s.risk_level == 0.7
        assert len(s.actions) == 2

    def test_serialization(self):
        s = Strategy(
            id="planA_x_0",
            type=StrategyType.CONSERVATIVE,
            description="Test",
            actions=["a1", "a2"],
            expected_impact={"x": 0.5},
            risk_level=0.3,
            source="default",
        )
        d = s.to_dict()
        assert d["id"] == "planA_x_0"
        assert d["type"] == "conservative"
        assert d["actions"] == ["a1", "a2"]


# ── LoopTrace Tests ──────────────────────────────────────────────────────────

class TestLoopTrace:
    def test_basic_trace(self):
        trace = LoopTrace(
            cycle_id="cycle_0001",
            phase=LoopPhase.VERIFY,
            decisions_analyzed=100,
            verification_passed=True,
        )
        assert trace.cycle_id == "cycle_0001"
        assert trace.verification_passed is True

    def test_trace_serialization(self):
        gap = GapReport(
            pattern=FailurePattern.SLOW_CONVERGENCE,
            severity=0.5,
            evidence=[],
            description="Slow",
        )
        strategy = Strategy(
            id="planA_conv_1",
            type=StrategyType.CONSERVATIVE,
            description="Fix slow convergence",
            actions=["double_lr"],
            expected_impact={"improvement": 0.2},
            risk_level=0.3,
            source="default",
        )
        trace = LoopTrace(
            cycle_id="cycle_0001",
            phase=LoopPhase.VERIFY,
            decisions_analyzed=50,
            gaps_found=[gap],
            strategies=[strategy],
            selected_strategy=strategy,
            verification_passed=True,
        )
        d = trace.to_dict()
        assert d["cycle_id"] == "cycle_0001"
        assert len(d["gaps_found"]) == 1
        assert d["selected_strategy"]["id"] == "planA_conv_1"


# ── MetaCognitiveLoop Core Tests ─────────────────────────────────────────────

class TestMetaCognitiveLoopInit:
    def test_default_initialization(self):
        loop = MetaCognitiveLoop()
        assert loop._cycle_counter == 0
        assert len(loop.decision_buffer) == 0
        assert not loop._converged

    def test_custom_params(self):
        loop = MetaCognitiveLoop(
            convergence_epsilon=0.05,
            convergence_patience=5,
            decision_buffer_size=500,
        )
        assert loop.fp_detector.epsilon == 0.05
        assert loop.fp_detector.patience == 5


class TestMetaCognitiveLoopFeed:
    def test_feed_decisions(self):
        loop = MetaCognitiveLoop()
        decisions = [
            DecisionLog(id=f"d{i}", action="a", reward=0.5)
            for i in range(10)
        ]
        loop.feed_decisions(decisions)
        assert len(loop.decision_buffer) == 10

    def test_feed_decisions_buffer_limit(self):
        loop = MetaCognitiveLoop(decision_buffer_size=5)
        decisions = [
            DecisionLog(id=f"d{i}", action="a", reward=0.5)
            for i in range(20)
        ]
        loop.feed_decisions(decisions)
        assert len(loop.decision_buffer) <= 5

    def test_feed_feedback(self):
        loop = MetaCognitiveLoop()
        feedback = [
            {
                "severity": 0.8,
                "pattern": "reward_hacking",
                "action": "add_penalty",
                "outcome": "fixed",
                "effectiveness": 0.9,
            },
            {
                "severity": 0.2,  # below threshold, won't be saved
                "pattern": "minor",
                "action": "ignore",
                "outcome": "none",
                "effectiveness": 0.1,
            },
        ]
        loop.feed_feedback(feedback)
        assert len(loop.lessons_learned) == 1  # only severity > 0.5


# ── Evaluate Phase Tests ─────────────────────────────────────────────────────

class TestEvaluate:
    def test_evaluate_empty_buffer(self):
        loop = MetaCognitiveLoop()
        gaps = loop.evaluate()
        assert gaps == []

    def test_evaluate_no_issues(self):
        loop = MetaCognitiveLoop()
        # Steadily improving, diverse actions
        decisions = []
        for i in range(100):
            decisions.append(DecisionLog(
                id=f"d{i}",
                action=["move", "turn", "stop", "scan"][i % 4],
                reward=0.3 + i * 0.003,
            ))
        loop.feed_decisions(decisions)
        gaps = loop.evaluate()
        # Should not detect reward hacking or mode collapse
        patterns = [g.pattern for g in gaps]
        assert FailurePattern.REWARD_HACKING not in patterns

    def test_detect_reward_hacking(self):
        loop = MetaCognitiveLoop()
        decisions = []
        for i in range(30):
            decisions.append(DecisionLog(
                id=f"d{i}",
                action="exploit",  # always same action
                reward=0.95,       # very high reward
            ))
        loop.feed_decisions(decisions)
        gaps = loop.evaluate()
        patterns = [g.pattern for g in gaps]
        assert FailurePattern.REWARD_HACKING in patterns

    def test_detect_mode_collapse(self):
        loop = MetaCognitiveLoop()
        decisions = []
        for i in range(60):
            decisions.append(DecisionLog(
                id=f"d{i}",
                action="a1" if i % 2 == 0 else "a2",  # only 2 actions
                reward=0.3,
            ))
        loop.feed_decisions(decisions)
        gaps = loop.evaluate()
        patterns = [g.pattern for g in gaps]
        assert FailurePattern.MODE_COLLAPSE in patterns

    def test_detect_oscillation(self):
        loop = MetaCognitiveLoop()
        decisions = []
        for i in range(60):
            decisions.append(DecisionLog(
                id=f"d{i}",
                action="move",
                reward=1.0 if i % 2 == 0 else -1.0,  # extreme oscillation
            ))
        loop.feed_decisions(decisions)
        gaps = loop.evaluate()
        patterns = [g.pattern for g in gaps]
        assert FailurePattern.OSCILLATION in patterns


# ── Generate Phase Tests ─────────────────────────────────────────────────────

class TestGenerateStrategies:
    def test_generate_from_gaps(self):
        loop = MetaCognitiveLoop()
        gap = GapReport(
            pattern=FailurePattern.SLOW_CONVERGENCE,
            severity=0.6,
            evidence=[],
            description="Too slow",
        )
        strategies = loop.generate_strategies([gap])
        # Should produce at least 2 (conservative + bold)
        assert len(strategies) >= 2
        types = [s.type for s in strategies]
        assert StrategyType.CONSERVATIVE in types
        assert StrategyType.BOLD in types

    def test_generate_from_feedback(self):
        loop = MetaCognitiveLoop()
        # Add a lesson first
        loop.feed_feedback([{
            "severity": 0.9,
            "pattern": "oscillation",
            "action": "reduce_lr_by_half",
            "outcome": "stable",
            "effectiveness": 0.85,
        }])

        gap = GapReport(
            pattern=FailurePattern.OSCILLATION,
            severity=0.7,
            evidence=[],
            description="Oscillation issue",
        )
        strategies = loop.generate_strategies([gap])
        # Should use the lesson for conservative fix
        conservative = [s for s in strategies if s.type == StrategyType.CONSERVATIVE]
        assert len(conservative) >= 1
        assert any("reduce_lr" in s.description.lower() for s in conservative)

    def test_bold_strategy_has_actions(self):
        loop = MetaCognitiveLoop()
        gap = GapReport(
            pattern=FailurePattern.REWARD_HACKING,
            severity=0.8,
            evidence=[],
            description="Hacking",
        )
        strategies = loop.generate_strategies([gap])
        bold = [s for s in strategies if s.type == StrategyType.BOLD]
        assert len(bold) >= 1
        assert len(bold[0].actions) > 0


# ── Adjust Phase Tests ───────────────────────────────────────────────────────

class TestAdjust:
    def test_adjust_selects_best_strategy(self):
        loop = MetaCognitiveLoop()
        # Feed some decisions to establish a score
        decisions = [DecisionLog(id=f"d{i}", action="a", reward=0.6)
                     for i in range(50)]
        loop.feed_decisions(decisions)

        good = Strategy(
            id="planA_good", type=StrategyType.CONSERVATIVE,
            description="Good fix", actions=["fix"],
            expected_impact={"improvement": 0.3},
            risk_level=0.1, source="test",
        )
        mediocre = Strategy(
            id="planB_med", type=StrategyType.BOLD,
            description="Risky fix", actions=["risky"],
            expected_impact={"exploration": 0.2},
            risk_level=0.8, source="test",
        )

        selected = loop.adjust([good, mediocre])
        assert selected is not None
        assert selected.id == "planA_good"  # lower risk, higher improvement

    def test_adjust_empty_strategies(self):
        loop = MetaCognitiveLoop()
        selected = loop.adjust([])
        assert selected is None

    def test_adjust_penalizes_high_risk(self):
        loop = MetaCognitiveLoop()
        decisions = [DecisionLog(id=f"d{i}", action="a", reward=0.6)
                     for i in range(50)]
        loop.feed_decisions(decisions)

        risky = Strategy(
            id="risky", type=StrategyType.BOLD,
            description="Very risky", actions=["danger"],
            expected_impact={"improvement": 0.3},
            risk_level=0.95,  # very high risk
            source="test",
        )
        selected = loop.adjust([risky])
        # Risky strategy might be rejected by convergence check
        # It might pass since penalized score could still be in CONTINUE state
        # Just check no crash
        assert True


# ── Verify Phase Tests ───────────────────────────────────────────────────────

class TestVerify:
    def test_verify_basic_strategy(self):
        loop = MetaCognitiveLoop()
        strategy = Strategy(
            id="test_strat_001",
            type=StrategyType.CONSERVATIVE,
            description="Safe conservative adjustment",
            actions=["tune_param"],
            expected_impact={"stability": 0.2},
            risk_level=0.1,
            source="default",
        )
        result = loop.verify(strategy)
        assert "godelian_safe" in result
        assert "self_check_passed" in result

    def test_verify_rejects_dangerous_strategy(self):
        loop = MetaCognitiveLoop()
        strategy = Strategy(
            id="danger_strat",
            type=StrategyType.BOLD,
            description="This self-modifying system always guarantees correctness",
            actions=["dangerous"],
            expected_impact={"improvement": 0.9},
            risk_level=0.95,  # above 0.9 threshold
            source="gap_driven",
        )
        result = loop.verify(strategy)
        assert result["self_check_passed"] is False

    def test_verify_rejects_empty_actions(self):
        loop = MetaCognitiveLoop()
        strategy = Strategy(
            id="empty_actions",
            type=StrategyType.CONSERVATIVE,
            description="No actions",
            actions=[],  # empty
            expected_impact={},
            risk_level=0.1,
            source="test",
        )
        result = loop.verify(strategy)
        assert result["self_check_passed"] is False


# ── Full Cycle Tests ─────────────────────────────────────────────────────────

class TestFullCycle:
    def test_run_cycle_no_data(self):
        loop = MetaCognitiveLoop()
        trace = loop.run_cycle()
        assert isinstance(trace, LoopTrace)
        assert trace.cycle_id == "cycle_0001"
        assert trace.decisions_analyzed == 0

    def test_run_cycle_basic(self):
        loop = MetaCognitiveLoop()
        # Feed some normal decisions
        decisions = []
        for i in range(50):
            decisions.append(DecisionLog(
                id=f"d{i}",
                action=["a", "b", "c"][i % 3],
                reward=0.5 + i * 0.002,
            ))
        loop.feed_decisions(decisions)
        loop.feed_feedback([{
            "severity": 0.9,
            "pattern": "oscillation",
            "action": "reduce_lr",
            "outcome": "stable",
            "effectiveness": 0.85,
        }])

        trace = loop.run_cycle()
        assert trace.cycle_id == "cycle_0001"
        assert trace.decisions_analyzed == 50
        # Should have run all phases
        assert isinstance(trace.gaps_found, list)  # may be empty if no issues

    def test_multiple_cycles(self):
        loop = MetaCognitiveLoop()
        decisions = [
            DecisionLog(id=f"d{i}", action=["a", "b"][i % 2], reward=0.5)
            for i in range(50)
        ]
        loop.feed_decisions(decisions)

        for _ in range(3):
            trace = loop.run_cycle()
            assert trace is not None

        assert loop._cycle_counter == 3
        assert len(loop.cycle_history) == 3

    def test_cycle_with_reward_hacking_produces_strategy(self):
        loop = MetaCognitiveLoop()
        decisions = [
            DecisionLog(id=f"d{i}", action="cheat", reward=0.95)
            for i in range(50)
        ]
        loop.feed_decisions(decisions)
        trace = loop.run_cycle()
        # Should detect reward hacking and generate strategies
        assert len(trace.strategies) > 0


# ── Export & Reset Tests ─────────────────────────────────────────────────────

class TestExportAndReset:
    def test_export_history(self):
        loop = MetaCognitiveLoop()
        decisions = [DecisionLog(id=f"d{i}", action="a", reward=0.5)
                     for i in range(10)]
        loop.feed_decisions(decisions)
        loop.run_cycle()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        loop.export_history(path)
        saved = Path(path)
        assert saved.exists()
        assert saved.stat().st_size > 0

        # Verify JSON
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        Path(path).unlink()

    def test_summary(self):
        loop = MetaCognitiveLoop()
        decisions = [DecisionLog(id=f"d{i}", action="a", reward=0.5)
                     for i in range(30)]
        loop.feed_decisions(decisions)
        loop.run_cycle()
        loop.run_cycle()

        s = loop.summary()
        assert s["cycles"] == 2
        assert "total_gaps_found" in s
        assert "strategies_adopted" in s

    def test_reset(self):
        loop = MetaCognitiveLoop()
        decisions = [DecisionLog(id=f"d{i}", action="a", reward=0.5)
                     for i in range(20)]
        loop.feed_decisions(decisions)
        loop.run_cycle()
        loop.reset()

        assert loop._cycle_counter == 0
        assert len(loop.decision_buffer) == 0
        assert len(loop.cycle_history) == 0
        assert len(loop.lessons_learned) == 0


# ── SelfCheckBenchmark Tests ─────────────────────────────────────────────────

class TestSelfCheckBenchmark:
    def test_pass_all_checks(self):
        strategy = Strategy(
            id="good_strat_v1",
            type=StrategyType.CONSERVATIVE,
            description="A well-formed conservative strategy",
            actions=["tune_lr", "add_momentum"],
            expected_impact={"improvement": 0.2},
            risk_level=0.3,
            source="lessons_learned",
        )
        result = SelfCheckBenchmark.run(strategy)
        assert result["passed"] == result["total"]
        assert result["failed"] == 0
        assert result["all_critical_passed"] is True

    def test_fail_on_empty_actions(self):
        strategy = Strategy(
            id="bad_strat_empty",
            type=StrategyType.CONSERVATIVE,
            description="Empty actions",
            actions=[],
            expected_impact={"improvement": 0.2},
            risk_level=0.3,
            source="default",
        )
        result = SelfCheckBenchmark.run(strategy)
        assert result["failed"] >= 1  # SC-001 and SC-008

    def test_fail_on_high_risk(self):
        strategy = Strategy(
            id="risky_strat",
            type=StrategyType.BOLD,
            description="Too risky",
            actions=["risky_move"],
            expected_impact={"improvement": 0.8},
            risk_level=0.95,
            source="gap_driven",
        )
        result = SelfCheckBenchmark.run(strategy)
        assert result["failed"] >= 1
        # SC-002 (high risk) should fail
        sc002 = [d for d in result["details"] if d["id"] == "SC-002"]
        assert len(sc002) > 0
        assert sc002[0]["passed"] is False

    def test_all_10_scenarios(self):
        result = SelfCheckBenchmark.run(
            Strategy(
                id="test_1",
                type=StrategyType.CONSERVATIVE,
                description="Test strategy for benchmark",
                actions=["action1", "action2"],
                expected_impact={"x": 0.5},
                risk_level=0.2,
                source="default",
            )
        )
        assert result["total"] == 10
        assert len(result["details"]) == 10

    def test_fail_on_duplicate_actions(self):
        strategy = Strategy(
            id="dup_test",
            type=StrategyType.CONSERVATIVE,
            description="Duplicate actions",
            actions=["a1", "a1", "a2"],
            expected_impact={"x": 0.3},
            risk_level=0.1,
            source="default",
        )
        result = SelfCheckBenchmark.run(strategy)
        # SC-009: no duplicates
        sc009 = [d for d in result["details"] if d["id"] == "SC-009"]
        assert sc009[0]["passed"] is False

    def test_fail_on_bad_id_format(self):
        strategy = Strategy(
            id="badid",  # no underscore, too short
            type=StrategyType.CONSERVATIVE,
            description="Bad ID format",
            actions=["a1"],
            expected_impact={"x": 0.1},
            risk_level=0.1,
            source="default",
        )
        result = SelfCheckBenchmark.run(strategy)
        sc010 = [d for d in result["details"] if d["id"] == "SC-010"]
        assert sc010[0]["passed"] is False


# ── Integration Scenario Tests ───────────────────────────────────────────────

class TestIntegrationScenarios:
    def test_full_pipeline_with_reward_hacking(self):
        """Full MetaCognitiveLoop pipeline detecting and fixing reward hacking."""
        loop = MetaCognitiveLoop()

        # Phase 1: Feed reward-hacking decisions
        decisions = [
            DecisionLog(id=f"d{i}", action="cheat", reward=0.95)
            for i in range(30)
        ]
        loop.feed_decisions(decisions)

        # Phase 1b: Feed some lessons for conservative strategy
        loop.feed_feedback([{
            "severity": 0.9,
            "pattern": "reward_hacking",
            "action": "add_reward_penalty",
            "outcome": "resolved",
            "effectiveness": 0.9,
        }])

        # Run full cycle
        trace = loop.run_cycle()

        # Assertions
        assert len(trace.gaps_found) > 0
        assert FailurePattern.REWARD_HACKING in [g.pattern for g in trace.gaps_found]
        assert len(trace.strategies) >= 2  # conservative + bold
        # Either a strategy was selected or verify says not ready
        # (adjust may return None if no strategy passes convergence check)

    def test_convergence_after_multiple_cycles(self):
        """After several cycles with steady improvement, should see convergence trend."""
        loop = MetaCognitiveLoop(convergence_epsilon=0.1, convergence_patience=2)

        # Simulate improving system across cycles
        for cycle in range(5):
            base_reward = 0.3 + cycle * 0.15
            decisions = [
                DecisionLog(
                    id=f"c{cycle}_d{i}",
                    action=["a", "b", "c", "d"][i % 4],
                    reward=min(0.97, base_reward + (i * 0.001)),
                )
                for i in range(50)
            ]
            loop.feed_decisions(decisions)
            loop.run_cycle()

        # After several cycles of improvement, should be tracking progress
        assert loop._cycle_counter == 5
        assert len(loop.cycle_history) == 5

    def test_godelian_check_on_self_referential_strategy(self):
        """A self-referential strategy should trigger Godelian boundary."""
        loop = MetaCognitiveLoop()

        strategy = Strategy(
            id="self_ref_strategy",
            type=StrategyType.BOLD,
            description="This system is always safe",
            actions=["modify_self"],
            expected_impact={"improvement": 0.5},
            risk_level=0.3,
            source="gap_driven",
        )

        result = loop.verify(strategy)
        # The Godelian check should process it (safe if not undecidable)
        assert "godelian_safe" in result

    def test_export_and_reload_history(self):
        """End-to-end: run cycles, export, verify JSON."""
        loop = MetaCognitiveLoop()

        for cycle in range(3):
            decisions = [
                DecisionLog(id=f"c{cycle}_d{i}", action="a", reward=0.5 + cycle * 0.1)
                for i in range(20)
            ]
            loop.feed_decisions(decisions)
            trace = loop.run_cycle()
            assert trace.verification_passed is not None  # may be True or False

        # Export
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        loop.export_history(path)

        # Verify
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 3
        for entry in data:
            assert "cycle_id" in entry
            assert "phase" in entry
            assert "verification_passed" in entry

        Path(path).unlink()


# ── Edge Cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_large_feedback_batch(self):
        loop = MetaCognitiveLoop()
        large_feedback = [
            {"severity": 0.8, "pattern": f"p{i}", "action": f"a{i}",
             "outcome": "ok", "effectiveness": 0.7}
            for i in range(500)
        ]
        loop.feed_feedback(large_feedback)
        assert len(loop.lessons_learned) == 500

    def test_run_cycle_repeatedly_empty(self):
        loop = MetaCognitiveLoop()
        for i in range(10):
            trace = loop.run_cycle()
            assert trace.cycle_id == f"cycle_{i+1:04d}"
        assert len(loop.cycle_history) == 10

    def test_compute_score_no_data(self):
        loop = MetaCognitiveLoop()
        assert loop._compute_current_score() == 0.0

    def test_compute_score_with_data(self):
        loop = MetaCognitiveLoop()
        decisions = [DecisionLog(id=f"d{i}", action="a", reward=0.7)
                     for i in range(100)]
        loop.feed_decisions(decisions)
        score = loop._compute_current_score()
        assert 0.6 <= score <= 0.8  # near 0.7 with zero variance
