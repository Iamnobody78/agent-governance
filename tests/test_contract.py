"""Contract Tests — verify AgentInterface compliance."""

import pytest
import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))

from governance.core.agent_interface import AgentInterface


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
