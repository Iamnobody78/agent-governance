# Roadmap: agent-governance

**AI Agent 治理标准框架 — 路线图 v1.0 → v2.0 → v3.0**

---

## v1.0 — 核心治理引擎 ✅ (2026-07-27)

> **目标**: 完成可运行的治理核心，284 测试全绿，0 ruff errors。

| 模块 | 功能 | 测试 | 状态 |
|------|------|:--:|:--:|
| Meta-Theory Consistency | 42 层元能力逻辑矛盾检测 | P0 | ✅ |
| RealityBridge | 4 通道外部世界反馈 | P1 | ✅ |
| ApplicabilityGate | 8 维特征 MLP 任务分类器 | P2 | ✅ |
| FixedPointDetector | 假收敛检测 + 扰动注入 + 退火 | 42/42 | ✅ |
| GodelianBoundary | 自指命题检测 + 外部验证路由 | 43/43 | ✅ |
| MetaCognitiveLoop | 5 阶段元认知闭环 + A/B 双轨策略 | 49/49 | ✅ |
| SelfCheckEngine | 3 层自验证 + 7 信任根 | 50/50 | ✅ |
| DigitalTwinCalibrator | Sim-to-Real Gap 量化 + 漂移检测 | 44/44 | ✅ |
| ConfigLoader | YAML 配置 + 环境变量覆盖 | — | ✅ |
| CI/CD | 5-stage pipeline + self-heal | — | ✅ |

---

## v1.5 — 生态集成 🚧 (2026-08)

> **目标**: 让社区知道项目存在并能 5 分钟上手。

| 里程碑 | 内容 | 验收标准 |
|--------|------|----------|
| **README 重写** | "为什么" + "对比" + "生态集成" 三部分 | 新访客 30 秒理解项目价值 |
| **DEMO 示例** | `chat_agent_with_governance.py` | 可运行，展示完整治理流程 |
| **ECOSYSTEM 文档** | LangChain / AutoGen / CrewAI 集成指南 | 3 个框架的完整代码示例 |
| **ROADMAP 发布** | 本文档 | v1.0 → v3.0 清晰路径 |
| **GitHub Release** | v1.5.0 tag + Release Notes | 可下载的稳定版本 |

---

## v2.0 — 社区生态 (2026-09 ~ 2026-12)

> **目标**: 建立贡献者社区和应用案例库。

| 里程碑 | 内容 | 优先级 |
|--------|------|:------:|
| **插件机制** | 治理插件市场（社区贡献的安全规则、失败模式检测器） | P0 |
| **可视化面板** | Prometheus 指标导出 + Grafana 仪表盘模板 | P0 |
| **多语言绑定** | TypeScript/JavaScript SDK (for Node.js Agent frameworks) | P1 |
| **LangChain 正式包** | PyPI 发布 `agent-governance-langchain` | P1 |
| **AutoGen 正式包** | PyPI 发布 `agent-governance-autogen` | P1 |
| **案例库** | 5+ 个不同领域（客服/代码/机器人/数据分析/教育）的治理案例 | P1 |
| **基准测试** | Agent Governance Benchmark (AGB) — 10 个治理场景 + 评分 | P2 |
| **论文发表** | 将架构设计发布为学术论文（arXiv + 顶会投稿） | P2 |

---

## v3.0 — 治理标准 (2027+)

> **目标**: 成为 AI Agent 治理的事实标准。

| 里程碑 | 内容 |
|--------|------|
| **NIST AI RMF 对齐** | 将 agent-governance 映射到 NIST AI Risk Management Framework 的治理要求 |
| **EU AI Act 合规** | 提供符合 EU AI Act 的 Agent 合规检查清单和自动化审计 |
| **ISO 标准提案** | 基于框架编写 AI Agent 治理的 ISO 标准草案 |
| **行业认证** | "Agent Governance Certified" 认证体系 |
| **基金会** | 独立治理基金会（类似 CNCF） |

---

## 短期动作项 (最近 2 周)

- [x] 284 测试全绿 + 0 ruff
- [x] README 重写（"为什么需要" + "对比" + "生态集成"）
- [x] DEMO 示例 `chat_agent_with_governance.py`
- [x] ECOSYSTEM 集成文档
- [x] ROADMAP 发布
- [ ] GitHub Release v1.5.0
- [ ] 提交到 PyPI（`agent-governance`）
- [ ] Twitter/X + Reddit + HackerNews 发布
- [ ] 联系 LangChain / AutoGen 社区寻求集成评审

---

## 关键指标

| 指标 | v1.0 | v1.5 | v2.0 | v3.0 |
|------|:----:|:----:|:----:|:----:|
| GitHub Stars | — | 100 | 1,000 | 10,000 |
| Contributors | 1 | 5 | 20 | 50 |
| 集成框架 | 0 | 3 (docs) | 5+ (packages) | 10+ |
| PyPI downloads | — | 100/mo | 1,000/mo | 10,000/mo |
| 测试覆盖率 | 284 tests | 300+ | 500+ | 1,000+ |
| 治理案例 | 0 | 1 (demo) | 10+ | 50+ |

---

*最后更新: 2026-08-01*
