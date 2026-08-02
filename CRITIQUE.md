# CRITIQUE.md — agent-governance v1.7.0 自我批判

> 这份文档是本项目在 v1.7.0 阶段结束时的自我审查。它不是外部攻击的产物，而是元治理的实践——项目治理自身，包括治理自身的缺陷。

## 一、概念与实现不对齐

### 1.1 "哥德尔边界" (GodelianBoundary)

**宣称**：检测自指命题，作为 Agent 行为的安全边界。

**源码**：`governance/meta/godelian_boundary.py:110-117`

```python
patterns = [
    re.compile(r'\bthis (system|agent|model)\b'),
    re.compile(r'\b(always|never|guarantee)\b'),
]
```

**实际**：6 个关键词正则匹配。零哥德尔编号、零不完备性证明、零自指逻辑。

**修正方向**：要么补真算法，要么改名为"关键词检测器"。

### 1.2 "不动点检测" (FixedPointDetector)

**宣称**：检测 Agent 行为是否收敛到不动点，防止假收敛。

**源码**：`governance/meta/fixed_point_detector.py:32-38`

```python
if abs(current - previous) < epsilon:
    state = ConvergenceState.CONVERGED
```

**实际**：`delta < epsilon` 的阈值比较。零 Banach 压缩映射、零不动点理论。

**修正方向**：要么补真数学，要么改名为"迭代收敛检测"。

### 1.3 "元认知循环" (MetaCognitiveLoop)

**宣称**：监控→评估→生成→调整→验证的元认知闭环。

**源码**：`governance/meta/meta_cognitive_loop.py:L314-318`

```python
if mean_r > 0.8 and action_diversity < 0.3:
    return GapReport(pattern=FailurePattern.REWARD_HACKING, ...)
```

**实际**：算术平均值 + 动作多样性阈值。零行为模式识别、零元认知洞察。

开发者注释自认（L504）：**"模拟扰动测试后的分数（玩具算式）"**

### 1.4 "SelfCheck" — 10 边界场景验证

**源码**：`governance/meta/meta_cognitive_loop.py:L573`

```python
if len(strategy.description) < 3: return False
```

**实际**：检查字符串长度是否小于 3。

**修正方向**：要么补真实场景，要么删除 "10 边界场景" 宣称。

---

## 二、架构与宣传不对齐

### 2.1 "零侵入" (Zero-invasiveness)

**宣称**："实现 4 个接口方法即可"。

**源码**：`governance/core/agent_interface.py:13-68`

```python
class AgentInterface(ABC):
    @abstractmethod
    def observe(self) -> Observation: ...
    @abstractmethod
    def act(self) -> Action: ...
```

**实际**：强制 `import` 并继承 `AgentInterface`，必须实现 4 个抽象方法。这是 ABC 继承，不是 Sidecar/Proxy。

**修正方向**：要么补 HTTP/gRPC 拦截网关，要么删除 "零侵入" 宣称。

---

## 三、测试质量与数量不对齐

### 3.1 530 tests，但全部在测 dataclass

**源码**：典型断言模式

```python
def test_creation(self):
    p = Proposition("p1", "The system is safe")
    assert p.id == "p1"
    assert p.content == "The system is safe"
```

**实际**：测试的是 Python dataclass 字段赋值，不是治理逻辑。

**总执行时间**：37s / 530 tests ≈ 70ms/test — 确认为轻量数据结构断言。

缺失的测试类型：
- 网络连接与协议交互
- 并发与超时处理
- 异常恢复与回退逻辑
- 真实场景下的策略演化
- 外部系统集成

---

## 四、结论

本项目的 v1.7.0 处于 **"概念架构完整，工程实现为 PoC 级别"** 的状态。

| 维度 | 评级 | 说明 |
|------|:--:|------|
| 设计方向 | B+ | 学术思想有参考价值 |
| 工程实现 | D | 代码未对齐宣称 |
| 测试体系 | D | 覆盖数据结构，未覆盖逻辑 |
| 文档诚实性 | F | README 宣传与代码实作严重脱节 |
| 生产可用性 | F | 无超时、无回滚、无熔断、无 Sidecar |

**后续处理**：
- 本仓库已标记为 `v1.7.0-poc`，作为概念验证原型存档
- 新架构将从 `ARCHITECTURE.md` 开始，以本批判为第一章
- 每一步代码提交都必须对齐其宣称

---

*这份批判由本项目的元治理系统自动生成，旨在建立"项目治理自身"的闭环。*
