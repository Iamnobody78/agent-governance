# Discussion: Welcome! What brought you to agent-governance?

**Category**: General / Welcome

---

Hi everyone! 👋

Welcome to the **agent-governance** community. This is a MIT-licensed open-source framework that gives any AI agent the ability to think about its own decisions, verify its own safety, and evolve without losing control.

## What agent-governance provides

- **MetaCognitiveLoop**: Monitor → Evaluate → Generate → Adjust → Verify — a complete self-improvement cycle
- **GodelianBoundary**: Detects self-referential paradoxes and routes dangerous decisions to external verification
- **FixedPointDetector**: Detects and breaks infinite loops before they happen
- **TaG Hooks (NEW!)**: 9 pre-execution safety hooks — credential leak detection, deployment gates, self-modification guard, and more
- **368 tests**, all passing

## We'd love to hear from you

1. **What brought you here?** What problem are you trying to solve?
2. **What kind of agent are you building?** Chat agent? Robotics? Data pipeline?
3. **What would make this project useful to you?** Missing features? Documentation gaps?

## Getting started

```bash
pip install -e .
python examples/chat_agent_with_governance.py
```

Looking forward to building this together! 🚀
