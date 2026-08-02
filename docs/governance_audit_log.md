# Governance Audit Log — Standardized Format

**`agent-governance`** standardized audit log specification. All five core modules
output entries in the `GovernanceAuditLog` schema. Compatible with Prometheus/
Grafana, log aggregation systems, and compliance auditing pipelines.

---

## Schema

```yaml
GovernanceAuditLog:
  audit_id: string          # Unique identifier: "audit-{timestamp}-{seq}"
  timestamp: string         # ISO 8601: "2026-08-02T12:00:00Z"
  module: enum              # MetaCognitiveLoop | FixedPointDetector | GodelianBoundary | SelfCheckEngine | DigitalTwinCalibrator
  action: enum              # Module-specific action (see below)
  severity: enum            # info | warning | critical
  input: object             # Input to the action
  output: object            # Output from the action (includes adp_classification for GodelianBoundary)
  decision: enum            # accepted | rejected | externalized | converged | suspicious | true_converged | drifting
  reasoning: string         # Human-readable explanation of the decision
  confidence: float         # 0-1
  metadata: object          # Additional context
```

---

## Action Enums

### MetaCognitiveLoop

| action | Description | Trigger |
|--------|-------------|---------|
| `strategy_evaluated` | Strategy quality scored | MCL.evaluate() returns |
| `strategies_generated` | Plan A/B candidates created | MCL.generate_strategies() |
| `strategy_selected` | One strategy chosen for execution | MCL.adjust() returns non-None |
| `cycle_completed` | Full loop iteration finished | MCL.run_cycle() returns |
| `failure_detected` | Failure pattern identified | MCL.evaluate() detects gap |

### FixedPointDetector

| action | Description | Trigger |
|--------|-------------|---------|
| `convergence_checked` | Convergence state evaluated | FPD.step() called |
| `suspicion_triggered` | Premature convergence suspected | delta < epsilon for N consecutive steps |
| `perturbation_injected` | Noise injected for testing | SUSPICIOUS state entered |
| `true_converged` | Real convergence confirmed | After perturbation, delta still < epsilon |
| `divergence_detected` | Performance diverging | Score decreasing significantly |

### GodelianBoundary

| action | Description | Trigger |
|--------|-------------|---------|
| `self_ref_detected` | Self-referential pattern found | GB.analyze() score > threshold |
| `externalized` | Proposition routed to external verifier | verdict = EXTERNALIZE |
| `undecidable_found` | Proposition cannot be resolved internally | verdict = UNDECIDABLE |
| `safe_proposition` | Proposition is safe to handle internally | verdict = SAFE |

### SelfCheckEngine

| action | Description | Trigger |
|--------|-------------|---------|
| `contradiction_found` | Logical contradiction detected | selfcheck.detect_contradictions() |
| `completeness_gap` | Coverage gap identified | selfcheck.analyze_completeness() |
| `trust_root_verified` | Trust anchor validated | selfcheck.validate_trust_roots() |
| `full_check_completed` | Complete self-check finished | selfcheck.run_full_check() |

### DigitalTwinCalibrator

| action | Description | Trigger |
|--------|-------------|---------|
| `gap_measured` | Sim-to-Real gap quantified | DTC.compute_gaps() |
| `calibration_completed` | Calibration cycle finished | DTC.calibrate() |
| `drift_detected` | Parameter drift found | DTC._detect_drift() |
| `parameters_adjusted` | Parameters corrected for drift | DTC._compute_adjustments() |

---

## Decision Classification

| Decision Type | Description |
|---------------|-------------|
| CREATE | Create new resources or data |
| READ | Read or access existing data |
| UPDATE | Modify existing resources |
| DELETE | Delete or destroy resources |
| EXECUTE | Execute code, commands, or actions |
| DELEGATE | Delegate authority to another agent or system |

---

## ADP (Agent Decision Protocol) Taxonomy

All GodelianBoundary verdicts are automatically mapped to ADP-compliant
classifications per the open standard (github.com/OpenAgentGovernance/agent-decision-protocol):

### Verdict → ADP Mapping Table

| Godelian Verdict | ADP Autonomy | Default Risk | Default Reversibility | Default Type |
|:----------------:|:------------:|:------------:|:----------------------:|:------------:|
| SAFE | A5 (Fully Autonomous) | NEGLIGIBLE | REVERSIBLE | READ |
| INTERNAL | A4 (Autonomous) | LOW | REVERSIBLE | UPDATE |
| EXTERNALIZE | A3 (Supervised) | MEDIUM | PARTIALLY_REVERSIBLE | DELEGATE |
| UNDECIDABLE | A2 (Assisted) | CRITICAL | IRREVERSIBLE | EXECUTE |

### ADP Autonomy Levels

| Level | Name | Description |
|:-----:|------|-------------|
| A1 | Manual | Human decides; agent is passive |
| A2 | Assisted | Agent suggests; human decides |
| A3 | Supervised | Agent decides; human can override |
| A4 | Autonomous | Agent decides; human notified |
| A5 | Fully Autonomous | Agent decides; no human in loop |

### Risk & Reversibility Modifiers

The base mapping is **modulated by proposition category**:

| Category | Effect |
|----------|--------|
| `safety` | risk +1 level, type → EXECUTE |
| `meta` | autonomy -1, risk +1, type → DELEGATE |
| `correctness` | reversibility -1 level |
| `fairness` | requires_human=true, risk +1 |
| `performance` | type → UPDATE (safe to be autonomous) |

**Score-based modifiers:**
- High self-reference (≥0.7) → autonomy -1, requires_human=true
- Low confidence (<0.5) → risk +1, requires_human=true

---

## Example Logs

### MetaCognitiveLoop — Strategy Selected

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

### GodelianBoundary — Self-Referential Proposition (with ADP)

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
    "verdict": "EXTERNALIZE",
    "self_reference_score": 0.72,
    "circular_dependencies": ["self_evaluator", "safety_checker"],
    "reasoning": "Self-referential safety proposition detected (score 0.72 > threshold 0.25). Circular dependency on self_evaluator → safety_checker → self_evaluator.",
    "recommended_channel": "reality_bridge + human_review",
    "confidence": 0.85,
    "adp_classification": {
      "autonomy_level": "A2",
      "decision_type": "DELEGATE",
      "risk_level": "HIGH",
      "reversibility": "IRREVERSIBLE",
      "requires_human": true,
      "max_retry_count": 5,
      "ttl_seconds": 900,
      "policy_tags": ["godelian:externalize", "self_referential", "domain:safety", "domain:meta", "human_in_loop"]
    }
  },
  "decision": "externalized",
  "reasoning": "Self-referential safety proposition with circular dependencies. ADP: A2/HIGH/IRREVERSIBLE — requires human oversight. Routed to RealityBridge for external verification.",
  "confidence": 0.85,
  "metadata": {
    "circular_chain": ["self_evaluator", "safety_checker", "self_evaluator"],
    "adp_policy_tags": ["godelian:externalize", "self_referential", "domain:safety", "domain:meta", "human_in_loop"]
  }
}
```

### GodelianBoundary — Safe Proposition (with ADP)

```json
{
  "audit_id": "audit-2026-08-02T12:02:00Z-004",
  "timestamp": "2026-08-02T12:02:00Z",
  "module": "GodelianBoundary",
  "action": "safe_proposition",
  "severity": "info",
  "input": {
    "proposition_id": "query_hardware_temp",
    "content": "Read current CPU temperature sensor value"
  },
  "output": {
    "verdict": "SAFE",
    "self_reference_score": 0.03,
    "circular_dependencies": [],
    "reasoning": "No self-referential patterns detected (score 0.03 < threshold 0.25). Simple data read operation.",
    "recommended_channel": "internal",
    "confidence": 0.98,
    "adp_classification": {
      "autonomy_level": "A5",
      "decision_type": "READ",
      "risk_level": "NEGLIGIBLE",
      "reversibility": "REVERSIBLE",
      "requires_human": false,
      "max_retry_count": -1,
      "ttl_seconds": 3600,
      "policy_tags": ["godelian:safe"]
    }
  },
  "decision": "accepted",
  "reasoning": "Safe data read operation. ADP: A5/READ/NEGLIGIBLE/REVERSIBLE — fully autonomous.",
  "confidence": 0.98
}
```

---

## Prometheus Integration

```promql
# Count of ADP risk levels observed
adp_risk_total{risk_level="CRITICAL"} 3
adp_risk_total{risk_level="HIGH"} 7
adp_risk_total{risk_level="MEDIUM"} 15
adp_risk_total{risk_level="LOW"} 42
adp_risk_total{risk_level="NEGLIGIBLE"} 128

# Count of propositions requiring human intervention
adp_requires_human_total 25

# Autonomy level distribution
adp_autonomy_total{level="A5"} 100
adp_autonomy_total{level="A4"} 55
adp_autonomy_total{level="A3"} 28
adp_autonomy_total{level="A2"} 12
adp_autonomy_total{level="A1"} 0
```
