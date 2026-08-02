"""ApplicabilityGate feature extractor.

Converts a TaskDescriptor into an 8-dim ApplicabilityFeatures vector
using domain knowledge and keyword heuristics.

Feature design rationale:
  F1: Verifiability — RL + simulation → high. Creative tasks → low.
  F2: Action Safety — hardware control → low. Code review → high.
  F3: Feedback Quality — dense reward → high. Sparse → low.
  F4: Domain Maturity — robotics/simulation → mature. Custom/novel → immature.
  F5: Complexity Score — from descriptor (user-provided or inferred).
  F6: Environment Control — simulation → high. real_world → low.
  F7: Governance History — tracked per domain in history registry.
  F8: Stakeholder Count — single agent → 0, multi-agent → 1.
"""
from __future__ import annotations

import re

from governance.meta.applicability_gate.models import (
    ApplicabilityFeatures,
    TaskDescriptor,
)

# ── Domain maturity scores (0-1, higher = more mature) ──
DOMAIN_MATURITY = {
    "robotics": 0.85,
    "simulation": 0.90,
    "reinforcement_learning": 0.80,
    "rl": 0.80,
    "code_generation": 0.75,
    "code_review": 0.70,
    "testing": 0.85,
    "ci_cd": 0.90,
    "data_analysis": 0.80,
    "nlp": 0.70,
    "computer_vision": 0.75,
    "general": 0.50,
    "unknown": 0.30,
    "custom": 0.20,
}

# ── Safety category modifiers ──
SAFETY_BY_CATEGORY = {
    "rl_training": 0.6,
    "simulation": 0.8,
    "code_generation": 0.7,
    "code_review": 0.9,
    "deployment": 0.3,
    "hardware_control": 0.2,
    "audit": 0.9,
    "test": 0.9,
}

# ── Keyword-based verifiability signals ──
VERIFIABLE_KEYWORDS = [
    r"winrate", r"accuracy", r"loss", r"reward", r"score",
    r"pass", r"fail", r"benchmark", r"test", r"metric",
    r"precision", r"recall", r"f1", r"latency", r"throughput",
]

UNVERIFIABLE_KEYWORDS = [
    r"best", r"good", r"nice", r"beautiful", r"elegant",
    r"intuitive", r"creative", r"aesthetic",
]


class FeatureExtractor:
    """Extract 8 applicability features from a TaskDescriptor."""

    def __init__(self):
        self._governance_history: dict[str, float] = {
            "bottlesumo": 0.9,
            "rl_training": 0.85,
            "ci_cd": 0.95,
            "code_review": 0.80,
            "testing": 0.85,
        }

    # ── Public API ──────────────────────────────────────────────────────

    def extract(self, task: TaskDescriptor) -> ApplicabilityFeatures:
        """Extract all 8 features from a task descriptor."""
        return ApplicabilityFeatures(
            verifiability=self._compute_verifiability(task),
            action_safety=self._compute_safety(task),
            feedback_quality=self._compute_feedback_quality(task),
            domain_maturity=self._compute_domain_maturity(task),
            complexity_score=task.complexity,
            env_control=self._compute_env_control(task),
            governance_history=self._compute_governance_history(task),
            stakeholder_count=self._compute_stakeholder_count(task),
        )

    def extract_vector(self, task: TaskDescriptor) -> list[float]:
        """Extract features as a raw float vector."""
        return self.extract(task).to_vector()

    def register_history(self, domain: str, score: float) -> None:
        """Record governance success for a domain."""
        self._governance_history[domain] = max(
            0.0, min(1.0, score),
        )

    # ── Feature computations ────────────────────────────────────────────

    def _compute_verifiability(self, task: TaskDescriptor) -> float:
        """How objectively verifiable are the task's outcomes?"""
        if task.has_ground_truth is False:
            return 0.2

        text = (task.description + " " + task.category).lower()

        verifiable_hits = sum(
            1 for kw in VERIFIABLE_KEYWORDS if re.search(kw, text)
        )
        unverifiable_hits = sum(
            1 for kw in UNVERIFIABLE_KEYWORDS if re.search(kw, text)
        )

        base = 0.6 if task.has_ground_truth else 0.3
        base += 0.1 * verifiable_hits
        base -= 0.15 * unverifiable_hits
        return max(0.0, min(1.0, base))

    def _compute_safety(self, task: TaskDescriptor) -> float:
        """How safe are the actions this task involves?"""
        if task.safety_critical:
            return 0.1

        base = SAFETY_BY_CATEGORY.get(task.category, 0.5)

        # Modifiers from environment
        if task.environment == "real_world":
            base -= 0.2
        elif task.environment == "simulation":
            base += 0.1

        return max(0.0, min(1.0, base))

    def _compute_feedback_quality(self, task: TaskDescriptor) -> float:
        """How dense and reliable is the reward/feedback signal?"""
        text = (task.description + " " + task.category).lower()

        if task.environment == "simulation":
            base = 0.8
        elif task.environment == "real_world":
            base = 0.4
        else:
            base = 0.6

        # Dense reward signals
        if any(kw in text for kw in ["reward", "score", "metric", "loss"]):
            base += 0.1
        if "sparse" in text or "delayed" in text:
            base -= 0.15

        return max(0.0, min(1.0, base))

    def _compute_domain_maturity(self, task: TaskDescriptor) -> float:
        """How mature is the tooling in this domain?"""
        domain = task.domain.lower()
        for key, value in DOMAIN_MATURITY.items():
            if key in domain:
                return value
        # Try category as fallback
        cat = task.category.lower()
        for key, value in DOMAIN_MATURITY.items():
            if key in cat:
                return value
        return DOMAIN_MATURITY.get("unknown", 0.3)

    def _compute_env_control(self, task: TaskDescriptor) -> float:
        """How controlled is the execution environment?"""
        env = task.environment.lower()
        if env == "simulation":
            return 0.95
        if env == "hybrid":
            return 0.70
        if env == "real_world":
            return 0.25
        return 0.50

    def _compute_governance_history(self, task: TaskDescriptor) -> float:
        """Has this domain/category been governed before?"""
        # Check exact match first
        for key, score in self._governance_history.items():
            if key == task.category.lower() or key == task.domain.lower():
                return score
            if key in task.description.lower():
                return score
        return 0.1  # no prior governance

    def _compute_stakeholder_count(self, task: TaskDescriptor) -> float:
        """How many agents/actors are involved?"""
        text = (task.description + " " + " ".join(task.tags)).lower()
        count = 0
        if any(kw in text for kw in ["multi", "team", "collaborat", "swarm"]):
            count = 3
        elif any(kw in text for kw in ["dual", "pair", "two"]):
            count = 2
        elif any(kw in text for kw in ["single", "solo"]):
            count = 1

        if count == 0:
            count = 1  # default: single agent

        # P2's governance benefits from multi-agent setups
        return min(1.0, count / 3.0)
