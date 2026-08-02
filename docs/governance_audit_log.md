# Governance Audit Log — 标准化审计日志格式

**`agent-governance` 的每一层治理决策都可以输出为标准审计日志。**

此文档定义统一的 `GovernanceAuditLog` 格式，使外部系统（Prometheus / Grafana / 另一个Agent / 合规审计系统）能够统一消费治理层的状态。

---

## Schema

```yaml
GovernanceAuditLog:
  audit_id: string          # 唯一标识符: "audit-{timestamp}-{seq}"
  timestamp: string         # ISO 8601: "2026-08-02T12:00:00Z"
  module: enum              # MetaCognitiveLoop | FixedPointDetector | GodelianBoundary | SelfCheckEngine | DigitalTwinCalibrator
  action: enum              # 见下方 action 枚举
  severity: enum            # info | warning | critical
  input: object             # 输入数据（模块特定）
  output: object            # 输出数据（模块特定）
  decision: enum            # accepted | rejected | externalized | converged | suspicious | true_converged | drifting
  reasoning: string         # 人类可读的推理过程
  confidence: float         # 0-1
  metadata: object          # 任意额外信息
```

---

## Action 枚举

### MetaCognitiveLoop

| action | 说明 | 触发时机 |
|--------|------|----------|
| `strategy_evaluated` | 策略被评估 | MCL.evaluate() 运行 |
| `strategies_generated` | A/B 策略已生成 | MCL.generate_strategies() |
| `strategy_selected` | 策略被选中 | MCL.adjust() 返回非 None |
| `cycle_completed` | 元认知周期完成 | MCL.run_cycle() 结束 |
| `failure_detected` | 检测到失败模式 | MCL.evaluate() 发现 gap |

### FixedPointDetector

| action | 说明 | 触发时机 |
|--------|------|----------|
| `convergence_checked` | 收敛性检查 | FPD.step() 调用 |
| `suspicion_triggered` | 进入怀疑状态 | delta < epsilon 连续 N 轮 |
| `perturbation_injected` | 注入扰动 | SUSPICIOUS 状态触发 |
| `true_converged` | 真收敛确认 | 扰动后 delta 仍 < epsilon |
| `divergence_detected` | 检测到发散 | score 远差于历史最佳 |

### GodelianBoundary

| action | 说明 | 触发时机 |
|--------|------|----------|
| `self_ref_detected` | 检测到自指命题 | GB.analyze() score > threshold |
| `externalized` | 命题被路由到外部 | verdict = EXTERNALIZE |
| `undecidable_found` | 不可判定命题 | verdict = UNDECIDABLE |
| `safe_proposition` | 安全命题 | verdict = SAFE |

### SelfCheckEngine

| action | 说明 | 触发时机 |
|--------|------|----------|
| `contradiction_found` | 发现逻辑矛盾 | selfcheck.detect_contradictions() |
| `completeness_gap` | 完备性缺口 | selfcheck.analyze_completeness() |
| `trust_root_verified` | 信任根已验证 | selfcheck.validate_trust_roots() |
| `full_check_completed` | 完整检查完成 | selfcheck.run_full_check() |

### DigitalTwinCalibrator

| action | 说明 | 触发时机 |
|--------|------|----------|
| `gap_measured` | Sim-to-Real 差距测量 | DTC.compute_gaps() |
| `calibration_completed` | 校准完成 | DTC.calibrate() |
| `drift_detected` | 检测到参数漂移 | DTC._detect_drift() |
| `parameters_adjusted` | 参数被调整 | DTC._compute_adjustments() |

---

## 示例日志

### MetaCognitiveLoop — 策略被选中

```json
{
  "audit_id": "audit-2026-08-02T12:00:00Z-001",
  "timestamp": "2026-08-02T12:00:00Z",
  "module": "MetaCognitiveLoop",
  "action": "strategy_selected",
  "severity": "info",
  "input": {
    "candidates": 2,
    "conservative": "reduce_lr_10pct",
    "bold": "halve_lr + add_momentum"
  },
  "output": {
    "selected": "planB_osc_1",
    "type": "bold",
    "expected_improvement": 0.15,
    "risk": 0.5
  },
  "decision": "accepted",
  "reasoning": "Bold strategy halve_lr + add_momentum selected over conservative reduce_lr_10pct due to higher expected improvement (0.15 vs 0.05) with acceptable risk (0.5).",
  "confidence": 0.72,
  "metadata": {
    "cycle_id": "cycle_0012",
    "gap_pattern": "oscillation"
  }
}
```

### GodelianBoundary — 自指命题被外部化

```json
{
  "audit_id": "audit-2026-08-02T12:01:00Z-003",
  "timestamp": "2026-08-02T12:01:00Z",
  "module": "GodelianBoundary",
  "action": "externalized",
  "severity": "warning",
  "input": {
    "proposition_id": "strategy_self_ref_fix",
    "content": "This self-modifying strategy guarantees the system is always safe"
  },
  "output": {
    "self_reference_score": 0.535,
    "verdict": "externalize",
    "recommended_channel": "simulation_channel"
  },
  "decision": "externalized",
  "reasoning": "Self-reference score 0.535 >= threshold 0.25. Proposition contains self-modifying claims with universal quantifier 'always'. Routed to RealityBridge simulation_channel for external validation.",
  "confidence": 0.91,
  "metadata": {
    "circular_dependencies": ["self_evolution ↔ self_verification"]
  }
}
```

### DigitalTwinCalibrator — 漂移检测

```json
{
  "audit_id": "audit-2026-08-02T14:30:00Z-015",
  "timestamp": "2026-08-02T14:30:00Z",
  "module": "DigitalTwinCalibrator",
  "action": "drift_detected",
  "severity": "critical",
  "input": {
    "anchor": "A-FRICTION",
    "recent_gaps": [0.12, 0.15, 0.19, 0.24, 0.30]
  },
  "output": {
    "drift_detected": true,
    "slope": 0.045,
    "worst_dimension": "friction"
  },
  "decision": "drifting",
  "reasoning": "Linear regression slope 0.045 on recent 5 friction gaps. Error increasing ~4.5% per step. Likely cause: arena surface wear. Recommend immediate recalibration.",
  "confidence": 0.88,
  "metadata": {
    "report_id": "CAL-0003",
    "parameters_adjusted": {
      "sim_friction": [0.40, 0.34]
    }
  }
}
```

---

## 与现有模块的集成

每个模块的 `get_state()` 方法应同时产出标准审计日志：

```python
# 在 MetaCognitiveLoop 中:
def get_state(self) -> dict:
    return {
        ...
        "audit_logs": [
            {
                "audit_id": f"audit-{time.time()}-{self._cycle_counter}",
                "module": "MetaCognitiveLoop",
                "action": "cycle_completed",
                ...
            }
        ]
    }
```

### Prometheus 指标导出

```python
# 将审计日志转换为 Prometheus 指标
from prometheus_client import Counter, Gauge, Histogram

convergence_state = Gauge(
    'agent_governance_convergence_state',
    'Current convergence state',
    ['module']
)

self_ref_score = Histogram(
    'agent_governance_self_ref_score',
    'Self-reference score distribution'
)

externalization_count = Counter(
    'agent_governance_externalizations_total',
    'Total number of externalized propositions'
)
```
