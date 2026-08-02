"""Deadlock Detection — verify Agent state machine is thread-safe."""

import pytest
import threading
import time
from pathlib import Path
import sys

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))


@pytest.mark.timeout(30)
def test_concurrent_agent_creation():
    """Multiple threads creating agents should not deadlock."""
    from examples.bottlesumo.bottlesumo_agent import BottleSumoAgent
    errors = []

    def create_and_use():
        try:
            agent = BottleSumoAgent()
            for _ in range(10):
                agent.observe()
                agent.act(0)
                agent.get_metrics()
                agent.get_capabilities()
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=create_and_use) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors, f"Concurrent errors: {errors}"


@pytest.mark.timeout(10)
def test_monotonic_constraint_thread_safety():
    """MonotonicConstraint should handle concurrent writes."""
    from governance.meta.monotonic_constraint import MonotonicConstraint
    mc = MonotonicConstraint()
    errors = []

    def record_batch():
        try:
            for i in range(50):
                mc.record_action(i % 21, hash(str(i)), safe=(i % 3 != 0))
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=record_batch) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    report = mc.report()
    assert report["safe_actions"] > 0, "No safe actions recorded"
    assert not errors, f"Thread safety errors: {errors}"
