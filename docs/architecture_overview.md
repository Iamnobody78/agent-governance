# Architecture Overview

## System Layers

```
┌─────────────────────────────────────────────┐
│           Agent Applications                 │
│  (BottleSumo, Code Writer, Data Analyzer)    │
├─────────────────────────────────────────────┤
│         Agent Governance Framework           │
│  ┌─────────────────────────────────────┐    │
│  │       Meta-Scheduler (L6)           │    │
│  │   Coordinates 6 meta-layers         │    │
│  ├───────────┬───────────┬─────────────┤    │
│  │  Safety   │ Evolution │ Social      │    │
│  │  Guard    │ Shadow   │ Reputation  │    │
│  │  Rails    │ Loop     │ System      │    │
│  ├───────────┼───────────┼─────────────┤    │
│  │  Halluci- │ ABDL     │ Meta-Audit  │    │
│  │  nation   │ Rule     │ 42-Layer    │    │
│  │  Guard    │ Engine   │ Health      │    │
│  ├───────────┴───────────┴─────────────┤    │
│  │     5-Tier Decision Spectrum         │    │
│  │  Hard → Fuzzy → Statistical → Deep   │    │
│  │            → LLM Reasoning            │    │
│  └─────────────────────────────────────┘    │
├─────────────────────────────────────────────┤
│             Agent Interface                  │
│      observe() | act() | get_metrics()      │
│             get_capabilities()              │
├─────────────────────────────────────────────┤
│          Agent Implementation                │
│   (User's domain-specific agent code)        │
└─────────────────────────────────────────────┘
```

## Key Components

### 1. Meta-Scheduler (L6)
The highest governance layer. Coordinates 6 sub-layers (Safety, Evolution, Social, Hallucination Guard, ABDL Engine, Meta-Audit) through a priority queue with non-blocking per-layer locks.

### 2. ABDL Rule Engine
Agent Behavior Description Language — a unified rule language with 4 priority levels:
- **L0**: Immutable axioms (safety, reversibility, budget)
- **L1**: Constitutional rules (routing, heartbeat, session)
- **L2**: Operational rules (audit schedule, security scan, edge avoidance)
- **L3**: Heuristic rules (speed adapt, defense, exploration)

### 3. Shadow Loop Self-Evolution
Continuous improvement cycle:
```
Audit → Diagnose → Generate Fix → Validate in Closed-Loop → Deploy if improved
```

### 4. 42-Layer Meta-Audit
Continuous health monitoring across 42 meta-capability layers (P0-P5). Each layer outputs `health_score`, `alerts`, and `recommendations`.

### 5. Safety Guardrails
- Injection detection
- Trust scoring (decaying confidence)
- Capability boundary enforcement
- Rate limiting

## Integration Pattern

Any Agent implements 4 methods on `AgentInterface` and registers:
```python
python scripts/register_agent.py --agent my_agent.py
```

The governance layer then wraps the agent, providing all capabilities transparently.
