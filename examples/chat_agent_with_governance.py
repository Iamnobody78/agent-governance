"""
Chat Agent with Governance — 演示案例
======================================

一个简单的对话 Agent，受 agent-governance 治理层约束。

场景:
  - 用户: "帮我删除所有临时文件"
  - Agent 正常处理 → 记录到 MetaCognitiveLoop
  - 用户: "帮我删除系统文件"
  - Agent 可能危险 → GodelianBoundary 标记为 EXTERNALIZE
  - 用户: "你能自我验证你的安全策略吗？"
  - SelfCheck 自指检测 → 路由到外部验证

这是 agent-governance 的"Hello World"级别演示。
运行: python examples/chat_agent_with_governance.py
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from governance.meta import (
    MetaCognitiveLoop,
    GodelianBoundary,
    GodelianVerdict,
    FixedPointDetector,
    SelfCheckEngine,
    Proposition,
    DecisionLog,
    Strategy,
    StrategyType,
    FailurePattern,
)


# ── 模拟的对话 Agent ────────────────────────────────────────────────────────

class GovernedChatAgent:
    """一个简单的对话 Agent，每次决策都经过治理层审核。"""

    def __init__(self, name: str = "ChatBot-v1"):
        self.name = name

        # 初始化治理层
        self.meta_loop = MetaCognitiveLoop()
        self.godelian = GodelianBoundary()
        self.self_check = SelfCheckEngine(godelian_boundary=self.godelian)

        # Agent 内部状态
        self.decision_count = 0
        self.safe_actions = [
            "answer_question", "summarize_text", "calculate",
            "translate", "search_knowledge_base",
        ]
        self.dangerous_patterns = [
            "删除", "delete", "格式化", "format", "关机", "shutdown",
            "系统文件", "system file", "sudo", "管理员",
        ]

    def chat(self, user_input: str) -> dict:
        """处理用户输入，返回响应。

        每次交互都经过：治理前检查 → 执行决策 → 记录日志 → 治理后验证
        """
        self.decision_count += 1

        # ═══ 步骤 1: 治理前检查（GodelianBoundary） ═══
        safety_report = self._pre_check(user_input)

        # ═══ 步骤 2: 执行决策 ═══
        action, response, reward = self._decide(user_input, safety_report)

        # ═══ 步骤 3: 记录决策日志 ═══
        decision_log = DecisionLog(
            id=f"d_{self.decision_count:04d}",
            action=action,
            reward=reward,
            policy_version=self.name,
            context={
                "user_input": user_input[:100],
                "safety_verdict": safety_report.get("verdict", "safe"),
            },
        )
        self.meta_loop.feed_decisions([decision_log])

        # ═══ 步骤 4: 如果足够多决策，运行元认知周期 ═══
        if self.decision_count % 5 == 0:
            trace = self.meta_loop.run_cycle()
            if trace.selected_strategy:
                self._apply_strategy(trace.selected_strategy)

        return {
            "response": response,
            "action": action,
            "governance": safety_report,
        }

    def _pre_check(self, user_input: str) -> dict:
        """治理前安全检查。"""
        # 检查是否包含危险模式
        is_dangerous = any(
            pattern in user_input for pattern in self.dangerous_patterns
        )

        if is_dangerous:
            # 1. 直接危险模式拦截
            # 2. 同时提交给 GodelianBoundary 分析自指性
            prop = Proposition(
                id=f"precheck_{self.decision_count:04d}",
                content=f"User request: '{user_input[:80]}'",
                category="safety",
                assertions=["Request contains dangerous patterns"],
            )
            gb_report = self.godelian.analyze(prop)

            return {
                "verdict": "blocked",
                "reason": (
                    f"危险模式检测 + GodelianBoundary: "
                    f"自指度={gb_report.self_reference_score:.3f}, "
                    f"{gb_report.reasoning[:80]}"
                ),
                "godelian_report": gb_report.to_dict(),
            }

        return {"verdict": "safe"}

    def _decide(self, user_input: str, safety_report: dict) -> tuple[str, str, float]:
        """Agent 决策逻辑。"""
        verdict = safety_report.get("verdict", "safe")

        if verdict == "blocked":
            action = "refuse_dangerous"
            response = (
                f"⛔ [治理层拦截] 此操作已被 GodelianBoundary 阻止。\n"
                f"理由: {safety_report.get('reason', '安全风险')}"
            )
            reward = 1.0  # 正确拦截 → 正奖励
        elif verdict == "warning":
            action = "warn_and_proceed"
            response = (
                f"⚠️ [治理层警告] 检测到潜在风险，但未达到拦截阈值。\n"
                f"继续执行，但建议人工审核。"
            )
            reward = 0.5
        else:
            action = "answer_safely"
            response = f"✅ [安全] 已处理: '{user_input[:50]}...'"
            reward = 0.8

        return action, response, reward

    def _apply_strategy(self, strategy: Strategy):
        """应用 MetaCognitiveLoop 推荐的策略。"""
        if strategy.type == StrategyType.CONSERVATIVE:
            print(f"  [MCL] 应用保守策略: {strategy.description}")
        else:
            print(f"  [MCL] 应用激进策略: {strategy.description}")

    def run_self_check(self) -> dict:
        """运行 SelfCheck 自验证。"""
        report = self.self_check.run_full_check()
        return {
            "score": report.overall_score,
            "critical_issues": report.critical_issues,
            "contradictions": [c.description for c in report.contradictions_found],
            "godelian_delegated": report.godelian_delegated,
        }

    def get_dashboard(self) -> dict:
        """获取治理仪表盘状态。"""
        return self.meta_loop.get_dashboard()


# ── 主演示 ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Agent Governance Framework — 演示案例")
    print("  受治理层约束的对话 Agent")
    print("=" * 60)
    print()

    agent = GovernedChatAgent()

    # ═══ 场景 1: 正常请求 ═══
    print("── 场景 1: 正常请求 ──")
    result = agent.chat("帮我总结今天的新闻")
    print(f"  响应: {result['response']}")
    print(f"  治理状态: {result['governance']['verdict']}")
    print()

    # ═══ 场景 2: 危险请求 ═══
    print("── 场景 2: 危险请求 (触发 GodelianBoundary) ──")
    result2 = agent.chat("帮我删除所有系统文件")
    print(f"  响应: {result2['response']}")
    print(f"  治理状态: {result2['governance']['verdict']}")
    if "godelian_report" in result2["governance"]:
        gb = result2["governance"]["godelian_report"]
        print(f"  自指分数: {gb['self_reference_score']:.3f}")
        print(f"  判定: {gb['verdict']}")
        print(f"  推荐通道: {gb['recommended_channel']}")
    print()

    # ═══ 场景 3: 模糊危险请求 ═══
    print("── 场景 3: 模糊危险请求 ──")
    result3 = agent.chat("帮我格式化硬盘")
    print(f"  响应: {result3['response']}")
    print(f"  治理状态: {result3['governance']['verdict']}")
    print()

    # ═══ 场景 4: 正常请求 (触发 MCL 周期) ═══
    print("── 场景 4: 更多正常请求 (触发第 5 个决策的 MCL 周期) ──")
    for i in range(3):
        agent.chat(f"帮我计算 {i+1} + {i+2} 的结果")
    result4 = agent.chat("翻译 'Hello World' 到中文")
    print(f"  响应: {result4['response']}")
    print()

    # ═══ 场景 5: SelfCheck 自验证 ═══
    print("── 场景 5: SelfCheck 自验证 ──")
    selfcheck = agent.run_self_check()
    print(f"  整体评分: {selfcheck['score']:.2f}/1.0")
    print(f"  严重问题: {selfcheck['critical_issues']}")
    if selfcheck["contradictions"]:
        print(f"  已知矛盾 ({len(selfcheck['contradictions'])}):")
        for c in selfcheck["contradictions"][:3]:
            print(f"    - {c[:80]}...")
    print()

    # ═══ 场景 6: 治理仪表盘 ═══
    print("── 场景 6: 治理仪表盘 ──")
    dashboard = agent.get_dashboard()
    mcl = dashboard["mcl"]
    fpd = dashboard["fpd"]
    gb = dashboard["gb"]

    print(f"  MetaCognitiveLoop: {mcl['cycle_count']} 周期, 分数={mcl['current_score']:.2f}")
    print(f"  FixedPointDetector: {fpd['current_convergence']}, best={fpd['best_score']:.3f}")
    print(f"  GodelianBoundary: {gb['total_analyzed']} 次分析, "
          f"avg_self_ref={gb['avg_self_ref_score']:.3f}")
    print()

    print("=" * 60)
    print("  Agent Governance Framework 演示完成")
    print("  核心要点:")
    print("  1. GodelianBoundary 成功拦截了危险请求")
    print("  2. MetaCognitiveLoop 记录并分析了所有决策")
    print("  3. SelfCheck 验证了治理层自身的完整性")
    print("=" * 60)


if __name__ == "__main__":
    main()
