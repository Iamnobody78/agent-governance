# ARCHITECTURE.md — agent-governance v2

> 本文档是 agent-governance v2 的架构设计文件。它以 v1.7.0-PoC 的自我批判为起点，定义了一个诚实的、可验证的、生产就绪的 Agent 治理框架。

---

## 第一章：为什么重来

### 1.1 v1 的问题不是"实现不到位"，是"概念与代码之间不存在对应关系"

v1.7.0-PoC 的 CRITIQUE.md 对 6 个核心模块的逐行审计揭示了一个系统性模式：

| 模块 | 宣称 | 实际代码 | 行号 |
|------|------|----------|:--:|
| GodelianBoundary | 哥德尔不完备性边界检测 | 6 个关键词正则匹配 | `godelian_boundary.py:110-117` |
| FixedPointDetector | Banach 不动点检测假收敛 | `abs(current - previous) < epsilon` | `fixed_point_detector.py:32` |
| MetaCognitiveLoop | 5 阶段元认知闭环 | 均值+多样性阈值；开发者自注"玩具算式" | `meta_cognitive_loop.py:314,504` |
| SelfCheck | 10 边界场景验证 | `len(strategy.description) < 3` | `meta_cognitive_loop.py:573` |
| AgentInterface | 零侵入 Sidecar | ABC 继承 + 4 个 @abstractmethod | `agent_interface.py:13-68` |
| 530 测试 | 治理逻辑测试 | dataclass 字段赋值验证（~70ms/test） | 全部 test_*.py |

**这不是一个可以"修复"的代码库。** 每一行代码都是为"看起来像那么回事"而写的，不是为"真正工作"而写的。在 regex 基础上补 Gödel 编号和在自行车上装火箭发动机一样——底盘不承载。

### 1.2 v1 的真正价值

v1 不是废品。它的价值不在代码而在三个层面：

| 层面 | 价值 | v2 如何使用 |
|------|------|-------------|
| **问题定义** | 4 个根本性问题（元认知缺失、无自演进、无安全边界、无自我验证）是真实存在的 | 保留为 v2 的 North Star |
| **架构草图** | 4 层架构（数据→引擎→标准化→组织）是对的 | 保留架构分层，更换每层的实现方式 |
| **教训** | v1 是"如何不做一个治理框架"的完整案例 | CRITIQUE.md 作为 v2 的开发宪法，每个 Pull Request 必须对齐宣称 |

### 1.3 v2 的铁律

从 v1 的失败中提取三条不可违反的原则：

| # | 铁律 | 检查方式 |
|:--:|------|----------|
| 1 | **每个宣称必须有可执行的代码证据** | PR Review 时用 `grep` 验证：宣称 A → 代码必须有 A 的实现（不能是空壳/正则/阈值） |
| 2 | **每个测试必须验证真实运行时行为** | 禁止 `assert x == y` 式的 dataclass 赋值测试；每个测试必须涉及 IO/网络/状态迁移 |
| 3 | **文档与代码同一仓库、同一提交** | 架构决策记录（ADR）与实现代码在同一 PR 中提交 |

---

## 第二章：诚实架构

### 2.1 核心定位变更

| | v1 | v2 |
|---|-----|-----|
| **定位** | "可迁移的 Agent 治理范式" | "Agent 行为的透明代理网关" |
| **侵入性** | ABC 继承（SDK 模式） | HTTP/gRPC 拦截代理（Sidecar 模式） |
| **部署方式** | `pip install` + 修改 Agent 代码 | 独立进程，与 Agent 并列运行 |
| **目标用户** | Agent 开发者 | 平台运维 / SRE |

### 2.2 物理架构

```
┌─────────────┐    HTTP/gRPC     ┌─────────────────┐    HTTP/gRPC     ┌─────────────┐
│             │ ───────────────→ │                 │ ───────────────→ │             │
│  User/API   │                  │ agent-governance│                  │  Agent      │
│  Client     │ ←─────────────── │ v2 (Sidecar)    │ ←─────────────── │  (LangChain/│
│             │                  │                 │                  │  AutoGen/   │
└─────────────┘                  │ port :9000      │                  │  CrewAI...) │
                                 └────────┬────────┘                  └─────────────┘
                                          │
                                          │ 写入
                                          ▼
                                 ┌─────────────────┐
                                 │  DecisionLog    │
                                 │  (SQLite/        │
                                 │   PostgreSQL)    │
                                 └────────┬────────┘
                                          │
                                          │ 查询
                                          ▼
                                 ┌─────────────────┐
                                 │  Dashboard      │
                                 │  (Grafana/       │
                                 │   Web UI)        │
                                 └─────────────────┘
```

**关键特性**：

- **Agent 代码零修改**：Agent 不知道治理层存在。它只看到来自治理层转发的请求。
- **独立进程**：崩溃不传染。治理层挂了，Agent 仍可直连（降级模式）。
- **协议无关**：首个版本支持 HTTP/gRPC，后续可扩展 WebSocket/stdio。

### 2.3 逻辑架构（4 层）

```
┌──────────────────────────────────────────────────────────────────┐
│ L4  组织层    │ 审计报告 / 合规仪表盘 / 策略管理 UI               │
├──────────────────────────────────────────────────────────────────┤
│ L3  策略层    │ 策略引擎（YAML→可执行规则） / 冲突检测 / 优先级    │
├──────────────────────────────────────────────────────────────────┤
│ L2  决策层    │ 拦截 → 分析 → 裁决 → 转发 / 拒绝 / 升级            │
├──────────────────────────────────────────────────────────────────┤
│ L1  数据层    │ 请求/响应日志 / 决策记录 / 状态快照 / 密码学签名    │
└──────────────────────────────────────────────────────────────────┘
```

#### L1: 数据层

| 组件 | 说明 | 技术选型 |
|------|------|----------|
| RequestLog | 完整的 HTTP/gRPC 请求/响应记录 | JSON Lines 文件 + SQLite |
| DecisionRecord | 每次裁决的完整记录（输入、规则匹配、结果、时间戳） | SQLite（本地）/ PostgreSQL（集群） |
| StateSnapshot | Agent 状态快照（用于回滚和分析） | SQLite BLOB |
| CryptoSigner | 对决策记录进行签名（防篡改审计） | Ed25519 / HMAC-SHA256 |

**v1 教训**：v1 的数据层是内存字典（`DecisionLog = List[dict]`），进程重启全丢失。v2 必须持久化。

#### L2: 决策层

这是 v2 的核心——请求拦截与裁决引擎。

```
Request → [Parse] → [PolicyMatch] → [Verdict] → Forward / Deny / Escalate
                         │
                         ├─ 匹配策略规则
                         ├─ 计算风险分数
                         ├─ 检查速率限制
                         └─ 记录决策日志
```

| 裁决 | 动作 |
|------|------|
| `ALLOW` | 转发请求到 Agent，记录日志 |
| `DENY` | 返回 403，记录日志 + 原因 |
| `ESCALATE` | 挂起请求，推送审批通知（Webhook / Slack / 飞书） |

**v1 教训**：v1 的裁决是纯内存运算，无超时、无熔断、无人工审批通道。v2 必须实现：

- **超时**：单次裁决 > 500ms 自动降级为 ALLOW（不阻塞 Agent）
- **熔断**：连续 10 次 ESCALATE 未获审批 → 自动 ALLOW（不卡死管道）
- **人工审批**：Webhook 推送 → 外部系统确认 → 回调继续

#### L3: 策略层

策略用 YAML 定义，由策略引擎编译为可执行规则。

```yaml
# policy: block_delete.yaml
name: block-delete-operations
scope: ["production"]
rules:
  - action: DENY
    condition:
      method: POST
      path_pattern: "/api/delete/*"
    reason: "删除操作在生产环境被禁止"
  - action: ESCALATE
    condition:
      method: POST
      path_pattern: "/api/config/*"
    reason: "配置修改需要人工审批"
    escalation:
      channel: slack
      timeout: 300  # 5 分钟后自动降级为 DENY
```

**v1 教训**：v1 的"策略"是硬编码在 Python 字典里的字符串（`"halve_learning_rate"`），不是可配置的规则。v2 的策略必须是**数据（YAML/JSON），不是代码**。

#### L4: 组织层

| 组件 | 说明 |
|------|------|
| 审计报告 | 从 DecisionRecord 生成合规报告（谁在何时做了什么裁决） |
| 合规仪表盘 | Grafana 面板：请求量、拒绝率、升级率、延迟分布 |
| 策略管理 UI | 可视化的策略编辑器（YAML → 表单），非技术人员可操作 |

**v1 教训**：v1 的"可观测性"是 `get_state()` 返回一个字典。v2 的可观测性必须是**实时指标 + 持久化日志 + 可视化**。

---

## 第三章：v1 → v2 模块映射

### 3.1 可保留的概念（重新实现，不移植代码）

| v1 模块 | v1 实现 | v2 保留的概念 | v2 实现方式 |
|---------|---------|---------------|-------------|
| GodelianBoundary | 关键词正则匹配 | "自指命题可能导致不安全行为"这个想法本身 | 在策略层设置规则：检测 Agent 对自身代码/配置的修改请求 → 自动 ESCALATE |
| FixedPointDetector | `abs(x-y) < epsilon` | "行为收敛不等于找到最优解"这个想法 | 在决策层增加滑动窗口分析：连续 N 次相同 Action → 标记为 `PATTERN_STUCK` → 发告警 |
| MetaCognitiveLoop | 玩具算式 | "Agent 需要知道自己的局限"这个想法 | 在决策层增加 `CapabilityCheck`：跨过策略定义的能力边界时 → 注入 "你确定吗？" 元提示到响应头 |
| SelfCheck | `len(desc) < 3` | "系统需要自我验证"这个想法 | 在数据层增加 `HealthCheck`：定时验证日志完整性、签名有效性、策略一致性 |
| AgentInterface | ABC 继承 | "标准化的 Agent 行为描述" | 在 L3 策略层用 YAML schema 描述 Agent 能力，而非 Python 继承 |

### 3.2 直接抛弃（无保留价值）

| v1 模块 | 为什么抛弃 |
|---------|-----------|
| test_*.py (全部 530 个) | dataclass 赋值验证，等同于无测试 |
| adp_taxonomy.py | 学术分类法无工程价值 |
| applicability.py | "适用性门"的阈值判定无实际用途 |
| database_governance.py | 纯 dataclass 包装，无数据库交互 |

### 3.3 保留并改进（少量代码可移植）

| v1 模块 | 保留部分 | 改进方向 |
|---------|----------|----------|
| code_hole_detector.py | AST 扫描逻辑可用 | 从 lint 工具升级为 CI 门禁 |
| github_guardian.py | Issue/PR 健康扫描逻辑 | 从静态分析升级为事件驱动 |

---

## 第四章：第一个模块 — HTTP 拦截网关

### 4.1 模块规格

```
模块名: governance-gateway
语言: Python 3.10+
框架: aiohttp (异步 HTTP) / grpcio (gRPC)
端口: 9000 (默认，可配置)
协议: HTTP/1.1 + gRPC (首版支持 HTTP)
```

### 4.2 API 规范

```
POST /v1/intercept
  - 请求体: 原始 Agent 请求的完整副本（method, path, headers, body）
  - 响应: ALLOW(200, 转发) / DENY(403) / ESCALATE(202, 挂起)
  - 超时: 500ms（超时自动 ALLOW）

GET /v1/health
  - 返回: {"status": "ok", "uptime": 3600, "decisions": 1423}

GET /v1/decisions?from=2026-08-01T00:00:00Z&to=2026-08-02T00:00:00Z
  - 返回: 决策记录列表（分页）
```

### 4.3 数据流

```
                Agent Client                    agent-governance-v2                  Actual Agent
                    │                                    │                                │
                    │  POST /api/chat                    │                                │
                    │  {"message": "delete user 42"}     │                                │
                    │ ─────────────────────────────────→ │                                │
                    │                                    │                                │
                    │                                    │  1. Parse request              │
                    │                                    │  2. Match policies             │
                    │                                    │     → block_delete matched     │
                    │                                    │  3. Verdict: DENY             │
                    │                                    │  4. Log decision               │
                    │                                    │                                │
                    │  403 Forbidden                     │                                │
                    │  {"reason": "block-delete-..."}    │                                │
                    │ ←───────────────────────────────── │                                │
```

### 4.4 第一个 PR 的验收标准

- [ ] `POST /v1/intercept` 返回 `ALLOW` 当无匹配策略时
- [ ] `POST /v1/intercept` 返回 `DENY` 当匹配禁止策略时
- [ ] `POST /v1/intercept` 返回 `ESCALATE` 当匹配升级策略时
- [ ] 超时 500ms 后自动 `ALLOW`（不阻塞 Agent）
- [ ] 所有决策写入 SQLite（可查询、不可篡改）
- [ ] `GET /v1/health` 返回运行状态
- [ ] 测试：包含真实的 HTTP 请求/响应（非 dataclass 赋值）
- [ ] 测试：包含超时场景
- [ ] 测试：包含并发场景（≥10 并发请求）

---

## 附录 A：架构决策记录 (ADR)

### ADR-001: 为什么选 Sidecar 而非 SDK

| 选项 | 优点 | 缺点 | 决定 |
|------|------|------|:--:|
| SDK (v1 方式) | 集成简单 | Agent 代码必须修改；框架升级需重新部署 Agent | ❌ |
| Sidecar (v2 方式) | Agent 零修改；独立升级；崩溃不传染 | 增加网络延迟 | ✅ |
| WASM 插件 | 性能最优 | 生态不成熟；调试困难 | 🔮 未来 |

### ADR-002: 为什么选 aiohttp 而非 FastAPI

| 选项 | 优点 | 缺点 | 决定 |
|------|------|------|:--:|
| FastAPI | 自动 OpenAPI、Type Hints | 依赖重（Starlette+Pydantic）；拦截代理不需要这些 | ❌ |
| aiohttp | 轻量（~2MB）；原生异步；适合代理场景 | 无自动文档 | ✅ |

### ADR-003: 为什么选 SQLite 而非 PostgreSQL（首版）

| 选项 | 优点 | 缺点 | 决定 |
|------|------|------|:--:|
| SQLite | 零配置；单文件；适合单机 Sidecar | 不适合多副本 | ✅ (v2.0) |
| PostgreSQL | 集群友好；强一致 | 需要独立部署 | 🔮 (v2.1+) |

---

## 附录 B：v2 与 v1 的关键差异总结

| 维度 | v1.7.0-PoC | v2.0 |
|------|------------|------|
| 侵入性 | ABC 继承 | Sidecar 代理（零修改） |
| 策略定义 | 硬编码 Python 字典 | YAML 配置文件 |
| 决策引擎 | if-else + regex | 策略匹配树 + 优先级 |
| 持久化 | 内存字典 | SQLite / PostgreSQL |
| 可观测性 | `get_state()` 字典 | Prometheus 指标 + Grafana |
| 人工审批 | 无 | Webhook 推送 + 回调 |
| 超时/熔断 | 无 | 500ms 超时 + 连续失败熔断 |
| 测试 | dataclass 赋值验证 | 真实 HTTP/gRPC 请求 |
| 诚实度 | 学术名词堆砌 | 每个宣称有代码证据 |

---

*本文档随 agent-governance v2 的每次架构变更更新。最后更新：2026-08-02。*
