"""P2 ApplicabilityGate — models for task applicability classification.

Determines whether a given task/scenario is suitable for Agent Governance
by extracting 8 applicability features and running a lightweight classifier.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateDecision(str, Enum):
    ALLOW = "allow"        # score >= 0.7 — full governance applies
    REVIEW = "review"      # score 0.3-0.7 — human review recommended
    REJECT = "reject"      # score < 0.3 — governance not applicable


@dataclass
class TaskDescriptor:
    """Raw task input before feature extraction."""

    task_id: str
    category: str                          # e.g. "rl_training", "code_generation"
    description: str                       # free-text task description
    domain: str = "unknown"                # robotics / nlp / vision / general
    complexity: float = 0.5                # 0-1, estimated task complexity
    safety_critical: bool = False          # could actions cause harm?
    has_ground_truth: bool = True          # can outcomes be objectively verified?
    environment: str = "simulation"        # simulation / real_world / hybrid
    tags: list[str] = field(default_factory=list)


@dataclass
class ApplicabilityFeatures:
    """8-dim feature vector extracted from a TaskDescriptor."""

    # Feature 1: Verifiability — can outputs be objectively measured?
    verifiability: float = 0.0  # 0 (subjective) → 1 (fully verifiable)

    # Feature 2: Action Safety — how risky are actions?
    action_safety: float = 0.0  # 0 (unsafe) → 1 (completely safe)

    # Feature 3: Feedback Quality — how rich is the reward signal?
    feedback_quality: float = 0.0  # 0 (sparse/noisy) → 1 (dense/clean)

    # Feature 4: Domain Maturity — how mature is the domain's tooling?
    domain_maturity: float = 0.0  # 0 (novel/chaotic) → 1 (well-established)

    # Feature 5: Complexity Score — normalized task complexity
    complexity_score: float = 0.0  # 0 (trivial) → 1 (extremely complex)

    # Feature 6: Environment Control — how controlled is the environment?
    env_control: float = 0.0  # 0 (uncontrolled real-world) → 1 (fully simulated)

    # Feature 7: Governance History — has this domain been governed before?
    governance_history: float = 0.0  # 0 (no prior) → 1 (extensive prior)

    # Feature 8: Stakeholder Count — how many agents/actors involved?
    # (normalized: 0=solo, 1=3+ agents)
    stakeholder_count: float = 0.0

    def to_vector(self) -> list[float]:
        """Return feature vector for classifier input."""
        return [
            self.verifiability,
            self.action_safety,
            self.feedback_quality,
            self.domain_maturity,
            self.complexity_score,
            self.env_control,
            self.governance_history,
            self.stakeholder_count,
        ]

    @classmethod
    def from_vector(cls, vec: list[float]) -> ApplicabilityFeatures:
        """Create from a model output vector."""
        if len(vec) >= 8:
            return cls(*vec[:8])
        return cls()


@dataclass
class ApplicabilityScore:
    """Classifier output + reasoning."""

    score: float                          # [0, 1] raw probability
    decision: GateDecision = GateDecision.REVIEW
    confidence: float = 0.0               # classifier confidence
    features: ApplicabilityFeatures | None = None
    reasoning: str = ""                   # human-readable explanation
    threshold_allow: float = 0.7
    threshold_reject: float = 0.3

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "decision": self.decision.value,
            "confidence": self.confidence,
            "features": (
                self.features.to_vector() if self.features else None
            ),
            "reasoning": self.reasoning,
            "threshold_allow": self.threshold_allow,
            "threshold_reject": self.threshold_reject,
        }


@dataclass
class FeedbackSample:
    """Post-hoc feedback for classifier training."""

    task: TaskDescriptor
    predicted_score: float
    actual_outcome: float       # 1.0 = governance helped, 0.0 = governance hurt
    timestamp: float = 0.0
    notes: str = ""
