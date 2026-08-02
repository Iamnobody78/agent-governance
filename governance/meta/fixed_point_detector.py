"""
FixedPointDetector — 递归改进不动点检测器
============================================

解决 HyperAgents 论文指出的"无限回归"问题：通过检测迭代改进是否收敛
(而非无穷堆叠元层级)来终止递归。

核心思想：
  - 每次迭代后记录状态快照 (score, params, structure)
  - 计算连续两轮间的 delta
  - 如果 delta < epsilon 连续 N 轮 → CONVERGED (不动点)
  - 如果 delta 震荡/发散 → OSCILLATING / DIVERGING (需干预)

学术来源: HyperAgents (Meta, 2026), Gödel Agent, Fixed-Point Theory

集成点:
  - self_evolution_closed_loop.py 的 run() 循环
  - MetaCognitiveLoop 的迭代终止条件
"""
import json
import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# ── Convergence State ────────────────────────────────────────────────────────

class ConvergenceState(str, Enum):
    """迭代状态枚举"""
    CONTINUE = "continue"           # 仍在改进，继续迭代
    CONVERGED = "converged"         # 已达不动点，停止
    OSCILLATING = "oscillating"     # 震荡：在两点间来回跳
    DIVERGING = "diverging"         # 发散：越来越差
    PLATEAU = "plateau"             # 高原：改进极其缓慢


# ── State Snapshot ────────────────────────────────────────────────────────────

@dataclass
class StateSnapshot:
    """一次迭代的状态快照"""
    iteration: int
    score: float                    # 主指标 (如 audit_score)
    params_hash: str                # 参数/模型的哈希
    structure_hash: str             # 代码结构的哈希
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "score": self.score,
            "params_hash": self.params_hash,
            "structure_hash": self.structure_hash,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StateSnapshot":
        return cls(**d)


# ── Convergence Report ────────────────────────────────────────────────────────

@dataclass
class ConvergenceReport:
    """收敛检测报告"""
    state: ConvergenceState
    current_iteration: int
    score_delta: float              # 最近两轮的 score 变化
    score_trend: list[float]        # 最近 N 轮的 score 序列
    params_changed: bool            # 参数是否变化
    structure_changed: bool         # 结构是否变化
    oscillations_detected: int      # 检测到的震荡次数
    confidence: float               # 收敛置信度 (0-1)
    recommendation: str             # 建议动作

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "current_iteration": self.current_iteration,
            "score_delta": self.score_delta,
            "score_trend": self.score_trend,
            "params_changed": self.params_changed,
            "structure_changed": self.structure_changed,
            "oscillations_detected": self.oscillations_detected,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
        }


# ── FixedPointDetector ────────────────────────────────────────────────────────

class FixedPointDetector:
    """检测迭代改进是否收敛到不动点。

    解决了"元元层无限递归"问题：当改进 delta < epsilon 时，
    不再堆叠新的元层级，而是终止并报告收敛。

    使用方式:
        detector = FixedPointDetector(epsilon=0.01, patience=3)
        for i in range(max_iters):
            score = run_evolution_cycle()
            state = detector.step(score, params, structure)
            if state == ConvergenceState.CONVERGED:
                break  # 不动点已达，无需再迭代
    """

    def __init__(
        self,
        epsilon: float = 0.01,
        patience: int = 3,
        window_size: int = 5,
        oscillation_threshold: float = 0.001,
        divergence_factor: float = 2.0,
    ):
        """
        Args:
            epsilon: 收敛阈值。score 变化小于此值视为无改进。
            patience: 容忍轮数。连续 patience 轮 delta < epsilon 才判定 CONVERGED。
            window_size: 滑动窗口大小，用于计算趋势。
            oscillation_threshold: 震荡检测阈值。方向反转次数 >= 2 判定震荡。
            divergence_factor: 发散因子。如果 score 比历史上最好还差 factor 倍，判定发散。
        """
        self.epsilon = epsilon
        self.patience = patience
        self.window_size = window_size
        self.oscillation_threshold = oscillation_threshold
        self.divergence_factor = divergence_factor

        self._history: deque[StateSnapshot] = deque(maxlen=window_size)
        self._best_score: float = float("-inf")
        self._best_iteration: int = 0
        self._stagnation_counter: int = 0
        self._direction_history: list[int] = []  # +1(up), -1(down), 0(flat)
        self._current_iteration: int = 0

    # ── Core API ──────────────────────────────────────────────────────────

    def step(
        self,
        score: float,
        params: object | str | None = None,
        structure: object | str | None = None,
        metadata: dict | None = None,
    ) -> ConvergenceReport:
        """执行一次迭代步，返回收敛状态。

        Args:
            score: 当前迭代的主指标分数。
            params: 模型参数（用于计算参数哈希）。可以是字符串、字节或任何对象。
            structure: 代码/架构结构（用于计算结构哈希）。
            metadata: 任意附加元数据。

        Returns:
            ConvergenceReport: 收敛检测报告。
        """
        self._current_iteration += 1

        # 计算哈希
        params_hash = self._hash(params) if params is not None else ""
        structure_hash = self._hash(structure) if structure is not None else ""

        snapshot = StateSnapshot(
            iteration=self._current_iteration,
            score=score,
            params_hash=params_hash,
            structure_hash=structure_hash,
            metadata=metadata or {},
        )

        # 更新历史
        previous = self._history[-1] if self._history else None
        self._history.append(snapshot)

        # 更新最佳
        if score > self._best_score:
            self._best_score = score
            self._best_iteration = self._current_iteration

        # 计算 delta
        score_delta = score - previous.score if previous else 0.0

        # 更新方向历史
        if previous:
            if abs(score_delta) < self.oscillation_threshold:
                self._direction_history.append(0)
            elif score_delta > 0:
                self._direction_history.append(1)
            else:
                self._direction_history.append(-1)
            # 限制方向历史长度
            if len(self._direction_history) > self.window_size * 2:
                self._direction_history = self._direction_history[-self.window_size * 2:]

        # 判定状态
        state = self._determine_state(snapshot, previous, score_delta)

        return ConvergenceReport(
            state=state,
            current_iteration=self._current_iteration,
            score_delta=score_delta,
            score_trend=[s.score for s in self._history],
            params_changed=params_hash != (previous.params_hash if previous else ""),
            structure_changed=structure_hash != (previous.structure_hash if previous else ""),
            oscillations_detected=self._count_oscillations(),
            confidence=self._compute_confidence(state),
            recommendation=self._recommend(state),
        )

    def reset(self):
        """重置检测器状态。"""
        self._history.clear()
        self._best_score = float("-inf")
        self._best_iteration = 0
        self._stagnation_counter = 0
        self._direction_history.clear()
        self._current_iteration = 0

    # ── Observability ────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """获取运行时可观测状态（供 dashboard / 外部查询）。

        Returns:
            dict with: current_iteration, best_score, stagnation_counter,
                       recent_trend, current_convergence, oscillation_count,
                       params_stable, config_summary
        """
        hist = list(self._history)
        recent_trend = [s.score for s in hist[-5:]] if hist else []
        current_state = None
        if len(hist) >= 2:
            delta = abs(hist[-1].score - hist[-2].score)
            if delta < self.epsilon:
                if self._stagnation_counter >= self.patience:
                    current_state = "converged"
                else:
                    current_state = f"suspicious({self._stagnation_counter}/{self.patience})"
            else:
                current_state = "converging"
        elif hist:
            current_state = "initial"

        return {
            "module": "FixedPointDetector",
            "current_iteration": self._current_iteration,
            "best_score": self._best_score,
            "best_iteration": self._best_iteration,
            "stagnation_counter": self._stagnation_counter,
            "recent_trend": recent_trend,
            "current_convergence": current_state,
            "oscillation_count": self._count_oscillations(),
            "params_stable": (
                len(set(s.params_hash for s in hist[-3:])) == 1
                if len(hist) >= 3 else None
            ),
            "config": {
                "epsilon": self.epsilon,
                "patience": self.patience,
                "window_size": self.window_size,
                "divergence_factor": self.divergence_factor,
            },
        }

    # ── State Determination ───────────────────────────────────────────────

    def _determine_state(
        self,
        current: StateSnapshot,
        previous: StateSnapshot | None,
        score_delta: float,
    ) -> ConvergenceState:
        """综合判定当前迭代状态。"""

        # 首次迭代：无法判定
        if previous is None:
            return ConvergenceState.CONTINUE

        # 1. 检查发散
        if self._is_diverging(current):
            return ConvergenceState.DIVERGING

        # 2. 检查震荡
        if self._is_oscillating():
            return ConvergenceState.OSCILLATING

        # 3. 检查高原（改进极慢）
        if self._is_plateau(score_delta):
            return ConvergenceState.PLATEAU

        # 4. 检查收敛
        if abs(score_delta) < self.epsilon:
            self._stagnation_counter += 1
            if self._stagnation_counter >= self.patience:
                return ConvergenceState.CONVERGED
        else:
            self._stagnation_counter = 0

        return ConvergenceState.CONTINUE

    def _is_diverging(self, current: StateSnapshot) -> bool:
        """检测发散：当前 score 远差于历史最佳。"""
        if self._best_score <= 0:
            return False
        # 如果当前分数比最佳下降超过 factor 倍
        return current.score < self._best_score / self.divergence_factor

    def _is_oscillating(self) -> bool:
        """检测震荡：方向频繁反转。"""
        if len(self._direction_history) < 4:
            return False
        # 统计方向反转次数
        reversals = sum(
            1 for i in range(1, len(self._direction_history))
            if self._direction_history[i] != 0
            and self._direction_history[i - 1] != 0
            and self._direction_history[i] != self._direction_history[i - 1]
        )
        return reversals >= 3  # 4步中至少3次反转 = 震荡

    def _is_plateau(self, score_delta: float) -> bool:
        """检测高原：改进存在但极其缓慢。"""
        if self._current_iteration < self.patience + 1:
            return False
        # 连续 patience 轮 delta 都小于 2*epsilon 但大于 epsilon
        if abs(score_delta) < self.epsilon * 2 and abs(score_delta) >= self.epsilon:
            # 检查是否连续
            recent_deltas = []
            for i in range(1, min(len(self._history), self.patience + 1)):
                prev = list(self._history)[-i - 1] if i < len(self._history) else None
                curr = list(self._history)[-i]
                if prev:
                    recent_deltas.append(abs(curr.score - prev.score))
            if len(recent_deltas) >= self.patience:
                return all(
                    self.epsilon <= d < self.epsilon * 2 for d in recent_deltas
                )
        return False

    def _count_oscillations(self) -> int:
        """统计震荡次数。"""
        if len(self._direction_history) < 2:
            return 0
        return sum(
            1 for i in range(1, len(self._direction_history))
            if self._direction_history[i] != 0
            and self._direction_history[i - 1] != 0
            and self._direction_history[i] != self._direction_history[i - 1]
        )

    def _compute_confidence(self, state: ConvergenceState) -> float:
        """计算收敛置信度 (0-1)。"""
        if state == ConvergenceState.CONVERGED:
            # 基于 stagnation 轮数和最近 delta 的大小
            delta_ratio = max(0, 1 - abs(self._last_delta()) / self.epsilon)
            return min(1.0, 0.5 + 0.5 * delta_ratio * (self._stagnation_counter / self.patience))
        elif state == ConvergenceState.OSCILLATING:
            return 0.3 + 0.1 * self._count_oscillations()
        elif state == ConvergenceState.DIVERGING:
            return 0.8  # 高置信度：确实在发散
        elif state == ConvergenceState.PLATEAU:
            return 0.6
        return 0.4  # CONTINUE

    def _last_delta(self) -> float:
        if len(self._history) < 2:
            return float("inf")
        hist = list(self._history)
        return abs(hist[-1].score - hist[-2].score)

    def _recommend(self, state: ConvergenceState) -> str:
        """根据状态生成建议。"""
        recommendations = {
            ConvergenceState.CONVERGED: (
                f"不动点已达 (iteration {self._current_iteration})。"
                f"最佳分数: {self._best_score:.4f} @ iteration {self._best_iteration}。"
                "停止迭代，无需再堆叠元层级。"
            ),
            ConvergenceState.DIVERGING: (
                f"检测到发散 (iteration {self._current_iteration})。"
                f"当前分数 {self._history[-1].score:.4f} vs 最佳 {self._best_score:.4f}。"
                "建议：回滚到 iteration {self._best_iteration}，调整学习率或奖励函数。"
            ),
            ConvergenceState.OSCILLATING: (
                f"检测到震荡 ({self._count_oscillations()} 次反转)。"
                "建议：减小步长、增加阻尼、或使用动量平滑。"
            ),
            ConvergenceState.PLATEAU: (
                f"检测到高原 (iteration {self._current_iteration})。"
                f"改进极缓慢 (delta < {self.epsilon * 2})。"
                "建议：如果已满足需求，可接受为次优解；否则引入探索噪声。"
            ),
            ConvergenceState.CONTINUE: "仍在改进中，继续迭代。",
        }
        return recommendations[state]

    # ── Utilities ─────────────────────────────────────────────────────────

    @staticmethod
    def _hash(obj: object | str) -> str:
        """计算对象的稳定哈希。"""
        if isinstance(obj, str):
            return hashlib.sha256(obj.encode()).hexdigest()[:16]
        try:
            serialized = json.dumps(obj, sort_keys=True, default=str)
            return hashlib.sha256(serialized.encode()).hexdigest()[:16]
        except (TypeError, ValueError):
            return hashlib.sha256(str(obj).encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """序列化检测器状态。"""
        return {
            "epsilon": self.epsilon,
            "patience": self.patience,
            "window_size": self.window_size,
            "history": [s.to_dict() for s in self._history],
            "best_score": self._best_score,
            "best_iteration": self._best_iteration,
            "stagnation_counter": self._stagnation_counter,
            "current_iteration": self._current_iteration,
        }

    def save(self, path: str | Path):
        """持久化到文件。"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str | Path) -> "FixedPointDetector":
        """从文件恢复。"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        detector = cls(
            epsilon=data["epsilon"],
            patience=data["patience"],
            window_size=data["window_size"],
        )
        detector._best_score = data["best_score"]
        detector._best_iteration = data["best_iteration"]
        detector._stagnation_counter = data["stagnation_counter"]
        detector._current_iteration = data["current_iteration"]
        for snap in data["history"]:
            detector._history.append(StateSnapshot.from_dict(snap))
        return detector


# ── Integration Shim ──────────────────────────────────────────────────────────
# 用于与 self_evolution_closed_loop.py 的无缝集成

class EvolutionConvergenceGuard:
    """自演进闭环的收敛守卫。

    在 SelfEvolutionEngine.run() 循环中插入：
        guard = EvolutionConvergenceGuard()
        for i in range(max_cycles):
            cycle = engine.run_full_cycle()
            report = guard.step(cycle)
            if report.should_stop:
                break
    """

    def __init__(self, epsilon: float = 0.03, patience: int = 2):
        self.detector = FixedPointDetector(epsilon=epsilon, patience=patience)
        self.reports: list[ConvergenceReport] = []

    def step(self, cycle) -> ConvergenceReport:
        """处理一个进化周期。"""
        report = self.detector.step(
            score=cycle.audit_score_after,
            params=str(cycle.fixes_deployed),
            structure=str([c.diagnosis.fix_category.value
                           for c in cycle.fixes_generated]),
            metadata={
                "cycle_id": cycle.cycle_id,
                "gaps_found": len(cycle.gaps_found),
                "fixes_deployed": len(cycle.fixes_deployed),
            },
        )
        self.reports.append(report)
        return report

    @property
    def should_stop(self) -> bool:
        """是否应停止迭代？"""
        if not self.reports:
            return False
        last = self.reports[-1]
        return last.state in (ConvergenceState.CONVERGED, ConvergenceState.DIVERGING)

    @property
    def converged(self) -> bool:
        """是否收敛？"""
        if not self.reports:
            return False
        return self.reports[-1].state == ConvergenceState.CONVERGED
