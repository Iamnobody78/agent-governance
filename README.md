# Agent Governance Framework

**AI Agent 治理标准框架 — 让任何 Agent 具备元认知、自演进、安全边界。**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Tests: 284/284](https://img.shields.io/badge/Tests-284%2F284-brightgreen.svg)](https://github.com/ivy-ai/agent-governance/actions)
[![Ruff: 0](https://img.shields.io/badge/Ruff-0%20errors-brightgreen.svg)](https://github.com/astral-sh/ruff)
[![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)](https://github.com/ivy-ai/agent-governance)

---

## 为什么需要 Agent Governance？

当前 AI Agent 面临 **四个根本性问题**，且没有任何现有框架系统性地解决它们：

| # | 问题 | 表现 | agent-governance 的解决方案 |
|:--:|------|------|---------------------------|
| 1 | **无元认知** | Agent 不知道"自己不知道什么"，不会主动请求帮助 | **MetaCognitiveLoop** — 监控→评估→策略A/B生成→调节→验证 |
| 2 | **无自演进** | Agent 行为固定，卡在局部最优，无法从失败中学习 | **FixedPointDetector** — 假收敛检测 + 扰动注入 + 退火 |
| 3 | **无安全边界** | Agent 可能执行"理论上正确但实际危险"的操作 | **GodelianBoundary** — 识别自指命题，路由到外部验证 |
| 4 | **无自我验证** | 系统声称"我是安全的"但无法自证 | **SelfCheckEngine** — 三层验证：矛盾检测 + 完备性分析 + 信任根管理 |

**`agent-governance` 不是一个 Agent 框架——它是任何 Agent 框架的上层治理层。**

---

## 对比：agent-governance vs 现有框架

| 维度 | LangChain / AutoGen / CrewAI | agent-governance |
|------|------------------------------|------------------|
| **定位** | Agent 开发框架 | Agent 治理层（插入到任何框架之上） |
| **元认知** | ❌ 无 | ✅ 5 阶段元认知闭环 |
| **安全边界** | ⚠️ 仅规则过滤 | ✅ 哥德尔边界 + 自指检测 + 外部验证路由 |
| **自演进** | ❌ 无 | ✅ 不动点检测 + 假收敛防护 |
| **可观测性** | ⚠️ 基础日志 | ✅ 3 模块 get_state() + get_dashboard() |
| **数字孪生** | ❌ 无 | ✅ Sim-to-Real Gap 量化 + 漂移检测 |
| **信任根** | ❌ 无 | ✅ 7 类信任根（公理 / 外部锚点 / 人类监督 / 已证明） |
| **学术锚点** | ❌ 无 | ✅ 7 篇顶会论文映射 (ACL/ICML/NeurIPS 2025-2026) |
| **侵入性** | 必须替换 Agent 框架 | **零侵入**——实现 4 个接口方法即可 |

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/ivy-ai/agent-governance.git
cd agent-governance
pip install -r requirements.txt
```

### 2. 30 秒体验：为你的 Agent 添加治理层

```python
from governance.meta import MetaCognitiveLoop, GodelianBoundary, FixedPointDetector
from governance.meta import SelfCheckEngine, DigitalTwinCalibrator

# 一行初始化治理核心
loop = MetaCognitiveLoop()

# 喂入决策日志（你的 Agent 产生的任何决策）
from governance.meta import DecisionLog
loop.feed_decisions([
    DecisionLog(id="d1", action="answer_query", reward=0.8),
    DecisionLog(id="d2", action="refuse_unsafe", reward=0.95),
])

# 运行一个完整的元认知周期
trace = loop.run_cycle()
print(f"Gaps found: {len(trace.gaps_found)}")
print(f"Strategies: {[s.description for s in trace.strategies]}")
print(f"Selected: {trace.selected_strategy.description if trace.selected_strategy else 'None'}")
```

### 3. 运行测试

```bash
pytest tests/ -q
# 284 passed in 1.05s
```

---

## 核心模块

| 模块 | 功能 | 测试 | 论文锚点 |
|------|------|:--:|------|
| **FixedPointDetector** | 假收敛检测 + 扰动注入 + 退火 | 42/42 | HyperAgents (Meta, 2026) |
| **GodelianBoundary** | 自指命题检测 + 外部验证路由 | 43/43 | Goedel Agent (ACL 2025) + MES |
| **MetaCognitiveLoop** | 5 阶段元认知闭环 + A/B 双轨策略 | 49/49 | MARS (ACL 2026) + ICML 2025 |
| **SelfCheckEngine** | 3 层自验证：矛盾 + 完备性 + 信任根 | 50/50 | Adaptive Quine (MDPI 2026) |
| **DigitalTwinCalibrator** | Sim-to-Real Gap 量化 + 漂移检测 | 44/44 | RoboVerse + SimLifter + TWICE |

---

## 生态集成

`agent-governance` 设计为**零侵入**——你不需要替换现有的 Agent 框架。把它插入到你的 Agent 和用户/环境之间作为治理层即可。

| 框架 | 集成方式 | 文档 |
|------|----------|------|
| **LangChain** | `GovernedChain` 包装 `AgentExecutor` | [docs/ecosystem_integration.md](docs/ecosystem_integration.md#langchain) |
| **AutoGen** | import `GovernedAgent` 替代 `AssistantAgent` | [docs/ecosystem_integration.md](docs/ecosystem_integration.md#autogen) |
| **CrewAI** | `GovernedCrew` 注入治理回调 | [docs/ecosystem_integration.md](docs/ecosystem_integration.md#crewai) |
| **OpenAI Assistants** | Function calling 注入治理检查 | [docs/ecosystem_integration.md](docs/ecosystem_integration.md#openai) |
| **自定义 Agent** | 实现 4 个接口方法 | [docs/integration_guide.md](docs/integration_guide.md) |

完整示例：**[examples/chat_agent_with_governance.py](examples/chat_agent_with_governance.py)**

---

## 文档

| 文档 | 说明 |
|------|------|
| [Architecture Overview](docs/architecture_overview.md) | 42 层元能力架构 |
| [Integration Guide](docs/integration_guide.md) | 如何集成新 Agent |
| [Ecosystem Integration](docs/ecosystem_integration.md) | LangChain / AutoGen / CrewAI 集成 |
| [Roadmap](docs/ROADMAP.md) | v1.0 → v2.0 → v3.0 路线图 |
| [ABDL Language](docs/abdl_reference.md) | Agent Behavior Description Language |
| [Example: BottleSumo](examples/bottlesumo/) | 参考实现（140GB 旗舰版） |

---

## 架构

```
governance/meta/
├── fixed_point_detector.py      # Phase 1: 不动点检测（HyperAgents 论文）
├── godelian_boundary.py         # Phase 2: 哥德尔边界（Gödel Agent 论文）
├── meta_cognitive_loop.py       # Phase 3: 元认知闭环（MARS 论文）
├── self_check_engine.py         # P3: 自验证引擎（Adaptive Quine 论文）
├── digital_twin_calibrator.py   # P4: 数字孪生校准（RoboVerse + SimLifter）
├── config_loader.py             # YAML 配置管理
└── meta_modules_config.yaml     # 46 行可调参数
```

---

## 维护模式：Agent-First

本项目由 **AI Agent 团队**维护。人类维护者只做战略决策。

| 角色 | 职责 |
|------|------|
| **AI Agent Team** | Code review, testing, docs, releases, Issue triage, PR validation |
| **Human Maintainers** | Strategic direction, major change approval, complex issue resolution |

见 [.github/AGENTS.md](.github/AGENTS.md)。

---

## 学术引用

如果你在学术研究中使用本框架，请引用以下论文：

- **HyperAgents**: Zhang et al., "HyperAgents: Scaling Self-Improving AI Agents", Meta FAIR, 2026
- **Gödel Agent**: Yin et al., "Gödel Agent: A Self-Referential Agent Framework", ACL 2025
- **MARS**: Hou et al., "Learn Like Humans: Use Meta-cognitive Reflection", ACL 2026
- **Adaptive Quine**: Saghiri et al., "Adaptive Quine Structures for Metacognitive Evolution", MDPI Mathematics 2026

---

## License

MIT © 2025-2026 Agent Governance Contributors

## Contributing

见 [CONTRIBUTING.md](CONTRIBUTING.md)。所有贡献经 AI Agent 团队审查。
