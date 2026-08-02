"""
Reference Implementation: BottleSumo Agent

Demonstrates how to integrate a sumo robot agent with the
Agent Governance Framework by implementing AgentInterface.
"""
import time
import numpy as np
from pathlib import Path

# Import agent interface (when installed as package)
try:
    from governance.core.agent_interface import AgentInterface
except ImportError:
    # Fallback for running examples directly
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from governance.core.agent_interface import AgentInterface


class BottleSumoAgent(AgentInterface):
    """BottleSumo sumo robot agent with governance integration."""

    def __init__(self, env=None):
        self._env = env  # LightweightBottleSumoEnv or similar
        self._last_observation = None
        self._episode_rewards = []
        self._total_actions = 0
        self._successful_actions = 0

    def observe(self) -> dict:
        """Get current observation from the sumo arena."""
        if self._env is None:
            return {
                "state": np.zeros(7),
                "timestamp": time.time(),
                "confidence": 1.0,
            }
        obs = self._env.reset()[0] if self._last_observation is None else self._last_observation
        return {
            "state": obs,
            "timestamp": time.time(),
            "confidence": 0.9,
        }

    def act(self, action) -> dict:
        """Execute action in the sumo arena."""
        if self._env is None:
            return {"status": "ok", "reward": 0.0, "done": False, "info": {}}

        try:
            obs, reward, terminated, truncated, info = self._env.step(action)
            self._last_observation = obs
            self._total_actions += 1
            if reward > 0:
                self._successful_actions += 1
            self._episode_rewards.append(float(reward))

            return {
                "status": "ok",
                "reward": float(reward),
                "done": terminated or truncated,
                "info": info or {},
            }
        except Exception as e:
            return {
                "status": "error",
                "reward": -1.0,
                "done": True,
                "info": {"error": str(e)},
            }

    def get_metrics(self) -> dict:
        """Return current performance metrics."""
        total = max(self._total_actions, 1)
        return {
            "success_rate": self._successful_actions / total,
            "latency": 0.005,  # ~5ms per action in lightweight sim
            "resource_usage": 0.15,  # CPU-only, low usage
        }

    def get_capabilities(self) -> list:
        """Return agent capabilities for task routing."""
        return [
            "rl_training",
            "simulation",
            "edge_detection",
            "opponent_tracking",
            "push_control",
        ]


# ── Quick Test ──
if __name__ == "__main__":
    agent = BottleSumoAgent()
    print("BottleSumoAgent created successfully")
    obs = agent.observe()
    print(f"  observe: {obs['state'].shape}, confidence={obs['confidence']}")
    result = agent.act(0)
    print(f"  act: {result['status']}")
    metrics = agent.get_metrics()
    print(f"  metrics: {metrics}")
    caps = agent.get_capabilities()
    print(f"  capabilities: {caps}")
