"""
Agent Interface — The 4 methods every Agent must implement.

This is the core contract between any Agent and the Governance Framework.
Implement these 4 methods and your Agent gains access to all governance
capabilities: safety guardrails, shadow-loop self-evolution, meta-audit,
ABDL rule evaluation, reputation tracking, and more.
"""
from abc import ABC, abstractmethod
from typing import Any


class AgentInterface(ABC):
    """Domain-agnostic base class for all Agents under governance.

    To integrate your Agent:
    1. Inherit from this class
    2. Implement all 4 abstract methods
    3. Call `python scripts/register_agent.py --agent my_agent.py`
    """

    @abstractmethod
    def observe(self) -> dict[str, Any]:
        """Return the current observation of the agent's environment.

        Must include:
            - state: current state representation (list, array, or dict)
            - timestamp: float (time.time())
            - confidence: float (0.0-1.0)

        Returns:
            dict with at minimum {"state": ..., "timestamp": ..., "confidence": ...}
        """
        pass

    @abstractmethod
    def act(self, action: Any) -> dict[str, Any]:
        """Execute the given action and return the result.

        Args:
            action: Action to execute (format depends on agent domain)

        Returns:
            dict with {"status": "ok"|"error", "reward": float,
                       "done": bool, "info": dict}
        """
        pass

    @abstractmethod
    def get_metrics(self) -> dict[str, float]:
        """Return current runtime metrics.

        Must include:
            - success_rate: float (0.0-1.0)
            - latency: float (seconds per action)
            - resource_usage: float (0.0-1.0)

        Returns:
            dict of metric_name -> float_value
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return list of agent capabilities.

        Examples: ["rl_training", "simulation", "hardware_control", "code_generation"]

        Used by the meta-scheduler for task routing and capability-aware
        resource allocation.
        """
        pass

    # ── Optional hooks (override if needed) ──

    def on_governance_alert(self, alert: dict[str, Any]) -> None:  # noqa: B027
        """Called when the governance layer issues an alert for this agent."""
        pass

    def on_evolution_patch(self, patch: str) -> bool:
        """Called when self-evolution engine proposes a patch.
        Return True to accept, False to reject.
        """
        return False  # Default: human review required

    def shutdown(self) -> None:  # noqa: B027
        """Cleanup resources before agent termination."""
        pass
