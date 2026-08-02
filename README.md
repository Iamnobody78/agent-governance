# Agent Governance Framework

**A domain-agnostic AI Agent governance paradigm. Let any Agent be trusted, evolve, collaborate, and have boundaries.**

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)

## What is this?

Agent Governance Framework is a **portable governance layer** that solves "Agents are untrustworthy, cannot evolve, and cannot collaborate" — the three core problems of AI Agent systems.

It is domain-agnostic (not tied to robots, software, or data analysis). Any Agent that implements **4 interface methods** gains:

| Capability | Description |
|:---|:---|
| **5-tier decision spectrum** | Hard logic -> Fuzzy -> Statistical -> Deep -> LLM, covering full-spectrum decisions |
| **Shadow loop self-evolution** | Learn from failures, auto-optimize rules |
| **Safety guardrails** | Injection detection, trust scoring, capability boundaries, rate limiting |
| **Hallucination protection** | Risk pre-check, consistency verification, traceability, cognitive boundaries |
| **Social layer** | Reputation system, task market, arbitration court, cultural evolution |
| **Meta-scheduler** | Coordinate 6 meta-layers, let governance self-govern |
| **Auto-deploy closed-loop** | Train -> Export -> Flash -> Verify automation |
| **ABDL rule language** | Unified rule definition (L0-L3 priority levels) |
| **42-layer meta-audit** | Continuous health monitoring across all layers |
| **Self-evolution engine** | Audit -> Diagnose -> Generate Fix -> Validate -> Deploy |

## Quick Start

### 1. Clone

```bash
git clone https://github.com/your-org/agent-governance.git
cd agent-governance
```

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Implement Your Agent

```python
from governance.core import AgentInterface

class MyAgent(AgentInterface):
    def observe(self):
        return {"state": [...], "timestamp": time.time(), "confidence": 0.9}

    def act(self, action):
        return {"status": "ok", "reward": 1.0, "done": False, "info": {}}

    def get_metrics(self):
        return {"success_rate": 0.92, "latency": 0.01, "resource_usage": 0.3}

    def get_capabilities(self):
        return ["rl_training", "simulation"]
```

### 4. Connect to Governance

```bash
python scripts/register_agent.py --agent my_agent.py
```

### 5. Launch Governance

```bash
./scripts/deploy_governance.sh
```

## Documentation

| Document | Description |
|:---|:---|
| [Architecture Overview](docs/architecture_overview.md) | System architecture |
| [Integration Guide](docs/integration_guide.md) | How to integrate a new Agent |
| [ABDL Language](docs/abdl_reference.md) | Agent Behavior Description Language |
| [Example: BottleSumo](examples/bottlesumo/) | Reference implementation |

## Architecture

```
agent-governance/
├── governance/          # Governance layer core
│   ├── core/            # Core interfaces and engines
│   ├── meta/            # Meta-audit, meta-scheduler, meta-language
│   ├── security/        # Guardrails, injection detection, trust scoring
│   └── evolution/       # Self-evolution closed-loop engine
├── core/                # Common utilities
├── agent_factory/       # Agent templates
├── interfaces/          # Integration specifications
├── examples/            # Reference implementations
├── scripts/             # Utility scripts
├── docs/                # Documentation
└── config/              # Configuration
```

## Maintenance Mode: Agent-First

This project is maintained by an **AI Agent team**. Human maintainers only make strategic decisions, not daily operations.

| Role | Responsibility |
|:---|:---|
| **AI Agent Team** | Code review, testing, docs, releases, Issue triage, PR validation |
| **Human Maintainers** | Strategic direction, major change approval, complex issue resolution |

See [.github/AGENTS.md](.github/AGENTS.md) for the Agent maintenance charter.

## License

MIT — see [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions reviewed by the AI Agent team.
