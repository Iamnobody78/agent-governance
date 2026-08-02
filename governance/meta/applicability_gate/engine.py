"""ApplicabilityGate engine — classify tasks for governance applicability.

Ties together extractor + classifier + decision thresholds.
"""
from __future__ import annotations

from governance.meta.applicability_gate.classifier import ApplicabilityClassifier
from governance.meta.applicability_gate.extractor import FeatureExtractor
from governance.meta.applicability_gate.models import (
    ApplicabilityScore,
    GateDecision,
    TaskDescriptor,
)


class ApplicabilityGate:
    """P2 gate: determines if a task is suitable for Agent Governance."""

    THRESHOLD_ALLOW = 0.7
    THRESHOLD_REJECT = 0.3

    def __init__(self, classifier: ApplicabilityClassifier | None = None):
        self._extractor = FeatureExtractor()
        self._classifier = classifier or ApplicabilityClassifier()

    # ── Public API ──────────────────────────────────────────────────────

    def evaluate(self, task: TaskDescriptor) -> ApplicabilityScore:
        """Evaluate a task and return applicability score.

        This is the main entry point for the P2 gate.
        """
        features = self._extractor.extract(task)
        score = self._classifier.predict(features.to_vector())

        decision = self._classify(score)
        confidence = self._compute_confidence(score)
        reasoning = self._generate_reasoning(task, features, score, decision)

        return ApplicabilityScore(
            score=round(score, 4),
            decision=decision,
            confidence=round(confidence, 4),
            features=features,
            reasoning=reasoning,
            threshold_allow=self.THRESHOLD_ALLOW,
            threshold_reject=self.THRESHOLD_REJECT,
        )

    def evaluate_batch(self, tasks: list[TaskDescriptor]) -> list[ApplicabilityScore]:
        """Evaluate multiple tasks."""
        return [self.evaluate(t) for t in tasks]

    def register_feedback(self, domain: str, success: bool) -> None:
        """Record governance feedback for a domain."""
        self._extractor.register_history(
            domain, 1.0 if success else 0.0,
        )

    def ci_check(self, tasks: list[TaskDescriptor] | None = None) -> int:
        """CI entry point. Returns exit code.

        0 = all tasks pass gate
        1 = at least one task rejected
        """
        if tasks is None:
            tasks = self._default_ci_tasks()

        results = self.evaluate_batch(tasks)
        rejected = [r for r in results if r.decision == GateDecision.REJECT]
        review = [r for r in results if r.decision == GateDecision.REVIEW]

        for r in results:
            print(
                f"APPLICABILITY: {r.decision.value:6} "
                f"score={r.score:.3f} conf={r.confidence:.3f} "
                f"| {r.reasoning[:80]}"
            )

        if rejected:
            print(f"\nREJECTED: {len(rejected)} tasks not suitable for governance")
            return 1
        if review:
            print(f"\nREVIEW: {len(review)} tasks flagged for human review")
            return 0  # review is not a failure — it's a human decision

        return 0

    def get_features(self, task: TaskDescriptor) -> list[float]:
        """Debug: extract features without classification."""
        return self._extractor.extract_vector(task)

    @property
    def feature_names(self) -> list[str]:
        """Return feature names for interpretability."""
        return [
            "verifiability",
            "action_safety",
            "feedback_quality",
            "domain_maturity",
            "complexity_score",
            "env_control",
            "governance_history",
            "stakeholder_count",
        ]

    # ── Internal ────────────────────────────────────────────────────────

    def _classify(self, score: float) -> GateDecision:
        if score >= self.THRESHOLD_ALLOW:
            return GateDecision.ALLOW
        if score >= self.THRESHOLD_REJECT:
            return GateDecision.REVIEW
        return GateDecision.REJECT

    @staticmethod
    def _compute_confidence(score: float) -> float:
        """Confidence = distance from nearest threshold boundary."""
        dist_allow = abs(score - ApplicabilityGate.THRESHOLD_ALLOW)
        dist_reject = abs(score - ApplicabilityGate.THRESHOLD_REJECT)
        nearest = min(dist_allow, dist_reject)
        return round(min(1.0, 1.0 - nearest * 3), 4)

    def _generate_reasoning(
        self,
        task: TaskDescriptor,
        features,
        score: float,
        decision: GateDecision,
    ) -> str:
        """Generate human-readable reasoning for the decision."""
        parts = []

        if features.env_control > 0.8:
            parts.append(f"controlled env ({features.env_control:.0%})")
        elif features.env_control < 0.3:
            parts.append(f"uncontrolled env ({features.env_control:.0%})")

        if features.action_safety < 0.3:
            parts.append(f"safety-critical ({features.action_safety:.0%})")

        if features.verifiability < 0.4:
            parts.append(f"low verifiability ({features.verifiability:.0%})")

        if features.governance_history > 0.7:
            parts.append(f"prior governance success ({features.governance_history:.0%})")

        if features.feedback_quality < 0.3:
            parts.append(f"sparse feedback ({features.feedback_quality:.0%})")

        if not parts:
            base = "task characteristics fall within governance suitable range"
            if decision == GateDecision.ALLOW:
                parts.append(f"{base} (score={score:.2f})")
            elif decision == GateDecision.REVIEW:
                parts.append(f"borderline case, recommending review (score={score:.2f})")
            else:
                parts.append(f"below threshold, governance not advised (score={score:.2f})")

        return "; ".join(parts)

    @staticmethod
    def _default_ci_tasks() -> list[TaskDescriptor]:
        """Default tasks for CI validation."""
        return [
            TaskDescriptor(
                task_id="ci_rl_train",
                category="rl_training",
                description="Train DQN agent in BottleSumo simulation with dense reward",
                domain="robotics",
                environment="simulation",
                tags=["bottlesumo", "rl", "verified"],
            ),
            TaskDescriptor(
                task_id="ci_code_gen",
                category="code_generation",
                description="Generate Python utility functions from spec",
                domain="general",
                environment="simulation",
                tags=["codex", "auto"],
            ),
            TaskDescriptor(
                task_id="ci_hardware",
                category="hardware_control",
                description="Control robot arm in real-world factory",
                domain="robotics",
                environment="real_world",
                safety_critical=True,
                tags=["hardware", "danger"],
            ),
        ]
