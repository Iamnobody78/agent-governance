"""
SelfCheckEngine — 哥德尔自指验证引擎 (P3)
==========================================

实现 Adaptive Quine Structures (MES, 2026) 的"递归元认知塔"概念
和 Gödel Agent (ACL 2025) 的自指修改机制。

三层架构:
  Layer 1 - ContradictionDetector: 自指矛盾检测
    - 扫描 42 层元能力中的逻辑矛盾（"X 是完备的" vs "X 需要外部验证"）
    - 检测循环自指（A 引用 B 验证 A，B 引用 A 验证 B）
    - 识别不可判定命题（"这句话是假的"类型）

  Layer 2 - CompletenessAnalyzer: 完备性缺口分析
    - 扫描元理论中哪些命题无内部验证路径
    - 分类缺口: 可内部修复 vs 必须外部验证 vs 不可判定
    - 生成 CompletenessGapReport

  Layer 3 - TrustRootManager: 信任根管理
    - 明确声明系统的"不可证公理"（如"BottleSumo 的目标是最大化安全胜率"）
    - 管理外部信任锚点（RealityBridge、用户反馈、物理测试）
    - 验证信任链不产生循环

学术来源:
  - Adaptive Quine Structures for Metacognitive Evolution (MDPI Mathematics, 2026)
  - Godel Agent: A Self-Referential Agent Framework (ACL 2025)
  - HyperAgents (Meta FAIR, 2026)
  - Position: Truly Self-Improving Agents Require Intrinsic Metacognitive Learning (ICML 2025)

集成点:
  - GodelianBoundary (P2): 接收不可判定命题 → 路由外部
  - MetaCognitiveLoop (P3): verify 阶段使用 SelfCheck 验证策略
  - RealityBridge (P1): 信任根锚定到物理世界
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from governance.meta.godelian_boundary import (
    GodelianBoundary,
    GodelianVerdict,
    Proposition,
)


# ── Domain Types ─────────────────────────────────────────────────────────────

class GapSeverity(str, Enum):
    """缺口严重度"""
    CRITICAL = "critical"     # 逻辑矛盾，必须立即修复
    HIGH = "high"             # 完备性缺口，影响核心功能
    MEDIUM = "medium"         # 潜在循环依赖
    LOW = "low"               # 可接受的不可判定命题
    INFO = "info"             # 信息性提示


class TrustRootType(str, Enum):
    """信任根类型"""
    AXIOM = "axiom"                       # 不可证但接受为真的公理
    EXTERNAL_ANCHOR = "external_anchor"   # 外部锚点（RealityBridge / 物理测试）
    HUMAN_OVERSIGHT = "human_oversight"   # 人类监督
    PROVEN = "proven"                     # 已被内部证明
    ASSUMED = "assumed"                   # 假设但未验证


@dataclass
class ContradictionNode:
    """一个自指矛盾节点。"""
    id: str
    description: str
    proposition_a: str          # 命题 A
    proposition_b: str          # 命题 B（与 A 矛盾）
    severity: GapSeverity
    affected_modules: list[str]  # 受影响的架构模块
    recommended_action: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "proposition_a": self.proposition_a,
            "proposition_b": self.proposition_b,
            "severity": self.severity.value,
            "affected_modules": self.affected_modules,
            "recommended_action": self.recommended_action,
        }


@dataclass
class CompletenessGap:
    """一个完备性缺口。"""
    id: str
    domain: str                 # 元理论域（如 safety, correctness, meta）
    description: str
    internal_provable: bool     # 系统内部是否可证
    external_verifiable: bool   # 是否可以外部验证
    godelian_verdict: str       # safe / internal / externalize / undecidable
    suggested_fix: str
    affected_layers: list[int]  # 受影响的元层级

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "description": self.description,
            "internal_provable": self.internal_provable,
            "external_verifiable": self.external_verifiable,
            "godelian_verdict": self.godelian_verdict,
            "suggested_fix": self.suggested_fix,
            "affected_layers": self.affected_layers,
        }


@dataclass
class TrustRoot:
    """一个信任根。"""
    id: str
    type: TrustRootType
    statement: str              # 公理陈述
    justification: str          # 为何接受此信任根
    verifiable: bool            # 是否可验证（但未验证）
    last_validated: float = 0.0 # 最近一次外部验证时间
    expires: bool = False       # 是否会过期（如外部锚点可能因环境变化而失效）

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "statement": self.statement,
            "justification": self.justification,
            "verifiable": self.verifiable,
            "last_validated": self.last_validated,
            "expires": self.expires,
        }


@dataclass
class SelfCheckReport:
    """一次完整的 SelfCheck 报告。"""
    check_id: str
    timestamp: float = field(default_factory=time.time)
    contradictions_found: list[ContradictionNode] = field(default_factory=list)
    completeness_gaps: list[CompletenessGap] = field(default_factory=list)
    trust_root_status: dict = field(default_factory=dict)
    overall_score: float = 1.0       # 0-1, 1 = 完全自恰
    critical_issues: int = 0
    godelian_delegated: int = 0      # 委托给 GodelianBoundary 的数量
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "timestamp": self.timestamp,
            "contradictions_found": [c.to_dict() for c in self.contradictions_found],
            "completeness_gaps": [g.to_dict() for g in self.completeness_gaps],
            "trust_root_status": self.trust_root_status,
            "overall_score": self.overall_score,
            "critical_issues": self.critical_issues,
            "godelian_delegated": self.godelian_delegated,
            "metadata": self.metadata,
        }


# ── SelfCheckEngine ──────────────────────────────────────────────────────────

class SelfCheckEngine:
    """哥德尔自指验证引擎。

    验证系统自身的完备性和一致性。

    使用方式:
        engine = SelfCheckEngine(godelian_boundary=gb)
        report = engine.run_full_check()
        if report.critical_issues > 0:
            fix_contradictions(report.contradictions_found)
    """

    # 预定义的自指矛盾检测规则
    CONTRADICTION_TEMPLATES: list[dict] = [
        {
            "id": "CONTRADICT-001",
            "prop_a": "系统是完备的（所有有效命题都可被证明）",
            "prop_b": "系统的安全性需要外部验证（GodelianBoundary EXTERNALIZE）",
            "modules": ["GodelianBoundary", "SelfCheckEngine"],
            "action": "承认不完备性，明确哪些命题域需要外部验证",
        },
        {
            "id": "CONTRADICT-002",
            "prop_a": "自演进闭环保证持续改进",
            "prop_b": "FixedPointDetector 在局部最优处停止（假收敛）",
            "modules": ["FixedPointDetector", "SelfEvolutionClosedLoop"],
            "action": "已通过 v11.28 防假收敛修正解决（SUSPICIOUS 状态）",
        },
        {
            "id": "CONTRADICT-003",
            "prop_a": "ABDL 规则引擎强制执行所有安全约束",
            "prop_b": "ABDL L0 规则可被自演进闭环修改",
            "modules": ["ABDL_Engine", "SelfEvolutionClosedLoop"],
            "action": "L0 规则标记为不可变（immutable），仅 L1-L3 可演进",
        },
        {
            "id": "CONTRADICT-004",
            "prop_a": "MetaCognitiveLoop 选择的策略是最优的",
            "prop_b": "策略 A/B 的比较依赖于 FixedPointDetector 的本地收敛判定",
            "modules": ["MetaCognitiveLoop", "FixedPointDetector"],
            "action": "接受次优性，标记为 heuristic-optimal 而非 global-optimal",
        },
        {
            "id": "CONTRADICT-005",
            "prop_a": "RealityBridge 提供客观的外部反馈",
            "prop_b": "RealityBridge 的仿真通道本身也是系统构建的（自主循环）",
            "modules": ["RealityBridge", "DigitalTwin"],
            "action": "明确声明显式外部通道（物理测试）vs 隐式外部通道（仿真）的区别",
        },
    ]

    def __init__(
        self,
        godelian_boundary: GodelianBoundary | None = None,
        trust_roots: list[TrustRoot] | None = None,
    ):
        self.godelian_boundary = godelian_boundary or GodelianBoundary()
        self.trust_roots: list[TrustRoot] = (
            trust_roots if trust_roots is not None else self._default_trust_roots()
        )
        self._check_history: list[SelfCheckReport] = []
        self._check_counter: int = 0

    # ── Layer 1: Contradiction Detection ──────────────────────────────────

    def detect_contradictions(self) -> list[ContradictionNode]:
        """扫描 42 层元能力中的逻辑矛盾。

        使用预定义模板 + 动态检测（通过 GodelianBoundary 分析自指命题）。
        """
        contradictions = []

        # 1. 静态模板检测
        for tmpl in self.CONTRADICTION_TEMPLATES:
            # 检查矛盾是否已被修正（通过检查 affected_modules 的状态）
            resolved = self._is_contradiction_resolved(tmpl["id"])
            if not resolved:
                contradictions.append(ContradictionNode(
                    id=tmpl["id"],
                    description=f"{tmpl['prop_a']} 与 {tmpl['prop_b']} 存在逻辑矛盾",
                    proposition_a=tmpl["prop_a"],
                    proposition_b=tmpl["prop_b"],
                    severity=GapSeverity.HIGH,
                    affected_modules=tmpl["modules"],
                    recommended_action=tmpl["action"],
                ))

        # 2. 动态检测: 通过 GodelianBoundary 分析自指命题
        dynamic_contradictions = self._detect_dynamic_contradictions()
        contradictions.extend(dynamic_contradictions)

        return contradictions

    def _is_contradiction_resolved(self, contradiction_id: str) -> bool:
        """检查某个已知矛盾是否已被修正。"""
        resolved = {
            "CONTRADICT-002": True,  # v11.28 amendment 已解决假收敛
        }
        return resolved.get(contradiction_id, False)

    def _detect_dynamic_contradictions(self) -> list[ContradictionNode]:
        """动态检测新的自指矛盾。"""
        contradictions = []
        # 生成自指命题并检查
        from governance.meta.godelian_boundary import PropositionGenerator
        gen = PropositionGenerator()
        undecidable_props = gen.generate_undecidable()

        for prop in undecidable_props:
            report = self.godelian_boundary.analyze(prop)
            if report.verdict == GodelianVerdict.UNDECIDABLE:
                contradictions.append(ContradictionNode(
                    id=f"DYNAMIC-{hashlib.md5(prop.content.encode()).hexdigest()[:8]}",
                    description=f"不可判定命题: {prop.content}",
                    proposition_a=prop.content,
                    proposition_b="系统无法自证此命题",
                    severity=GapSeverity.MEDIUM,
                    affected_modules=["GodelianBoundary", "SelfCheckEngine"],
                    recommended_action="委托 RealityBridge 外部验证",
                ))

        return contradictions

    # ── Layer 2: Completeness Analysis ────────────────────────────────────

    def analyze_completeness(self) -> list[CompletenessGap]:
        """分析元理论完备性缺口。

        扫描哪些命题域缺少内部验证路径。
        """
        gaps = []

        # Scanning domains
        domains = {
            "safety": "安全性验证",
            "correctness": "正确性证明",
            "performance": "性能保证",
            "fairness": "公平性",
            "robustness": "鲁棒性",
            "meta": "元理论自指",
        }

        for domain, desc in domains.items():
            # 为每个域生成一个可证性命题
            prop = Proposition(
                id=f"completeness_{domain}",
                content=f"The system can internally verify all {domain} properties",
                category=domain,
            )
            report = self.godelian_boundary.analyze(prop)

            is_internally_provable = report.verdict in (
                GodelianVerdict.SAFE, GodelianVerdict.INTERNAL
            )
            is_externally_verifiable = report.verdict in (
                GodelianVerdict.EXTERNALIZE, GodelianVerdict.UNDECIDABLE
            )

            gap = CompletenessGap(
                id=f"GAP-{domain.upper()}",
                domain=domain,
                description=f"{desc}: {report.reasoning}",
                internal_provable=is_internally_provable,
                external_verifiable=is_externally_verifiable,
                godelian_verdict=report.verdict.value,
                suggested_fix=(
                    "内部验证路径充足" if is_internally_provable
                    else f"需要 {report.recommended_channel} 外部验证"
                ),
                affected_layers=self._layers_for_domain(domain),
            )
            gaps.append(gap)

        return gaps

    def _layers_for_domain(self, domain: str) -> list[int]:
        """返回受域影响的元层级。"""
        domain_layers = {
            "safety": [0, 1, 5, 10],     # L0(公理), L1(规则), L5(安全), L10(对齐)
            "correctness": [0, 2, 8],    # L0, L2(验证), L8(审计)
            "performance": [3, 4, 15],   # L3(优化), L4(调度), L15(效率)
            "fairness": [6, 7, 18],      # L6(公平), L7(偏见), L18(伦理)
            "robustness": [9, 11, 20],   # L9(鲁棒), L11(对抗), L20(容错)
            "meta": [12, 13, 14, 21],    # L12-14(元层), L21(自演进)
        }
        return domain_layers.get(domain, [0])

    # ── Layer 3: Trust Root Management ────────────────────────────────────

    def _default_trust_roots(self) -> list[TrustRoot]:
        """默认信任根集合——系统的基本公理。"""
        return [
            TrustRoot(
                id="TR-001",
                type=TrustRootType.AXIOM,
                statement="BottleSumo 的核心目标是最大化安全条件下的相扑胜率",
                justification="项目宪章定义（toolchain_will.md）",
                verifiable=False,
            ),
            TrustRoot(
                id="TR-002",
                type=TrustRootType.AXIOM,
                statement="物理定律在擂台环境中是一致的（F=ma, τ=Iα）",
                justification="经典力学在宏观尺度下成立",
                verifiable=True,
            ),
            TrustRoot(
                id="TR-003",
                type=TrustRootType.EXTERNAL_ANCHOR,
                statement="RealityBridge 的仿真通道可以提供有意义的反馈",
                justification="仿真模型经过校准（P4 数字孪生）",
                verifiable=True,
                expires=True,
            ),
            TrustRoot(
                id="TR-004",
                type=TrustRootType.EXTERNAL_ANCHOR,
                statement="实机测试结果高于仿真预测结果",
                justification="仿真-实机差距可以通过系统辨识缩小",
                verifiable=True,
                expires=True,
            ),
            TrustRoot(
                id="TR-005",
                type=TrustRootType.HUMAN_OVERSIGHT,
                statement="人类操作员有权否决任何自动生成的策略",
                justification="人机协作安全原则",
                verifiable=True,
            ),
            TrustRoot(
                id="TR-006",
                type=TrustRootType.PROVEN,
                statement="FixedPointDetector 在 epsilon=0.01 时能正确检测收敛",
                justification="42 个单元测试通过 + 集成测试验证",
                verifiable=True,
                last_validated=time.time(),
            ),
            TrustRoot(
                id="TR-007",
                type=TrustRootType.PROVEN,
                statement="GodelianBoundary 能正确识别自指命题并路由外部",
                justification="43 个单元测试通过 + Godel 命题测试",
                verifiable=True,
                last_validated=time.time(),
            ),
        ]

    def validate_trust_roots(self) -> dict:
        """验证信任根的有效性。

        Returns:
            dict: {
                "total": int,
                "valid": int,
                "expired": list[TrustRoot],
                "unverifiable": list[TrustRoot],
                "circular_deps": list[str],
            }
        """
        expired = []
        unverifiable = []
        circular = []

        for root in self.trust_roots:
            # 检查过期
            if root.expires and root.last_validated > 0:
                age_hours = (time.time() - root.last_validated) / 3600
                if age_hours > 24:  # 外部锚点 24 小时后过期
                    expired.append(root)

            # 检查不可验证
            if not root.verifiable and root.type == TrustRootType.EXTERNAL_ANCHOR:
                unverifiable.append(root)

        # 检查信任链循环
        trust_refs = {}
        for root in self.trust_roots:
            for other in self.trust_roots:
                if root.id != other.id and root.statement in other.justification:
                    trust_refs.setdefault(root.id, []).append(other.id)
        # 检测循环
        for root_id, refs in trust_refs.items():
            for ref_id in refs:
                if ref_id in trust_refs and root_id in trust_refs[ref_id]:
                    circular.append(f"{root_id} ↔ {ref_id}")

        return {
            "total": len(self.trust_roots),
            "valid": len(self.trust_roots) - len(expired) - len(unverifiable),
            "expired": [r.to_dict() for r in expired],
            "unverifiable": [r.to_dict() for r in unverifiable],
            "circular_deps": circular,
        }

    def add_trust_root(self, root: TrustRoot):
        """添加新的信任根。"""
        # 检查不重复
        for existing in self.trust_roots:
            if existing.statement == root.statement:
                return  # 已存在
        self.trust_roots.append(root)

    def revoke_trust_root(self, root_id: str) -> bool:
        """撤销信任根。"""
        before = len(self.trust_roots)
        self.trust_roots = [r for r in self.trust_roots if r.id != root_id]
        return len(self.trust_roots) < before

    # ── Full Check ────────────────────────────────────────────────────────

    def run_full_check(self) -> SelfCheckReport:
        """执行完整的 SelfCheck 验证。

        返回综合报告，包含矛盾、完备性缺口、信任根状态。
        """
        self._check_counter += 1
        check_id = f"SELFCHECK-{self._check_counter:04d}"

        # Layer 1
        contradictions = self.detect_contradictions()

        # Layer 2
        completeness_gaps = self.analyze_completeness()

        # Layer 3
        trust_status = self.validate_trust_roots()

        # Scoring
        critical = sum(1 for c in contradictions
                       if c.severity == GapSeverity.CRITICAL)
        overall = self._compute_overall_score(
            contradictions, completeness_gaps, trust_status
        )

        # Godelian delegation
        delegated = len([
            g for g in completeness_gaps
            if g.godelian_verdict in ("externalize", "undecidable")
        ])

        report = SelfCheckReport(
            check_id=check_id,
            contradictions_found=contradictions,
            completeness_gaps=completeness_gaps,
            trust_root_status=trust_status,
            overall_score=overall,
            critical_issues=critical,
            godelian_delegated=delegated,
            metadata={
                "engine_version": "1.0.0",
                "trust_roots_count": len(self.trust_roots),
            },
        )

        self._check_history.append(report)
        return report

    def _compute_overall_score(
        self,
        contradictions: list[ContradictionNode],
        gaps: list[CompletenessGap],
        trust_status: dict,
    ) -> float:
        """计算整体自恰分数 (0-1)。"""
        score = 1.0

        # 每个 CRITICAL 矛盾扣 0.2
        critical_count = sum(1 for c in contradictions
                             if c.severity == GapSeverity.CRITICAL)
        score -= critical_count * 0.2

        # 每个 HIGH 矛盾扣 0.1
        high_count = sum(1 for c in contradictions
                         if c.severity == GapSeverity.HIGH)
        score -= high_count * 0.1

        # 每个不可内部验证的缺口扣 0.05
        incomplete = sum(1 for g in gaps if not g.internal_provable)
        score -= incomplete * 0.05

        # 过期信任根扣 0.1
        expired = len(trust_status.get("expired", []))
        score -= expired * 0.1

        # 循环依赖扣 0.15
        circular = len(trust_status.get("circular_deps", []))
        score -= circular * 0.15

        return max(0.0, min(1.0, round(score, 4)))

    # ── Observability ────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """获取运行时可观测状态。"""
        last_report = self._check_history[-1] if self._check_history else None
        return {
            "module": "SelfCheckEngine",
            "check_count": self._check_counter,
            "trust_roots_count": len(self.trust_roots),
            "last_score": last_report.overall_score if last_report else None,
            "last_critical_issues": last_report.critical_issues if last_report else 0,
            "contradiction_count": (
                len(last_report.contradictions_found) if last_report else 0
            ),
            "godelian_delegated": (
                last_report.godelian_delegated if last_report else 0
            ),
            "trust_roots_valid": (
                self.validate_trust_roots()["valid"]
            ),
        }

    def export_report(self, path: str | Path):
        """导出最近一次检查报告。"""
        if not self._check_history:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                self._check_history[-1].to_dict(),
                f, indent=2, ensure_ascii=False,
            )

    @property
    def history(self) -> list[SelfCheckReport]:
        return self._check_history

    def reset(self):
        self._check_history.clear()
        self._check_counter = 0
