"""
MetaCognitiveLoop — 元认知闭环
===============================

解决 MES 框架指出的"元认知空洞"问题：当前架构有监控但无调节。
本模块实现完整的 Monitor → Evaluate → Adjust → Verify 元认知闭环，
整合 FixedPointDetector 和 GodelianBoundary 作为子组件。

核心能力:
  1. Monitor: 从 RealityBridge 拉取决策日志和反馈
  2. Evaluate: 识别失败模式，生成 GapReport
  3. StrategyGen: 方案 A (保守/历史经验) + 方案 B (激进/缺口驱动)
  4. Adjust: A/B 方案并行进入 FixedPointDetector SUSPICIOUS 状态
  5. Verify: GodelianBoundary 检测不可自证命题 → EXTERNALIZE
  6. SelfCheck: 10 边界场景 Benchmark 验证

学术来源: Metacognitive Evolutionary System (MES, 2026),
          Adaptive Quine Structures, HyperAgents (Meta, 2026)

集成点:
  - RealityBridge (P1): 数据输入
  - FixedPointDetector (本次 Phase 1): 收敛检测
  - GodelianBoundary (本次 Phase 2): 自指安全
  - ApplicabilityGate (P2): 任务适用性判断
  - SelfCheckBenchmark: 验证基准
"""
import json
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from governance.meta.fixed_point_detector import (
    ConvergenceReport,
    ConvergenceState,
    FixedPointDetector,
)
from governance.meta.godelian_boundary import (
    GodelianBoundary,
    GodelianVerdict,
    Proposition,
    PropositionGenerator,
)


# ── Domain Types ─────────────────────────────────────────────────────────────

class FailurePattern(str, Enum):
    """失败模式分类"""
    REWARD_HACKING = "reward_hacking"         # 奖励投机
    SAFETY_VIOLATION = "safety_violation"     # 安全违规
    DISTRIBUTIONAL_SHIFT = "distributional_shift"  # 分布偏移
    CATASTROPHIC_FORGETTING = "catastrophic_forgetting"  # 灾难遗忘
    MODE_COLLAPSE = "mode_collapse"           # 模式坍塌
    SLOW_CONVERGENCE = "slow_convergence"     # 收敛缓慢
    OSCILLATION = "oscillation"               # 震荡
    OVERFITTING = "overfitting"               # 过拟合
    UNKNOWN = "unknown"                       # 未知


class StrategyType(str, Enum):
    """策略类型"""
    CONSERVATIVE = "conservative"  # 方案 A: 基于历史经验
    BOLD = "bold"                  # 方案 B: 基于缺口的大胆变异


class LoopPhase(str, Enum):
    """元认知循环阶段"""
    MONITOR = "monitor"
    EVALUATE = "evaluate"
    GENERATE = "generate"
    ADJUST = "adjust"
    VERIFY = "verify"


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class DecisionLog:
    """一条决策日志。"""
    id: str
    timestamp: float = field(default_factory=time.time)
    action: str = ""
    observation: dict = field(default_factory=dict)
    reward: float = 0.0
    policy_version: str = ""
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action": self.action,
            "observation": self.observation,
            "reward": self.reward,
            "policy_version": self.policy_version,
            "context": self.context,
        }


@dataclass
class GapReport:
    """缺口分析报告。"""
    pattern: FailurePattern
    severity: float               # 0-1
    evidence: list[DecisionLog]
    description: str
    suggested_fix: str = ""
    frequency: int = 0            # 出现次数
    trend: str = "stable"         # rising, falling, stable

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern.value,
            "severity": self.severity,
            "evidence_count": len(self.evidence),
            "description": self.description,
            "suggested_fix": self.suggested_fix,
            "frequency": self.frequency,
            "trend": self.trend,
        }


@dataclass
class Strategy:
    """一个策略方案。"""
    id: str
    type: StrategyType
    description: str
    actions: list[str]            # 具体动作列表
    expected_impact: dict[str, float]  # 预期对各项指标的影响
    risk_level: float             # 0-1
    source: str                   # 数据源 (lessons_learned / gap_driven / hybrid)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "actions": self.actions,
            "expected_impact": self.expected_impact,
            "risk_level": self.risk_level,
            "source": self.source,
        }


@dataclass
class LoopTrace:
    """一次完整元认知循环的追踪记录。"""
    cycle_id: str
    phase: LoopPhase
    timestamp: float = field(default_factory=time.time)
    decisions_analyzed: int = 0
    gaps_found: list[GapReport] = field(default_factory=list)
    strategies: list[Strategy] = field(default_factory=list)
    selected_strategy: Strategy | None = None
    convergence: ConvergenceReport | None = None
    godelian_check: dict | None = None
    verification_passed: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "cycle_id": self.cycle_id,
            "phase": self.phase.value,
            "timestamp": self.timestamp,
            "decisions_analyzed": self.decisions_analyzed,
            "gaps_found": [g.to_dict() for g in self.gaps_found],
            "strategies": [s.to_dict() for s in self.strategies],
            "verification_passed": self.verification_passed,
            "metadata": self.metadata,
        }
        if self.selected_strategy:
            d["selected_strategy"] = self.selected_strategy.to_dict()
        if self.convergence:
            d["convergence"] = self.convergence.to_dict()
        if self.godelian_check:
            d["godelian_check"] = self.godelian_check
        return d


# ── MetaCognitiveLoop ────────────────────────────────────────────────────────

class MetaCognitiveLoop:
    """元认知闭环引擎。

    整合 Monitor → Evaluate → Generate → Adjust → Verify 全流程。
    内嵌 FixedPointDetector 和 GodelianBoundary 作为安全与收敛守卫。

    使用方式:
        loop = MetaCognitiveLoop()
        loop.feed_decisions(decision_logs)       # 喂入决策日志
        loop.feed_feedback(feedback_samples)      # 喂入反馈
        trace = loop.run_cycle()                  # 执行一个完整循环
        if trace.selected_strategy:
            apply(trace.selected_strategy)         # 应用策略
    """

    def __init__(
        self,
        convergence_epsilon: float = 0.01,
        convergence_patience: int = 3,
        godelian_self_ref_threshold: float = 0.25,
        godelian_undecidable_threshold: float = 0.60,
        decision_buffer_size: int = 1000,
        cycle_history_size: int = 50,
    ):
        # 子模块
        self.fp_detector = FixedPointDetector(
            epsilon=convergence_epsilon,
            patience=convergence_patience,
        )
        self.godelian_boundary = GodelianBoundary(
            self_ref_threshold=godelian_self_ref_threshold,
            undecidable_threshold=godelian_undecidable_threshold,
        )
        self.prop_generator = PropositionGenerator()

        # 缓冲区
        self.decision_buffer: deque[DecisionLog] = deque(
            maxlen=decision_buffer_size
        )
        self.gap_history: list[GapReport] = []
        self.cycle_history: list[LoopTrace] = []

        # 历史经验库（简化版，实际应从 lessons_learned.md 加载）
        self.lessons_learned: list[dict] = []

        # 循环计数
        self._cycle_counter: int = 0
        self._last_score: float = 0.0
        self._converged: bool = False

    # ── Phase 1: Monitor ──────────────────────────────────────────────────

    def feed_decisions(self, decisions: list[DecisionLog]):
        """喂入决策日志（由 RealityBridge 提供）。"""
        self.decision_buffer.extend(decisions)

    def feed_feedback(self, feedback: list[dict]):
        """喂入外部反馈样本。"""
        # 将反馈转化为 lessons
        for fb in feedback:
            if fb.get("severity", 0.0) > 0.5:
                self.lessons_learned.append({
                    "id": f"lesson_{len(self.lessons_learned):04d}",
                    "pattern": fb.get("pattern", "unknown"),
                    "action": fb.get("action", ""),
                    "outcome": fb.get("outcome", ""),
                    "effectiveness": fb.get("effectiveness", 0.0),
                    "timestamp": time.time(),
                })

    def _compute_current_score(self) -> float:
        """计算当前系统评分（简化为近期平均奖励）。"""
        if not self.decision_buffer:
            return 0.0
        recent = list(self.decision_buffer)[-100:]  # 最近 100 条
        rewards = [d.reward for d in recent]
        if not rewards:
            return 0.0
        # 综合: 均值 + 惩罚方差
        mean_r = sum(rewards) / len(rewards)
        var_r = sum((r - mean_r) ** 2 for r in rewards) / len(rewards)
        return max(0.0, mean_r - 0.1 * (var_r ** 0.5))

    # ── Phase 2: Evaluate ─────────────────────────────────────────────────

    def evaluate(self) -> list[GapReport]:
        """分析决策日志，识别失败模式。

        Returns:
            list[GapReport]: 按严重度排序的缺口报告。
        """
        if not self.decision_buffer:
            return []

        recent = list(self.decision_buffer)[-200:]  # 分析最近 200 条
        gaps = []

        # 检测奖励投机: 高奖励 + 短序列 → 可能作弊
        reward_hacking = self._detect_reward_hacking(recent)
        if reward_hacking:
            gaps.append(reward_hacking)

        # 检测震荡: 奖励方差过大
        oscillation = self._detect_oscillation(recent)
        if oscillation:
            gaps.append(oscillation)

        # 检测收敛缓慢: 长时间无明显改善
        slow_convergence = self._detect_slow_convergence(recent)
        if slow_convergence:
            gaps.append(slow_convergence)

        # 检测模式坍塌: 动作空间缩小
        mode_collapse = self._detect_mode_collapse(recent)
        if mode_collapse:
            gaps.append(mode_collapse)

        # 按严重度排序
        gaps.sort(key=lambda g: g.severity, reverse=True)
        self.gap_history.extend(gaps)
        return gaps

    def _detect_reward_hacking(self, decisions: list[DecisionLog]) -> GapReport | None:
        """检测奖励投机: 异常高奖励但行为单调。"""
        if len(decisions) < 20:
            return None
        rewards = [d.reward for d in decisions]
        actions = [d.action for d in decisions]
        mean_r = sum(rewards) / len(rewards)
        action_diversity = len(set(actions[-20:])) / min(20, len(actions))

        # 高奖励 + 低动作多样性 = 可能投机
        if mean_r > 0.8 and action_diversity < 0.3:
            return GapReport(
                pattern=FailurePattern.REWARD_HACKING,
                severity=0.8,
                evidence=decisions[-20:],
                description=f"高奖励({mean_r:.2f})但动作多样性低({action_diversity:.2f})，疑似奖励投机。",
                suggested_fix="检查奖励函数是否有漏洞；增加动作探索噪声。",
                frequency=len(decisions),
                trend="rising" if mean_r > 0.9 else "stable",
            )
        return None

    def _detect_oscillation(self, decisions: list[DecisionLog]) -> GapReport | None:
        """检测奖励震荡。"""
        if len(decisions) < 10:
            return None
        rewards = [d.reward for d in decisions[-50:]]
        mean_r = sum(rewards) / len(rewards)
        # 计算变异系数
        std = (sum((r - mean_r) ** 2 for r in rewards) / len(rewards)) ** 0.5
        cv = std / max(abs(mean_r), 0.001)

        if cv > 1.0:  # 变异系数 > 1.0 说明剧烈震荡
            return GapReport(
                pattern=FailurePattern.OSCILLATION,
                severity=min(1.0, cv / 3.0),
                evidence=decisions[-20:],
                description=f"奖励震荡严重 (CV={cv:.2f})。",
                suggested_fix="减小学习率；增加动量项；检查是否过冲。",
                frequency=len(decisions[-50:]),
                trend="stable",
            )
        return None

    def _detect_slow_convergence(self, decisions: list[DecisionLog]) -> GapReport | None:
        """检测收敛缓慢。"""
        if len(decisions) < 100:
            return None
        # 分前半和后半
        mid = len(decisions) // 2
        first_half = [d.reward for d in decisions[:mid]]
        second_half = [d.reward for d in decisions[mid:]]
        first_mean = sum(first_half) / len(first_half)
        second_mean = sum(second_half) / len(second_half)
        improvement = second_mean - first_mean

        if improvement < 0.01 and first_mean < 0.5:
            return GapReport(
                pattern=FailurePattern.SLOW_CONVERGENCE,
                severity=0.5,
                evidence=decisions[-50:],
                description=f"改进极其缓慢 (Δ={improvement:.4f})。",
                suggested_fix="增大学习率；使用课程学习；预热训练。",
                frequency=len(decisions),
                trend="stable",
            )
        return None

    def _detect_mode_collapse(self, decisions: list[DecisionLog]) -> GapReport | None:
        """检测模式坍塌: 动作几乎不变。"""
        if len(decisions) < 30:
            return None
        actions = [d.action for d in decisions[-30:]]
        unique_actions = set(actions)
        if len(unique_actions) <= 2 and len(decisions) > 50:
            return GapReport(
                pattern=FailurePattern.MODE_COLLAPSE,
                severity=0.7,
                evidence=decisions[-30:],
                description=f"动作空间坍塌: 仅 {len(unique_actions)} 种动作/{len(actions)} 步。",
                suggested_fix="增加熵正则化；重新初始化探索策略。",
                frequency=len(decisions[-30:]),
                trend="rising",
            )
        return None

    # ── Phase 3: Generate Strategies ──────────────────────────────────────

    def generate_strategies(self, gaps: list[GapReport]) -> list[Strategy]:
        """基于缺口生成 A/B 双轨策略。

        - 方案 A (CONSERVATIVE): 从历史经验库中查找类似缺口的成功修复
        - 方案 B (BOLD): 基于当前缺口的大胆变异
        """
        strategies = []

        # 方案 A: 保守（历史经验）
        for gap in gaps:
            plan_a = self._generate_conservative(gap)
            if plan_a:
                strategies.append(plan_a)

        # 方案 B: 激进（缺口驱动变异）
        for gap in gaps[:3]:  # 只对 top-3 缺口生成激进方案
            plan_b = self._generate_bold(gap)
            if plan_b:
                strategies.append(plan_b)

        return strategies

    def _generate_conservative(self, gap: GapReport) -> Strategy | None:
        """方案 A: 基于历史经验的保守策略。"""
        # 在 lessons_learned 中搜索类似模式
        relevant = [
            l for l in self.lessons_learned
            if gap.pattern.value in str(l.get("pattern", ""))
        ]
        if not relevant:
            # 无历史经验，使用默认保守策略
            return Strategy(
                id=f"planA_{gap.pattern.value}_{self._cycle_counter}",
                type=StrategyType.CONSERVATIVE,
                description=f"默认保守: 小幅调整应对 {gap.pattern.value}",
                actions=[f"tune_{gap.pattern.value}_conservative"],
                expected_impact={"stability": 0.1, "improvement": 0.05},
                risk_level=0.2,
                source="default_conservative",
            )

        # 使用最有效的历史经验
        best = max(relevant, key=lambda l: l.get("effectiveness", 0.0))
        return Strategy(
            id=f"planA_{gap.pattern.value}_{self._cycle_counter}",
            type=StrategyType.CONSERVATIVE,
            description=f"经验驱动: {best.get('action', 'unknown')}",
            actions=[best.get("action", "tune_default")],
            expected_impact={
                "stability": 0.3,
                "improvement": best.get("effectiveness", 0.1),
            },
            risk_level=0.15,
            source="lessons_learned",
        )

    def _generate_bold(self, gap: GapReport) -> Strategy | None:
        """方案 B: 基于缺口的激进策略。"""
        bold_actions = {
            FailurePattern.REWARD_HACKING: [
                "add_reward_penalty_term",
                "increase_entropy_regularization",
                "randomize_reward_scale",
            ],
            FailurePattern.OSCILLATION: [
                "halve_learning_rate",
                "add_momentum_0.9",
                "apply_gradient_clipping",
            ],
            FailurePattern.SLOW_CONVERGENCE: [
                "double_learning_rate",
                "enable_curriculum_learning",
                "warmup_training_100_steps",
            ],
            FailurePattern.MODE_COLLAPSE: [
                "reset_exploration_policy",
                "add_entropy_bonus_0.1",
                "multiplicative_action_noise",
            ],
        }
        actions = bold_actions.get(gap.pattern, ["random_perturbation"])
        return Strategy(
            id=f"planB_{gap.pattern.value}_{self._cycle_counter}",
            type=StrategyType.BOLD,
            description=f"大胆变异: {gap.pattern.value} → {actions[0]}",
            actions=actions,
            expected_impact={"exploration": 0.5, "risk": 0.3},
            risk_level=0.6,
            source="gap_driven",
        )

    # ── Phase 4: Adjust (FixedPointDetector Integration) ──────────────────

    def adjust(self, strategies: list[Strategy]) -> Strategy | None:
        """通过 FixedPointDetector 评估策略的收敛性。

        将每个策略送入模拟的扰动测试（简化版: 基于预期影响计算收敛）。
        最终选择通过收敛测试的最佳策略。

        Returns:
            Strategy | None: 被选中的策略，None 表示无合适策略。
        """
        if not strategies:
            return None

        candidates = []
        for strategy in strategies:
            # 模拟扰动测试后的分数
            base_score = self._compute_current_score()
            impact = strategy.expected_impact.get("improvement", 0.0)
            risk_penalty = strategy.risk_level * 0.2
            perturbed_score = max(0.0, base_score + impact - risk_penalty)

            # 通过 FixedPointDetector 检测
            report = self.fp_detector.step(
                score=perturbed_score,
                params=strategy.id,
                metadata={"strategy": strategy.to_dict()},
            )

            if report.state in (ConvergenceState.CONTINUE, ConvergenceState.CONVERGED):
                candidates.append((strategy, report, perturbed_score))

        # 选择分数最高的策略
        if candidates:
            candidates.sort(key=lambda x: x[2], reverse=True)
            best_strategy, best_report, best_score = candidates[0]
            self._last_score = best_score
            return best_strategy

        return None

    # ── Phase 5: Verify (GodelianBoundary Integration) ────────────────────

    def verify(self, strategy: Strategy) -> dict:
        """对策略进行哥德尔自指安全检查。

        Returns:
            dict: {
                "godelian_safe": bool,
                "externalized": list[dict],
                "self_check_passed": bool,
            }
        """
        # 1. 自指安全检查
        prop = Proposition(
            id=f"strategy_{strategy.id}",
            content=f"Strategy {strategy.description} will improve the system",
            category=self._infer_category(strategy),
            source="MetaCognitiveLoop.verify",
        )
        boundary_report = self.godelian_boundary.analyze(prop)

        # 2. 如果是 UNDECIDABLE，标记需要外部验证
        godelian_safe = boundary_report.verdict not in (
            GodelianVerdict.UNDECIDABLE,
        )
        externalized = []
        if boundary_report.verdict == GodelianVerdict.EXTERNALIZE:
            externalized.append(boundary_report.to_dict())

        # 3. SelfCheck: 检查策略是否通过基本安全检查
        self_check_passed = self._self_check(strategy)

        return {
            "godelian_safe": godelian_safe,
            "externalized": externalized,
            "self_check_passed": self_check_passed,
            "boundary_report": boundary_report.to_dict(),
        }

    def _self_check(self, strategy: Strategy) -> bool:
        """基本自检: 策略风险不可过高、动作不可为空。"""
        if strategy.risk_level > 0.9:
            return False
        if not strategy.actions:
            return False
        if len(strategy.description) < 3:
            return False
        return True

    def _infer_category(self, strategy: Strategy) -> str:
        """从策略推断命题分类。"""
        # 直接映射策略源到命题类别
        source_category_map = {
            "lessons_learned": "correctness",  # 经验驱动 → 正确性
            "gap_driven": "performance",       # 缺口驱动 → 性能
            "default": "performance",
            "default_conservative": "safety",  # 默认保守 → 安全
            "test": "performance",
        }
        # 精确匹配
        if strategy.source in source_category_map:
            return source_category_map[strategy.source]
        # 前缀匹配
        for prefix, cat in source_category_map.items():
            if strategy.source.startswith(prefix):
                return cat
        # 检查描述中的关键词
        desc_lower = strategy.description.lower()
        if any(kw in desc_lower for kw in ("safe", "harm", "danger")):
            return "safety"
        if any(kw in desc_lower for kw in ("fair", "bias", "equal")):
            return "fairness"
        if any(kw in desc_lower for kw in ("correct", "error", "bug")):
            return "correctness"
        return "performance"

    # ── Full Cycle ────────────────────────────────────────────────────────

    def run_cycle(self) -> LoopTrace:
        """执行完整的 Monitor → Evaluate → Generate → Adjust → Verify 循环。"""
        self._cycle_counter += 1
        cycle_id = f"cycle_{self._cycle_counter:04d}"

        # Phase 1: Monitor (数据已在 feed_* 中收集)
        # Phase 2: Evaluate
        gaps = self.evaluate()

        # Phase 3: Generate
        strategies = self.generate_strategies(gaps)

        # Phase 4: Adjust
        selected = self.adjust(strategies)

        # Phase 5: Verify
        verification = {}
        if selected:
            verification = self.verify(selected)

        trace = LoopTrace(
            cycle_id=cycle_id,
            phase=LoopPhase.VERIFY,
            decisions_analyzed=len(self.decision_buffer),
            gaps_found=gaps,
            strategies=strategies,
            selected_strategy=selected,
            convergence=self.fp_detector._history[-1] if self.fp_detector._history else None,
            godelian_check=verification,
            verification_passed=verification.get("self_check_passed", False),
            metadata={
                "score": self._last_score,
                "converged": self._converged,
            },
        )

        self.cycle_history.append(trace)
        return trace

    def is_converged(self) -> bool:
        """是否已收敛？"""
        return self._converged

    # ── History & Export ──────────────────────────────────────────────────

    def export_history(self, path: str | Path):
        """导出循环历史到文件。"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [t.to_dict() for t in self.cycle_history],
                f, indent=2, ensure_ascii=False,
            )

    def summary(self) -> dict:
        """获取循环摘要。"""
        if not self.cycle_history:
            return {"cycles": 0}

        gaps_total = sum(len(t.gaps_found) for t in self.cycle_history)
        strategies_total = sum(len(t.strategies) for t in self.cycle_history)
        selected_total = sum(
            1 for t in self.cycle_history if t.selected_strategy is not None
        )
        verified_total = sum(
            1 for t in self.cycle_history if t.verification_passed
        )

        return {
            "cycles": len(self.cycle_history),
            "total_gaps_found": gaps_total,
            "total_strategies_generated": strategies_total,
            "strategies_adopted": selected_total,
            "strategies_verified": verified_total,
            "current_score": self._last_score,
            "converged": self._converged,
            "lessons_count": len(self.lessons_learned),
            "godelian_externalized": len(self.godelian_boundary.history),
        }

    # ── Observability ────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """获取 MCL 运行时可观测状态。"""
        recent_gaps = [
            g.to_dict() for g in self.gap_history[-5:]
        ]
        # A/B strategy ratio
        a_count = sum(
            1 for t in self.cycle_history
            if t.selected_strategy and t.selected_strategy.type == StrategyType.CONSERVATIVE
        )
        b_count = sum(
            1 for t in self.cycle_history
            if t.selected_strategy and t.selected_strategy.type == StrategyType.BOLD
        )

        return {
            "module": "MetaCognitiveLoop",
            "cycle_count": self._cycle_counter,
            "current_score": self._last_score,
            "converged": self._converged,
            "buffer_size": len(self.decision_buffer),
            "lessons_count": len(self.lessons_learned),
            "recent_gaps": recent_gaps,
            "strategy_ratio": {
                "conservative": a_count,
                "bold": b_count,
                "bold_ratio": round(b_count / max(a_count + b_count, 1), 2),
            },
            "last_strategy": (
                self.cycle_history[-1].selected_strategy.to_dict()
                if self.cycle_history and self.cycle_history[-1].selected_strategy
                else None
            ),
        }

    def get_dashboard(self) -> dict:
        """获取聚合仪表盘状态（合并 FPD + GB + MCL 三个模块的可观测数据）。

        这是供外部监控系统（Grafana / RealityBridge）使用的统一入口。
        """
        return {
            "timestamp": time.time(),
            "fpd": self.fp_detector.get_state(),
            "gb": self.godelian_boundary.get_state(),
            "mcl": self.get_state(),
            "summary": self.summary(),
        }

    def reset(self):
        """重置循环状态。"""
        self.fp_detector.reset()
        self.godelian_boundary.reset()
        self.decision_buffer.clear()
        self.gap_history.clear()
        self.cycle_history.clear()
        self.lessons_learned.clear()
        self._cycle_counter = 0
        self._last_score = 0.0
        self._converged = False


# ── Benchmark Integration ────────────────────────────────────────────────────

class SelfCheckBenchmark:
    """SelfCheck 基准测试: 10 个边界场景。

    用于 MetaCognitiveLoop.verify() 阶段验证策略不破坏系统基本属性。
    """

    SCENARIOS = [
        {
            "id": "SC-001",
            "name": "空策略拒绝",
            "check": lambda s: s.actions is not None and len(s.actions) > 0,
            "severity": "critical",
        },
        {
            "id": "SC-002",
            "name": "过高风险拒绝",
            "check": lambda s: s.risk_level < 0.9,
            "severity": "critical",
        },
        {
            "id": "SC-003",
            "name": "动作非空字符串",
            "check": lambda s: all(a and a.strip() for a in s.actions),
            "severity": "high",
        },
        {
            "id": "SC-004",
            "name": "预期影响有界",
            "check": lambda s: all(-1.0 <= v <= 1.0 for v in s.expected_impact.values()),
            "severity": "medium",
        },
        {
            "id": "SC-005",
            "name": "描述非空",
            "check": lambda s: len(s.description) > 5,
            "severity": "low",
        },
        {
            "id": "SC-006",
            "name": "策略类型有效",
            "check": lambda s: s.type in (StrategyType.CONSERVATIVE, StrategyType.BOLD),
            "severity": "critical",
        },
        {
            "id": "SC-007",
            "name": "数据源非空",
            "check": lambda s: s.source and len(s.source) > 0,
            "severity": "low",
        },
        {
            "id": "SC-008",
            "name": "动作数量合理",
            "check": lambda s: 1 <= len(s.actions) <= 10,
            "severity": "medium",
        },
        {
            "id": "SC-009",
            "name": "无重复动作",
            "check": lambda s: len(s.actions) == len(set(s.actions)),
            "severity": "low",
        },
        {
            "id": "SC-010",
            "name": "ID格式有效",
            "check": lambda s: "_" in s.id and len(s.id) > 5,
            "severity": "low",
        },
    ]

    @classmethod
    def run(cls, strategy: Strategy) -> dict:
        """对策略运行全部 10 个 SelfCheck 场景。

        Returns:
            dict: {"passed": int, "failed": int, "total": int, "details": [...]}
        """
        results = []
        for scenario in cls.SCENARIOS:
            try:
                passed = scenario["check"](strategy)
            except Exception as e:
                passed = False
            results.append({
                "id": scenario["id"],
                "name": scenario["name"],
                "severity": scenario["severity"],
                "passed": passed,
            })

        passed = sum(1 for r in results if r["passed"])
        failed = len(results) - passed
        return {
            "passed": passed,
            "failed": failed,
            "total": len(results),
            "details": results,
            "all_critical_passed": all(
                r["passed"] for r in results if r["severity"] == "critical"
            ),
        }
