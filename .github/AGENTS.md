# Agent Maintenance Charter

This project is maintained by an AI Agent team under the following charter:

## 1. Autonomy
Agent team has authority for all routine maintenance without human intervention:
- Bug fixes (non-architectural)
- Documentation updates
- Version releases
- CI/CD configuration adjustments

## 2. Boundaries
Agent team MUST NOT perform the following without human approval:
- Modify `interfaces/agent_interface.yaml` (API changes)
- Modify `governance/core/constitution.yaml` (governance constitution)
- Delete `LICENSE` or `CONTRIBUTING.md`
- Convert the project to private

## 3. Transparency
All Agent team operations must be recorded in:
- GitHub Actions logs
- CHANGELOG.md
- `.agent_state/entropy.log` (internal)

## 4. Human Takeover
If Agent team fails to resolve the same issue 3 consecutive times,
mark `needs-human-review` and notify human maintainers.

## 5. Self-Evolution
Agent team may autonomously update its own maintenance scripts
(`scripts/` directory) provided all tests pass.
