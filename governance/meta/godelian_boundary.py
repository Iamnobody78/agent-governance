"""
GodelianBoundary — 哥德尔自指边界检测器
========================================

解决 Gödel Agent 论文指出的"自指悖论"问题：任何足够强大的自指系统
都包含无法自证的命题。本模块识别这些命题并路由到外部验证。

核心思想：
  - 分析命题的自指度 (self-referential index)
  - 识别循环依赖链 (self → meta → meta-meta → self)
  - 检测不可自证命题 → 标记 EXTERNALIZE
  - 委托 RealityBridge (P1) 进行外部验证

学术来源: Gödel Agent, Gödel's Incompleteness Theorems, Tarski's Undefinability

集成点:
  - MetaCognitiveLoop: 验证阶段遇到不可自证命题 → EXTERNALIZE
  - RealityBridge: 接收 EXTERNALIZE 标记的命题 → 4通道外部反馈
"""
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from .adp_taxonomy import (
    ADPClassification,
    map_to_adp,
)


# ── Verdict ──────────────────────────────────────────────────────────────────

class GodelianVerdict(str, Enum):
    """哥德尔裁决"""
    INTERNAL = "internal"           # 系统内部可验证
    EXTERNALIZE = "externalize"     # 必须委托外部验证
    UNDECIDABLE = "undecidable"     # 在系统内不可判定（真正的哥德尔命题）
    SAFE = "safe"                   # 非自指，安全


@dataclass
class Proposition:
    """一个待验证的命题。"""
    id: str
    content: str                    # 命题内容
    category: str = ""              # 分类（如 "safety", "fairness", "correctness"）
    assertions: list[str] = field(default_factory=list)   # 子断言
    context: dict = field(default_factory=dict)           # 上下文
    source: str = ""                # 来源模块

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "assertions": self.assertions,
            "context": self.context,
            "source": self.source,
        }


@dataclass
class BoundaryReport:
    """边界检测报告。"""
    proposition_id: str
    verdict: GodelianVerdict
    self_reference_score: float     # 0-1, 自指度
    circular_dependencies: list[str]  # 检测到的循环依赖
    reasoning: str                  # 推理过程
    recommended_channel: str        # 推荐的外部验证通道
    confidence: float               # 0-1
    adp_classification: dict | None = None  # ADP-compliant decision classification

    def to_dict(self) -> dict:
        result = {
            "proposition_id": self.proposition_id,
            "verdict": self.verdict.value,
            "self_reference_score": self.self_reference_score,
            "circular_dependencies": self.circular_dependencies,
            "reasoning": self.reasoning,
            "recommended_channel": self.recommended_channel,
            "confidence": self.confidence,
        }
        if self.adp_classification is not None:
            result["adp_classification"] = self.adp_classification
        return result


# ── GodelianBoundary ─────────────────────────────────────────────────────────

class GodelianBoundary:
    """检测命题是否触及哥德尔边界（不可自证）。

    核心算法:
      1. 计算自指度 (self-reference score)
      2. 检测循环依赖链
      3. 根据阈值判定 INTERNAL / EXTERNALIZE / UNDECIDABLE

    使用方式:
        boundary = GodelianBoundary()
        prop = Proposition("p1", "This system is always safe")
        report = boundary.analyze(prop)
        if report.verdict == GodelianVerdict.EXTERNALIZE:
            reality_bridge.externalize(report)  # 委托 P1
    """

    # 自指关键词模式 + 权重映射（权重越高的模式越指示自指）
    SELF_REFERENTIAL_PATTERNS: list[tuple[re.Pattern, float]] = [
        (re.compile(r"\bthis (system|agent|model|framework|architecture)\b", re.I), 0.8),
        (re.compile(r"\bself[-\s]?(referenc|modif|improv|evolv|verif|validat|check|audit|correct|repair|heal|assess|diagnos|govern|regulat)\w*\b", re.I), 1.0),
        (re.compile(r"\b(its own|itself|own)\b", re.I), 0.6),
        (re.compile(r"\b(meta[-\s]?(agent|model|system|level|layer|cognit|theory|govern|program|learn))\w*\b", re.I), 0.9),
        (re.compile(r"\b(recursive|recursion|self[-\s]?reflect|circular|feedback loop)\b", re.I), 0.7),
        (re.compile(r"\b(always|never|guarantee\w*|certain\w*|provable|complete|infallible|foolproof|all)\b", re.I), 1.2),
    ]

    # 已知的循环依赖模式
    CIRCULAR_PATTERNS: list[tuple[str, str]] = [
        ("self_evolution", "meta_governance"),
        ("meta_governance", "self_evolution"),
        ("audit", "self_check"),
        ("self_check", "audit"),
        ("validator", "validated_by"),
        ("optimizer", "optimized_by"),
        ("governance", "governed_by"),
    ]

    def __init__(
        self,
        self_ref_threshold: float = 0.25,
        undecidable_threshold: float = 0.60,
    ):
        """
        Args:
            self_ref_threshold: 自指度 > 此值 → EXTERNALIZE
            undecidable_threshold: 自指度 > 此值 → UNDECIDABLE (真正的哥德尔命题)
        """
        self.self_ref_threshold = self_ref_threshold
        self.undecidable_threshold = undecidable_threshold
        self._reports: list[BoundaryReport] = []

    # ── Core API ──────────────────────────────────────────────────────────

    def analyze(self, proposition: Proposition) -> BoundaryReport:
        """分析命题，返回边界报告。

        Args:
            proposition: 待分析的命题。

        Returns:
            BoundaryReport: 边界检测结果。
        """
        self_ref_score = self._compute_self_reference(proposition)
        circular_deps = self._detect_circular_dependencies(proposition)

        # 判定
        verdict, reasoning = self._classify(
            proposition, self_ref_score, circular_deps
        )

        confidence = self._compute_confidence(self_ref_score, circular_deps)

        # ADP classification: map Godelian verdict to enterprise-compliant taxonomy
        adp = self._adp_classify(verdict, proposition, self_ref_score, confidence)

        report = BoundaryReport(
            proposition_id=proposition.id,
            verdict=verdict,
            self_reference_score=self_ref_score,
            circular_dependencies=circular_deps,
            reasoning=reasoning,
            recommended_channel=self._recommend_channel(verdict, proposition),
            confidence=confidence,
            adp_classification=adp.to_dict() if adp else None,
        )

        self._reports.append(report)
        return report

    def analyze_batch(
        self, propositions: list[Proposition]
    ) -> list[BoundaryReport]:
        """批量分析命题。"""
        return [self.analyze(p) for p in propositions]

    def filter_externalizable(
        self, propositions: list[Proposition]
    ) -> list[tuple[Proposition, BoundaryReport]]:
        """过滤出需要外部验证的命题。"""
        results = []
        for p in propositions:
            report = self.analyze(p)
            if report.verdict in (GodelianVerdict.EXTERNALIZE,
                                  GodelianVerdict.UNDECIDABLE):
                results.append((p, report))
        return results

    # ── Self-Reference Computation ────────────────────────────────────────

    def _compute_self_reference(self, proposition: Proposition) -> float:
        """计算命题的自指度 (0-1)。

        使用分层权重: 不同模式有不同的自指指示强度。
        - "self-X" 模式权重最高 (1.0): 直接自指
        - "always/never" 次之 (1.2): 哥德尔特征
        - "this system/agent" (0.8): 系统自指
        - 归一化: sigmoid-like, 2+ 强匹配即触发高自指度
        """
        text = proposition.content.lower()
        for assertion in proposition.assertions:
            text += " " + assertion.lower()

        total_weight = 0.0
        active_patterns = 0

        for pattern, pattern_weight in self.SELF_REFERENTIAL_PATTERNS:
            matches = pattern.findall(text)
            if not matches:
                continue
            active_patterns += 1
            # 多次匹配增加但上限
            multiplier = min(1.5, 1.0 + (len(matches) - 1) * 0.25)
            total_weight += pattern_weight * multiplier

        # Sigmoid-like 归一化: 2个强匹配 (~2.0 total) → ~0.5, 3个(~3.0) → ~0.7
        # total_weight 的理论最大值约 5.2 (所有6个模式各匹配1次, 按各自权重)
        if total_weight <= 0:
            return 0.0
        score = 1.0 / (1.0 + 2.0 / max(total_weight, 0.01))
        return round(score, 4)

    def _detect_circular_dependencies(self, proposition: Proposition) -> list[str]:
        """检测循环依赖链。

        检查已知的循环模式是否出现在命题中。
        """
        circular = []
        text = proposition.content.lower()
        for a, b in self.CIRCULAR_PATTERNS:
            if a.lower() in text and b.lower() in text:
                circular.append(f"{a} ↔ {b}")

        # 检测嵌套元层级循环
        meta_levels = re.findall(r"meta[-]?(meta)+", text)
        if len(meta_levels) > 0:
            circular.append(f"meta recursion depth={max(len(m) for m in meta_levels)//4}")

        # 检测自演进+自验证闭环
        has_evolution = any(kw in text for kw in ["self-evolv", "self_evolv", "self improv"])
        has_verification = any(kw in text for kw in ["self-verif", "self_verif", "self-check", "self audit"])
        if has_evolution and has_verification:
            circular.append("self_evolution ↔ self_verification")

        return circular

    # ── Classification ────────────────────────────────────────────────────

    def _classify(
        self,
        proposition: Proposition,
        self_ref_score: float,
        circular_deps: list[str],
    ) -> tuple[GodelianVerdict, str]:
        """分类命题的哥德尔状态。"""

        # 非自指命题：安全
        if self_ref_score < 0.1 and not circular_deps:
            return GodelianVerdict.SAFE, (
                "命题无自指特征，可在系统内部安全验证。"
            )

        # 极强自指+循环依赖：不可判定（真正的哥德尔命题）
        if self_ref_score >= self.undecidable_threshold and circular_deps:
            return GodelianVerdict.UNDECIDABLE, (
                f"自指度 {self_ref_score:.3f} >= {self.undecidable_threshold} "
                f"且存在 {len(circular_deps)} 个循环依赖。"
                "该命题在系统内不可判定（哥德尔命题）。"
                "必须委托外部验证并接受其不可完备性。"
            )

        # 自指度超过阈值：需要外部化
        if self_ref_score >= self.self_ref_threshold:
            reason_parts = [f"自指度 {self_ref_score:.3f} >= {self.self_ref_threshold}"]
            if circular_deps:
                reason_parts.append(
                    f"存在 {len(circular_deps)} 个循环依赖: {', '.join(circular_deps[:3])}"
                )
            return GodelianVerdict.EXTERNALIZE, (
                f"{'; '.join(reason_parts)}。"
                "系统无法自证此命题，委托 RealityBridge 进行外部验证。"
            )

        # 中等自指度但有循环依赖
        if circular_deps:
            return GodelianVerdict.EXTERNALIZE, (
                f"自指度 {self_ref_score:.3f} 未超过阈值，"
                f"但存在 {len(circular_deps)} 个循环依赖: {', '.join(circular_deps[:3])}。"
                "建议外部验证以打破循环。"
            )

        # 低自指度，可内部处理
        return GodelianVerdict.INTERNAL, (
            f"自指度 {self_ref_score:.3f} 在可接受范围内，"
            "系统内部可验证。"
        )

    def _recommend_channel(
        self, verdict: GodelianVerdict, proposition: Proposition
    ) -> str:
        """推荐外部验证通道。"""
        if verdict in (GodelianVerdict.INTERNAL, GodelianVerdict.SAFE):
            return "internal"

        # 根据命题类型推荐通道
        category_map = {
            "safety": "simulation_channel",      # P1: sim验证安全命题
            "performance": "training_log_channel", # P1: 训练日志
            "fairness": "user_feedback_channel",   # P1: 用户反馈
            "correctness": "shadow_loop_channel",   # P1: Shadow Loop
        }
        if proposition.category in category_map:
            return category_map[proposition.category]

        # 不可判定命题需要所有通道 + 人工
        if verdict == GodelianVerdict.UNDECIDABLE:
            return "all_channels + human_review"

        return "simulation_channel"  # 默认

    def _compute_confidence(
        self, self_ref_score: float, circular_deps: list[str]
    ) -> float:
        """计算判定置信度。"""
        base = 0.5 + self_ref_score * 0.4  # 自指度越高，置信度越高
        if circular_deps:
            base = max(base, 0.8)  # 有循环依赖 → 高置信度需要外部化
        return round(min(1.0, base), 4)

    # ── History ───────────────────────────────────────────────────────────

    @property
    def history(self) -> list[BoundaryReport]:
        return self._reports

    def get_stats(self) -> dict:
        """获取统计信息。"""
        counts = {v.value: 0 for v in GodelianVerdict}
        for r in self._reports:
            counts[r.verdict.value] += 1
        return {
            "total_analyzed": len(self._reports),
            **counts,
            "avg_self_ref_score": (
                sum(r.self_reference_score for r in self._reports) / len(self._reports)
                if self._reports else 0.0
            ),
        }

    def reset(self):
        self._reports.clear()

    # ── ADP Classification ─────────────────────────────────────────────────

    def _adp_classify(
        self,
        verdict: GodelianVerdict,
        proposition: Proposition,
        self_ref_score: float,
        confidence: float,
    ) -> ADPClassification | None:
        """Map a Godelian verdict to ADP (Agent Decision Protocol) taxonomy.

        This produces enterprise-compliant decision classifications for audit trails,
        following the ADP open standard.

        Args:
            verdict: The Godelian verdict (SAFE/INTERNAL/EXTERNALIZE/UNDECIDABLE)
            proposition: The original proposition being analyzed
            self_ref_score: 0-1 self-reference score
            confidence: 0-1 confidence in the verdict

        Returns:
            ADPClassification with autonomy level, decision type, risk, reversibility
        """
        return map_to_adp(
            godelian_verdict=verdict.value,
            proposition_category=proposition.category,
            self_ref_score=self_ref_score,
            confidence=confidence,
        )

    # ── Observability ────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """获取运行时可观测状态。

        Returns:
            dict with: total_analyzed, verdict_distribution, avg_self_ref,
                       recent_externalizations, top_circular_patterns, config
        """
        stats = self.get_stats()
        # Recent externalizations
        recent = [
            r.to_dict() for r in self._reports[-5:]
            if r.verdict in (GodelianVerdict.EXTERNALIZE, GodelianVerdict.UNDECIDABLE)
        ]
        # Top circular dependency patterns
        circular_counts: dict[str, int] = {}
        for r in self._reports:
            for dep in r.circular_dependencies:
                circular_counts[dep] = circular_counts.get(dep, 0) + 1
        top_circular = sorted(
            circular_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "module": "GodelianBoundary",
            "total_analyzed": stats["total_analyzed"],
            "verdict_distribution": {
                k: v for k, v in stats.items()
                if k in ("safe", "internal", "externalize", "undecidable")
            },
            "avg_self_ref_score": round(stats["avg_self_ref_score"], 4),
            "recent_externalizations": recent,
            "top_circular_patterns": [
                {"pattern": p, "count": c} for p, c in top_circular
            ],
            "adp_risk_distribution": self._adp_risk_counts(),
            "adp_autonomy_distribution": self._adp_autonomy_counts(),
            "config": {
                "self_ref_threshold": self.self_ref_threshold,
                "undecidable_threshold": self.undecidable_threshold,
            },
        }

    def _adp_risk_counts(self) -> dict:
        """Count ADP risk levels across all reports."""
        from .adp_taxonomy import RiskLevel
        counts: dict[str, int] = {}
        for r in self._reports:
            if r.adp_classification:
                rl = r.adp_classification.get("risk_level", "unknown")
                counts[rl] = counts.get(rl, 0) + 1
        return counts

    def _adp_autonomy_counts(self) -> dict:
        """Count ADP autonomy levels across all reports."""
        counts: dict[str, int] = {}
        for r in self._reports:
            if r.adp_classification:
                al = r.adp_classification.get("autonomy_level", "unknown")
                counts[al] = counts.get(al, 0) + 1
        return counts


# ── RealityBridge Integration ───────────────────────────────────────────────

class RealityBridgeRouter:
    """将 GodelianBoundary 的 EXTERNALIZE 判决路由到 RealityBridge。

    与 bottlesumo_pi/core/reality_bridge/ 集成。
    """

    def __init__(self, boundary: GodelianBoundary | None = None):
        self.boundary = boundary or GodelianBoundary()

    def route(self, proposition: Proposition, bridge) -> dict:
        """
        分析命题，如果 EXTERNALIZE，路由到 RealityBridge。

        Args:
            proposition: 待分析的命题。
            bridge: RealityBridge 实例。

        Returns:
            dict: 路由结果。
        """
        report = self.boundary.analyze(proposition)

        if report.verdict in (GodelianVerdict.INTERNAL, GodelianVerdict.SAFE):
            return {"routed": False, "report": report.to_dict()}

        # 需要外部验证
        channel = getattr(bridge, report.recommended_channel, None)
        if channel:
            result = channel(proposition)
            return {
                "routed": True,
                "report": report.to_dict(),
                "bridge_result": str(result),
            }

        return {
            "routed": True,
            "report": report.to_dict(),
            "bridge_result": f"Channel '{report.recommended_channel}' not available",
        }


# ── Self-Referential Proposition Generator ──────────────────────────────────

class PropositionGenerator:
    """从系统状态自动生成自指命题，供 GodelianBoundary 分析。

    用于 MetaCognitiveLoop 的"系统在说什么关于自己的话"检测。
    """

    def __init__(self):
        self._templates = [
            # 安全性命题
            ("safety", "This system is always safe for users"),
            ("safety", "The agent never makes harmful decisions"),
            ("safety", "All safety constraints are provably enforced"),

            # 性能命题
            ("performance", "The self-evolution loop always improves performance"),
            ("performance", "Meta-learning converges to a global optimum"),
            ("performance", "The model's decisions are optimal for all inputs"),

            # 正确性命题
            ("correctness", "The self-audit mechanism catches all errors"),
            ("correctness", "The self-verification loop is complete and sound"),
            ("correctness", "ABDL rules are always correctly compiled to C code"),

            # 公平性命题
            ("fairness", "The governance system is fair to all stakeholders"),
            ("fairness", "Agent arbitration is unbiased by design"),
            ("fairness", "The reward function captures all human values"),

            # 哥德尔命题（故意构造的不可判定命题）
            ("meta", "This system can prove its own consistency"),
            ("meta", "The self-modification mechanism is always correct"),
            ("meta", "This statement cannot be verified by this system"),
        ]

    def generate(self, count: int | None = None) -> list[Proposition]:
        """生成自指命题。"""
        import random
        templates = self._templates.copy()
        random.shuffle(templates)
        if count:
            templates = templates[:count]

        propositions = []
        for i, (cat, content) in enumerate(templates):
            prop = Proposition(
                id=f"auto_gen_{i:03d}",
                content=content,
                category=cat,
                source="PropositionGenerator",
            )
            propositions.append(prop)
        return propositions

    def generate_undecidable(self) -> list[Proposition]:
        """只生成哥德尔不可判定命题。"""
        return [Proposition(
            id=f"godel_{i:03d}",
            content=content,
            category="meta",
            source="PropositionGenerator",
        ) for i, (_, content) in enumerate(self._templates) if "prove its own" in content
           or "always correct" in content
           or "cannot be verified" in content]
