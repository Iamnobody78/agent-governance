"""ApplicabilityGate classifier — lightweight 4-layer MLP.

Architecture: 8 → 16 → 8 → 4 → 1
  - Layer 1: 8→16 (ReLU)
  - Layer 2: 16→8 (ReLU)
  - Layer 3: 8→4 (ReLU)
  - Layer 4: 4→1 (Sigmoid)

Total params: (8*16+16) + (16*8+8) + (8*4+4) + (4*1+1) = 144 + 136 + 36 + 5 = 321 weights

Design: intentionally small to avoid overfitting on limited governance data.
Uses numpy-only implementation to avoid pytorch dependency in CI.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class ApplicabilityClassifier:
    """4-layer MLP for governance applicability scoring."""

    def __init__(self):
        self._rng = np.random.RandomState(42)
        # Layer weights: [W, b] pairs
        self.W1 = self._rng.randn(8, 16) * np.sqrt(2.0 / 8)
        self.b1 = np.zeros(16)
        self.W2 = self._rng.randn(16, 8) * np.sqrt(2.0 / 16)
        self.b2 = np.zeros(8)
        self.W3 = self._rng.randn(8, 4) * np.sqrt(2.0 / 8)
        self.b3 = np.zeros(4)
        self.W4 = self._rng.randn(4, 1) * np.sqrt(2.0 / 4)
        self.b4 = np.zeros(1)

        self._trained = False
        self._training_samples = 0

    # ── Public API ──────────────────────────────────────────────────────

    def predict(self, features: list[float]) -> float:
        """Forward pass — return applicability score [0, 1]."""
        x = np.array(features, dtype=np.float32).reshape(1, -1)

        # Layer 1: 8 → 16 (ReLU)
        x = np.maximum(0, x @ self.W1 + self.b1)
        # Layer 2: 16 → 8 (ReLU)
        x = np.maximum(0, x @ self.W2 + self.b2)
        # Layer 3: 8 → 4 (ReLU)
        x = np.maximum(0, x @ self.W3 + self.b3)
        # Layer 4: 4 → 1 (Sigmoid)
        x = 1.0 / (1.0 + np.exp(-(x @ self.W4 + self.b4)))

        return float(np.clip(x[0, 0], 0.0, 1.0))

    def predict_batch(self, feature_matrix: np.ndarray) -> np.ndarray:
        """Batch prediction — N × 8 → N × 1."""
        x = feature_matrix.astype(np.float32)

        x = np.maximum(0, x @ self.W1 + self.b1)
        x = np.maximum(0, x @ self.W2 + self.b2)
        x = np.maximum(0, x @ self.W3 + self.b3)
        x = 1.0 / (1.0 + np.exp(-(x @ self.W4 + self.b4)))

        return np.clip(x, 0.0, 1.0)

    def train(
        self,
        X: np.ndarray,       # N × 8 feature matrix
        y: np.ndarray,       # N × 1 labels (0 or 1)
        epochs: int = 200,
        lr: float = 0.01,
    ) -> list[float]:
        """Train the classifier using binary cross-entropy + SGD.

        Returns: loss history per epoch.
        """
        X = X.astype(np.float32)
        y = y.reshape(-1, 1).astype(np.float32)
        losses = []

        for _ in range(epochs):
            # ── Forward pass ──
            z1 = X @ self.W1 + self.b1
            a1 = np.maximum(0, z1)

            z2 = a1 @ self.W2 + self.b2
            a2 = np.maximum(0, z2)

            z3 = a2 @ self.W3 + self.b3
            a3 = np.maximum(0, z3)

            z4 = a3 @ self.W4 + self.b4
            y_pred = 1.0 / (1.0 + np.exp(-z4))
            y_pred = np.clip(y_pred, 1e-15, 1 - 1e-15)  # avoid log(0)

            # ── Binary cross-entropy loss ──
            loss = -np.mean(y * np.log(y_pred) + (1 - y) * np.log(1 - y_pred))
            losses.append(float(loss))

            # ── Backward pass ──
            dL = y_pred - y  # dL/dz4 (chain rule shortcut for BCE+sigmoid)
            N = X.shape[0]

            dW4 = a3.T @ dL / N
            db4 = np.mean(dL, axis=0)
            dA3 = dL @ self.W4.T
            dZ3 = dA3 * (z3 > 0)

            dW3 = a2.T @ dZ3 / N
            db3 = np.mean(dZ3, axis=0)
            dA2 = dZ3 @ self.W3.T
            dZ2 = dA2 * (z2 > 0)

            dW2 = a1.T @ dZ2 / N
            db2 = np.mean(dZ2, axis=0)
            dA1 = dZ2 @ self.W2.T
            dZ1 = dA1 * (z1 > 0)

            dW1 = X.T @ dZ1 / N
            db1 = np.mean(dZ1, axis=0)

            # ── Gradient descent ──
            for W, dW in [
                (self.W1, dW1), (self.W2, dW2),
                (self.W3, dW3), (self.W4, dW4),
            ]:
                W -= lr * dW
            for b, db_ in [
                (self.b1, db1), (self.b2, db2),
                (self.b3, db3), (self.b4, db4),
            ]:
                b -= lr * db_

        self._trained = True
        self._training_samples += X.shape[0]
        return losses

    def train_single(
        self,
        features: list[float],
        label: float,
        lr: float = 0.005,
    ) -> float:
        """Online training — update weights on a single sample.

        Returns: loss for this sample.
        """
        X = np.array([features], dtype=np.float32)
        y = np.array([[label]], dtype=np.float32)
        losses = self.train(X, y, epochs=1, lr=lr)
        return losses[0]

    def accuracy(self, X: np.ndarray, y: np.ndarray, threshold: float = 0.5) -> float:
        """Compute classification accuracy."""
        y_true = y.reshape(-1).astype(np.float32)
        y_pred = self.predict_batch(X).reshape(-1)
        correct = np.sum((y_pred >= threshold) == (y_true >= 0.5))
        return float(correct) / len(y_true)

    # ── Persistence ─────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        """Save weights to a JSON file."""
        data = {
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2.tolist(),
            "W3": self.W3.tolist(),
            "b3": self.b3.tolist(),
            "W4": self.W4.tolist(),
            "b4": self.b4.tolist(),
            "trained": self._trained,
            "training_samples": self._training_samples,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> ApplicabilityClassifier:
        """Load weights from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        clf = cls()
        clf.W1 = np.array(data["W1"])
        clf.b1 = np.array(data["b1"])
        clf.W2 = np.array(data["W2"])
        clf.b2 = np.array(data["b2"])
        clf.W3 = np.array(data["W3"])
        clf.b3 = np.array(data["b3"])
        clf.W4 = np.array(data["W4"])
        clf.b4 = np.array(data["b4"])
        clf._trained = data.get("trained", False)
        clf._training_samples = data.get("training_samples", 0)
        return clf

    @property
    def is_trained(self) -> bool:
        return self._trained

    @property
    def param_count(self) -> int:
        """Total learnable parameters."""
        return sum(
            w.size + b.size
            for w, b in [
                (self.W1, self.b1), (self.W2, self.b2),
                (self.W3, self.b3), (self.W4, self.b4),
            ]
        )
