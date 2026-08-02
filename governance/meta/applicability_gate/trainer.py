"""Feedback trainer for ApplicabilityGate.

Continuously improves the classifier using post-hoc governance outcomes:
  - Successful governance → positive label (1.0)
  - Failed governance → negative label (0.0)
  - Human correction → adjusted label
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from governance.meta.applicability_gate.classifier import ApplicabilityClassifier
from governance.meta.applicability_gate.extractor import FeatureExtractor
from governance.meta.applicability_gate.models import (
    FeedbackSample,
    TaskDescriptor,
)


class FeedbackTrainer:
    """Online feedback training loop for the applicability classifier."""

    def __init__(
        self,
        classifier: ApplicabilityClassifier | None = None,
        extractor: FeatureExtractor | None = None,
    ):
        self._classifier = classifier or ApplicabilityClassifier()
        self._extractor = extractor or FeatureExtractor()
        self._feedback_buffer: list[FeedbackSample] = []
        self._total_feedback = 0
        self._positive_feedback = 0

    # ── Public API ──────────────────────────────────────────────────────

    def record_outcome(
        self,
        task: TaskDescriptor,
        predicted_score: float,
        actual_success: bool,
        notes: str = "",
    ) -> FeedbackSample:
        """Record a governance outcome for training."""
        sample = FeedbackSample(
            task=task,
            predicted_score=predicted_score,
            actual_outcome=1.0 if actual_success else 0.0,
            timestamp=time.time(),
            notes=notes,
        )
        self._feedback_buffer.append(sample)
        self._total_feedback += 1
        if actual_success:
            self._positive_feedback += 1

        # Auto-train every 5 feedback samples
        if len(self._feedback_buffer) >= 5:
            self._train_from_buffer()

        # Update domain history
        self._extractor.register_history(
            task.domain, 1.0 if actual_success else 0.0,
        )

        return sample

    def train_single(self, task: TaskDescriptor, label: float) -> float:
        """Train on a single labeled example. Returns loss."""
        features = self._extractor.extract_vector(task)
        return self._classifier.train_single(features, label)

    def evaluate_accuracy(self, samples: list[FeedbackSample]) -> float:
        """Evaluate accuracy on feedback samples."""
        if not samples:
            return 1.0

        X = np.array([
            self._extractor.extract_vector(s.task) for s in samples
        ])
        y = np.array([s.actual_outcome for s in samples])
        return self._classifier.accuracy(X, y)

    def train_from_samples(
        self,
        samples: list[FeedbackSample],
        epochs: int = 100,
        lr: float = 0.01,
    ) -> list[float]:
        """Batch train from feedback samples."""
        if not samples:
            return []

        X = np.array([
            self._extractor.extract_vector(s.task) for s in samples
        ])
        y = np.array([s.actual_outcome for s in samples])
        return self._classifier.train(X, y, epochs=epochs, lr=lr)

    # ── Metrics ─────────────────────────────────────────────────────────

    def feedback_stats(self) -> dict:
        """Return feedback statistics."""
        return {
            "total_feedback": self._total_feedback,
            "positive_feedback": self._positive_feedback,
            "positive_rate": (
                self._positive_feedback / max(self._total_feedback, 1)
            ),
            "buffer_size": len(self._feedback_buffer),
            "classifier_trained": self._classifier.is_trained,
            "classifier_samples": self._classifier._training_samples,
        }

    # ── Persistence ─────────────────────────────────────────────────────

    def save_feedback(self, path: Path) -> None:
        """Save feedback buffer to JSON file."""
        data = [
            {
                "task_id": s.task.task_id,
                "predicted": s.predicted_score,
                "actual": s.actual_outcome,
                "timestamp": s.timestamp,
                "notes": s.notes,
            }
            for s in self._feedback_buffer
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_feedback(self, path: Path) -> None:
        """Load feedback buffer from JSON file."""
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._feedback_buffer = []
        for entry in data:
            self._feedback_buffer.append(FeedbackSample(
                task=TaskDescriptor(
                    task_id=entry["task_id"],
                    category="unknown",
                    description="",
                ),
                predicted_score=entry["predicted"],
                actual_outcome=entry["actual"],
                timestamp=entry.get("timestamp", 0.0),
                notes=entry.get("notes", ""),
            ))
        self._total_feedback = len(self._feedback_buffer)
        self._positive_feedback = sum(
            1 for s in self._feedback_buffer if s.actual_outcome >= 0.5
        )

    # ── Internal ────────────────────────────────────────────────────────

    def _train_from_buffer(self) -> None:
        """Train classifier on the feedback buffer and clear it."""
        self.train_from_samples(self._feedback_buffer, epochs=50, lr=0.005)
        # Keep last 10 for history, clear rest
        self._feedback_buffer = self._feedback_buffer[-10:]
