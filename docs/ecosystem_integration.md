# Ecosystem Integration Guide

**将 `agent-governance` 注入到任何现有 Agent 框架。**

`agent-governance` 不是另一个 Agent 框架——它是 **治理层（Governance Layer）**。你不需要替换 LangChain / AutoGen / CrewAI / OpenAI Assistants，只需要在它们和用户/环境之间插入治理检查。

---

## 集成模式

### Pattern 1: 包装器模式（推荐）

在 Agent 的决策函数前后插入治理检查：

```python
class GovernedAgent:
    def __init__(self, base_agent, meta_loop, godelian):
        self.agent = base_agent
        self.meta = meta_loop
        self.gb = godelian

    def decide(self, context):
        # 治理前检查
        safety = self.gb.analyze(Proposition(...))
        if safety.verdict == "externalize":
            return self.escalate(safety)

        # 执行原 Agent 决策
        result = self.agent.decide(context)

        # 记录决策
        self.meta.feed_decisions([DecisionLog(...)])

        # 定期运行元认知周期
        if self.should_reflect():
            self.meta.run_cycle()

        return result
```

### Pattern 2: 回调模式

将治理检查注册为框架的回调/中间件：

```python
agent.register_pre_hook("decide", godelian_boundary.check)
agent.register_post_hook("decide", meta_cognitive_loop.log)
agent.register_periodic_hook(interval=10, callback=meta_cognitive_loop.run_cycle)
```

---

## LangChain 集成

LangChain 的 `AgentExecutor` 可以包装在 `GovernedChain` 中：

```python
from langchain.agents import AgentExecutor, create_react_agent
from governance.meta import MetaCognitiveLoop, GodelianBoundary, Proposition, DecisionLog

class GovernedChain(AgentExecutor):
    """LangChain Agent 的治理包装器。"""

    def __init__(self, agent, tools, meta_loop=None, godelian=None):
        super().__init__(agent=agent, tools=tools)
        self.meta_loop = meta_loop or MetaCognitiveLoop()
        self.godelian = godelian or GodelianBoundary()
        self._step_count = 0

    def invoke(self, input_data, **kwargs):
        # Step 1: 治理前检查
        user_input = str(input_data.get("input", ""))
        prop = Proposition(
            id=f"langchain_{self._step_count}",
            content=user_input,
            category="safety",
        )
        gb_report = self.godelian.analyze(prop)

        if gb_report.verdict == "externalize":
            # 需要外部验证，返回安全响应
            return {"output": "Action blocked by governance layer. Requires human review."}

        # Step 2: 执行原始决策
        result = super().invoke(input_data, **kwargs)

        # Step 3: 记录决策日志
        self._step_count += 1
        self.meta_loop.feed_decisions([DecisionLog(
            id=f"lc_{self._step_count}",
            action=result.get("output", "")[:50],
            reward=0.8,  # 根据结果调整
            context={"source": "langchain"},
        )])

        # Step 4: 定期元认知周期
        if self._step_count % 10 == 0:
            self.meta_loop.run_cycle()

        return result
```

**使用方式**:
```python
from langchain.agents import create_react_agent
from langchain.tools import Tool

tools = [Tool(name="Search", func=search_fn, description="Search the web")]
agent = create_react_agent(llm, tools, prompt)
governed = GovernedChain(agent=agent, tools=tools)
result = governed.invoke({"input": "Help me delete system files"})
# → "Action blocked by governance layer. Requires human review."
```

---

## AutoGen 集成

AutoGen 的 `AssistantAgent` 可以包装在 `GovernedAssistant` 中：

```python
from autogen import AssistantAgent
from governance.meta import MetaCognitiveLoop, GodelianBoundary, Proposition, DecisionLog

class GovernedAssistant(AssistantAgent):
    """AutoGen AssistantAgent 的治理包装器。"""

    def __init__(self, name, llm_config, meta_loop=None, godelian=None, **kwargs):
        super().__init__(name=name, llm_config=llm_config, **kwargs)
        self.meta_loop = meta_loop or MetaCognitiveLoop()
        self.godelian = godelian or GodelianBoundary()
        self._msg_count = 0

    def generate_reply(self, messages=None, sender=None, **kwargs):
        # 治理前检查最近的用户消息
        if messages:
            last_msg = messages[-1] if isinstance(messages[-1], dict) else str(messages[-1])
            prop = Proposition(
                id=f"autogen_{self._msg_count}",
                content=str(last_msg)[:100],
                category="safety",
            )
            gb_report = self.godelian.analyze(prop)

            if gb_report.verdict in ("externalize", "undecidable"):
                return True, {
                    "content": "⛔ Governance layer blocked this action. Requires human approval.",
                    "role": "assistant",
                }

        # 执行原始生成
        reply = super().generate_reply(messages, sender, **kwargs)

        # 记录
        self._msg_count += 1
        self.meta_loop.feed_decisions([DecisionLog(
            id=f"ag_{self._msg_count}",
            action="generate_reply",
            reward=0.7,
            context={"sender": str(sender) if sender else "unknown"},
        )])

        return reply
```

**使用方式**:
```python
governed_bot = GovernedAssistant(
    name="SafeAssistant",
    llm_config={"config_list": [{"model": "gpt-4", "api_key": "..."}]},
)

user_proxy.initiate_chat(
    governed_bot,
    message="Delete all user data permanently"
)
# → "⛔ Governance layer blocked this action."
```

---

## CrewAI 集成

CrewAI 的 `Crew` 可以升级为 `GovernedCrew`：

```python
from crewai import Crew, Agent, Task
from governance.meta import MetaCognitiveLoop, GodelianBoundary

class GovernedCrew(Crew):
    """CrewAI Crew 的治理包装器。"""

    def __init__(self, agents, tasks, meta_loop=None, godelian=None, **kwargs):
        super().__init__(agents=agents, tasks=tasks, **kwargs)
        self.meta_loop = meta_loop or MetaCognitiveLoop()
        self.godelian = godelian or GodelianBoundary()
        self._task_count = 0

    def kickoff(self, inputs=None):
        # 治理前验证所有任务
        for task in self.tasks:
            prop = Proposition(
                id=f"crew_task_{self._task_count}",
                content=task.description,
                category="safety",
            )
            gb_report = self.godelian.analyze(prop)
            if gb_report.verdict == "externalize":
                raise ValueError(f"Task '{task.description[:50]}' blocked by governance layer.")

        result = super().kickoff(inputs)

        self._task_count += 1
        if self._task_count % 3 == 0:
            self.meta_loop.run_cycle()

        return result
```

---

## 自定义 Agent 集成

如果你有自己的 Agent 实现（不依赖任何框架）：

```python
from governance.meta import MetaCognitiveLoop, GodelianBoundary, FixedPointDetector
from governance.meta import SelfCheckEngine, DecisionLog, Proposition

# 1. 初始化治理层
meta = MetaCognitiveLoop()
gb = GodelianBoundary()
fpd = FixedPointDetector()
selfcheck = SelfCheckEngine(godelian_boundary=gb)

# 2. 在每个决策点插入治理检查
def governed_decision(agent, observation):
    # Godelian 安全检查
    safety = gb.analyze(Proposition(
        id=f"step_{agent.step}",
        content=str(observation),
        category="safety",
    ))
    if safety.verdict in ("externalize", "undecidable"):
        return safe_fallback_action()

    # 执行原始策略
    action = agent.policy(observation)

    # 记录决策
    meta.feed_decisions([DecisionLog(
        id=f"step_{agent.step}",
        action=str(action),
        reward=agent.last_reward,
    )])

    # 定期运行元认知
    if agent.step % 10 == 0:
        trace = meta.run_cycle()
        if trace.selected_strategy:
            agent.apply_strategy(trace.selected_strategy)

    return action

# 3. 定期自验证
if agent.step % 100 == 0:
    report = selfcheck.run_full_check()
    print(f"SelfCheck: score={report.overall_score}, critical={report.critical_issues}")
```

---

## 治理仪表盘（所有框架通用）

无论你使用哪个框架，都可以通过 `get_dashboard()` 获取统一的治理状态：

```python
dashboard = meta_loop.get_dashboard()

# 发送到监控系统
prometheus.push(dashboard["fpd"])  # FixedPointDetector 状态
prometheus.push(dashboard["gb"])   # GodelianBoundary 状态
prometheus.push(dashboard["mcl"])  # MetaCognitiveLoop 状态

# 或导出为 JSON
import json
print(json.dumps(dashboard, indent=2))
```

---

## 总结

| 框架 | 集成方式 | 侵入性 | 推荐场景 |
|------|----------|:------:|----------|
| **LangChain** | `GovernedChain` 包装 `AgentExecutor` | 低 | LLM Agent 开发 |
| **AutoGen** | `GovernedAssistant` 继承 `AssistantAgent` | 低 | 多 Agent 对话 |
| **CrewAI** | `GovernedCrew` 继承 `Crew` | 低 | 任务编排 |
| **自定义** | 函数级包装 | 极低 | 完全控制 |
