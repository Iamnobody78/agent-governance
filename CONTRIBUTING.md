# Contributing to Agent Governance Framework

## Development Setup

```bash
git clone https://github.com/your-org/agent-governance.git
cd agent-governance
pip install -e ".[dev]"
```

## Pull Request Checklist

- [ ] Code passes `ruff check .` (zero errors)
- [ ] Tests added/updated (`pytest tests/`)
- [ ] Documentation updated (relevant `.md` files)
- [ ] Interface compatibility verified (`python scripts/validate_interfaces.py`)
- [ ] CHANGELOG updated (under `[Unreleased]`)

## Working with the AI Agent Team

This project is primarily maintained by an AI Agent team (see [AGENTS.md](.github/AGENTS.md)).

### When you submit an Issue:
1. Agent responds within 24h with classification and priority
2. If Agent can fix independently, it submits a PR and tags you as reviewer
3. If human input is needed, Agent marks `needs-human-review`

### When you submit a PR:
1. Agent runs CI, tests, interface validation automatically
2. Agent performs code style and architecture consistency review
3. On pass, Agent marks `ready-for-merge`
4. Human maintainer confirms and merges

## Code of Conduct

Be respectful. Be constructive. See CODE_OF_CONDUCT.md.

## Questions?

Open a [Discussion](https://github.com/your-org/agent-governance/discussions).
