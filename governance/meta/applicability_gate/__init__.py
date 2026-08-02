"""P2 ApplicabilityGate — prevent governance misuse.

Determines if Agent Governance is suitable for a given task.
"""
from governance.meta.applicability_gate.engine import ApplicabilityGate
from governance.meta.applicability_gate.models import (
    ApplicabilityFeatures,
    ApplicabilityScore,
    FeedbackSample,
    GateDecision,
    TaskDescriptor,
)

__all__ = [
    "ApplicabilityFeatures",
    "ApplicabilityGate",
    "ApplicabilityScore",
    "FeedbackSample",
    "GateDecision",
    "TaskDescriptor",
]
