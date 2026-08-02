"""Contract Tests — verify AgentInterface compliance."""

import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))



def test_bottlesumo_agent_implements_all_methods():
    """BottleSumoAgent must implement all 4 required methods."""
    from examples.bottlesumo.bottlesumo_agent import BottleSumoAgent
    agent = BottleSumoAgent()

    assert hasattr(agent, "observe"), "Missing observe()"
    assert hasattr(agent, "act"), "Missing act()"
    assert hasattr(agent, "get_metrics"), "Missing get_metrics()"
    assert hasattr(agent, "get_capabilities"), "Missing get_capabilities()"


def test_bottlesumo_agent_observe_returns_dict():
    """observe() must return a dict with state, timestamp, confidence."""
    from examples.bottlesumo.bottlesumo_agent import BottleSumoAgent
    agent = BottleSumoAgent()
    result = agent.observe()

    assert isinstance(result, dict), "observe() must return dict"
    assert "state" in result, "Missing 'state' key"
    assert "timestamp" in result, "Missing 'timestamp' key"
    assert "confidence" in result, "Missing 'confidence' key"
    assert 0.0 <= result["confidence"] <= 1.0, "Confidence out of range"


def test_bottlesumo_agent_act_returns_dict():
    """act() must return a dict with status, reward, done, info."""
    from examples.bottlesumo.bottlesumo_agent import BottleSumoAgent
    agent = BottleSumoAgent()
    result = agent.act(0)

    assert isinstance(result, dict), "act() must return dict"
    assert result["status"] in ("ok", "error"), "Status must be ok or error"


def test_bottlesumo_agent_get_metrics_returns_dict():
    """get_metrics() must return a dict with required keys."""
    from examples.bottlesumo.bottlesumo_agent import BottleSumoAgent
    agent = BottleSumoAgent()
    metrics = agent.get_metrics()

    assert isinstance(metrics, dict)
    assert "success_rate" in metrics
    assert "latency" in metrics
    assert "resource_usage" in metrics


def test_bottlesumo_agent_get_capabilities_returns_list():
    """get_capabilities() must return a list of strings."""
    from examples.bottlesumo.bottlesumo_agent import BottleSumoAgent
    agent = BottleSumoAgent()
    caps = agent.get_capabilities()

    assert isinstance(caps, list), "get_capabilities() must return list"
    assert len(caps) > 0, "Must have at least one capability"
    assert all(isinstance(c, str) for c in caps), "All capabilities must be strings"


def test_monotonic_constraint_import():
    """P3 monotonic constraint engine is importable."""
    from governance.meta.monotonic_constraint import MonotonicConstraint
    mc = MonotonicConstraint()
    r = mc.report()
    assert r["status"] == "cold_start"
    assert r["p3_health"] == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# P0: Meta-Theory Consistency Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_meta_theory_consistency_import():
    """P0 meta-theory checker is importable with class + constants."""
    from governance.meta.meta_theory_consistency import (
        CONFLICT_PAIRS,
        SEVERITY_WEIGHT,
        ConsistencyChecker,
    )
    assert len(CONFLICT_PAIRS) == 12, "Must have 12 conflict pairs"
    assert len(SEVERITY_WEIGHT) == 5, "Must have P0-P4 weights"
    checker = ConsistencyChecker()
    assert checker is not None


def test_meta_theory_consistency_conflict_detection():
    """detect_conflicts() returns a list of conflict dictionaries."""
    from governance.meta.meta_theory_consistency import ConsistencyChecker
    checker = ConsistencyChecker()
    conflicts = checker.detect_conflicts()
    assert isinstance(conflicts, list), "detect_conflicts must return a list"

    for c in conflicts:
        assert "layer_a" in c
        assert "layer_b" in c
        assert "severity" in c
        assert "description" in c
        assert c["severity"] in ("P0", "P1", "P2", "P3", "P4")


def test_meta_theory_consistency_compute_score():
    """compute_score() returns 0-100 with meaningful structure."""
    from governance.meta.meta_theory_consistency import ConsistencyChecker
    checker = ConsistencyChecker()
    # Force empty layers for a clean 100 baseline
    checker._layers = {}
    score = checker.compute_score()
    assert score["consistency_score"] == 100.0
    assert score["conflicts_found"] == 0
    assert score["status"] == "CONSISTENT"


def test_meta_theory_consistency_full_pipeline():
    """Full pipeline: detect -> compute -> report."""
    from governance.meta.meta_theory_consistency import ConsistencyChecker
    checker = ConsistencyChecker()
    checker.detect_conflicts()
    score = checker.compute_score()

    assert 0.0 <= score["consistency_score"] <= 100.0
    assert isinstance(score["conflicts_found"], int)
    assert score["status"] in ("CONSISTENT", "WARNING", "BLOCKED")
    
    # Full report
    report = checker.report()
    assert "consistency_score" in report
    assert "conflict_details" in report
