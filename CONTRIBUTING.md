# Contributing to Agent Governance Framework

**欢迎！无论你是 AI 研究者、Agent 开发者、还是技术写作爱好者，总有你可以贡献的方式。**

---

## 我能贡献什么？

| 贡献类型 | 适合人群 | 难度 | 入门时间 | 典型产出 |
|----------|----------|:----:|:--------:|----------|
| **Bug 报告** | 所有用户 | 🟢 低 | 5 min | GitHub Issue |
| **文档改进** | 技术写作爱好者 | 🟢 低 | 30 min | PR to docs/ |
| **DEMO 示例** | Agent 开发者 | 🟢 低 | 2 hr | 新的 examples/ 文件 |
| **治理故事** | 产品/UX 思维者 | 🟢 低 | 1 hr | stories/ 新故事 |
| **新框架集成** | 熟悉 LangChain/AutoGen/CrewAI 的开发者 | 🟡 中 | 4-8 hr | 新的集成指南 + 代码 |
| **新模块实现** | 熟悉元认知/治理的开发者 | 🟡 中 | 8-16 hr | 新的 governance/meta/ 模块 |
| **基准测试** | 熟悉评估的开发者 | 🔴 高 | 16-32 hr | 新的 tests/benchmark/ |
| **论文复现** | 学术研究者 | 🔴 高 | 32-64 hr | 复现代码 + 论文笔记 |

### 不确定从哪里开始？

- 查看标记为 `good-first-issue` 的 issue
- 查看 `stories/` 目录，为已有故事添加你自己的版本
- 查看 `docs/` 目录，修正错别字或改进表达

---

## Development Setup

```bash
git clone https://github.com/ivy-ai/agent-governance.git
cd agent-governance
pip install -e ".[dev]"
```

## Pull Request Checklist

- [ ] Code passes `ruff check .` (zero errors)
- [ ] Tests added/updated (`pytest tests/`)
- [ ] Documentation updated (relevant `.md` files)
- [ ] Interface compatibility verified (`python scripts/validate_interfaces.py`)
- [ ] CHANGELOG updated (under `[Unreleased]`)
- [ ] New modules have `get_state()` method for observability

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

---

## Project Structure

```
agent-governance/
├── governance/meta/          # 核心治理模块
│   ├── fixed_point_detector.py
│   ├── godelian_boundary.py
│   ├── meta_cognitive_loop.py
│   ├── self_check_engine.py
│   ├── digital_twin_calibrator.py
│   ├── config_loader.py
│   └── meta_modules_config.yaml
├── governance/core/          # 核心 Agent 接口
├── tests/                    # 测试 (284/284)
├── examples/                 # 演示案例
├── stories/                  # 治理故事
├── docs/                     # 文档
│   ├── ecosystem_integration.md
│   ├── governance_boundaries.md
│   ├── governance_audit_log.md
│   ├── UPGRADE_GUIDE.md
│   └── ROADMAP.md
└── .github/                  # CI/CD + AI Agent 团队配置
```

---

## Code of Conduct

Be respectful. Be constructive. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Questions?

Open a [Discussion](https://github.com/ivy-ai/agent-governance/discussions).
