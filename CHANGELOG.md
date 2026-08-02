# Changelog

All notable changes to agent-governance will be documented in this file.


## [1.7.0] - 2026-08-01

### Phase 1: Layer 3 Standardization (6 new modules, 125 tests, 551 total)

#### Governance Benchmarks
- VeritasRunner (veritas_runner.py) - 4-dimension governability assessment
- HummblRunner (hummbl_runner.py) - 7 safety primitives, 29 test cases
- WardenRunner (warden_runner.py) - 12-layer posture scanner, A+-F grade

#### Telemetry + Protocols
- GovernanceTelemetry (otel_exporter.py) - OTel + GAAT GTS events
- A2AAdapter (a2a_adapter.py) - A2A protocol message encoding

#### Operations
- GitHubGuardian (github_guardian.py) - Daily health scanner, 0-100 scoring
- guardian-daily-scan.yml - Automated CI/CD health workflow

## [1.5.0] — 2026-08-01

### 🧠 Core Modules (5 new)
- **FixedPointDetector** (`governance/meta/fixed_point_detector.py`, 345 LOC) — Detects convergence, oscillation, divergence, and plateau states. Introduces SUSPICIOUS state with perturbation injection (ε-greedy boost + sensor noise) and annealing decay γ=0.95. State machine: SUSPICIOUS → TRUE_CONVERGED/BACK_TO_CONVERGING.
- **GodelianBoundary** (`governance/meta/godelian_boundary.py`, 340 LOC) — Detects self-referential paradoxes via weighted pattern matching (6 patterns, weights 0.6-1.2). Routes undecidable propositions to external reality bridges. Verdicts: SAFE, INTERNAL, EXTERNALIZE, UNDECIDABLE.
- **MetaCognitiveLoop** (`governance/meta/meta_cognitive_loop.py`, 507 LOC) — Full Monitor→Evaluate→Generate→Adjust→Verify cycle. Dual-track strategy generation (Plan A conservative + Plan B bold). Failure pattern detection: reward_hacking, oscillation, mode_collapse, slow_convergence. Integrated with FPD and GB.
- **SelfCheckEngine** (`governance/meta/self_check_engine.py`, 415 LOC) — Three-layer self-verification: ContradictionDetection (5 static templates + dynamic), CompletenessAnalysis (6 domains), TrustRootManagement (7 default anchors).
- **DigitalTwinCalibrator** (`governance/meta/digital_twin_calibrator.py`, 415 LOC) — Sim-to-Real gap quantification. 10 GapDimensions, RealityAnchor with tolerance tracking, linear regression slope-based drift detection, RMSE-based calibration scoring.

### ⚙️ Configuration & Infrastructure
- **ConfigLoader** (`governance/meta/config_loader.py`, 297 LOC) — Lightweight YAML parser (no pyyaml dependency), env var overrides (META_FPD_EPSILON etc.), FPDConfig/GBConfig/MCLConfig/MetaConfig dataclasses.
- **meta_modules_config.yaml** (46 lines) — Centralized configuration with anti-premature-convergence parameters.

### ✅ Testing (284 tests, 0 errors)
- `test_fixed_point.py` (279 LOC, 42 tests): Serialization, convergence states, EvolutionConvergenceGuard, edge cases.
- `test_godelian.py` (324 LOC, 43 tests): Propositions, verdicts, circular deps, batch processing, RealityBridgeRouter.
- `test_metacognitive.py` (442 LOC, 49 tests): Full cycle, failure patterns, strategy A/B, SelfCheckBenchmark.
- `test_integration_meta_modules.py` (708 LOC, 23 tests): 10 integration scenarios (INT-001 through INT-010).
- `test_self_check.py` (526 LOC, 50 tests): Contradiction detection, completeness analysis, trust root management.
- `test_digital_twin.py` (405 LOC, 44 tests): Calibration pipeline, drift detection, anchor management.
- `test_applicability.py` — Fixed classifier test (seeded + two-stage training).

### 📚 Documentation
- **README.md** (172 lines) — Complete rewrite: "为什么需要" (4 problems), comparison vs LangChain/AutoGen/CrewAI, ecosystem integration, quickstart, module table, academic citations.
- **DEMO** (`examples/chat_agent_with_governance.py`, 260 LOC) — GovernedChatAgent with 6 scenarios, GB pre-check, MCL cycle, SelfCheck, dashboard.
- **ECOSYSTEM** (`docs/ecosystem_integration.md`, 299 LOC) — Integration guides for LangChain, AutoGen, CrewAI, custom agents.
- **ROADMAP.md** (98 lines) — v1.0→v1.5→v2.0→v3.0.
- **governance_boundaries.md** (77 lines) — "能治理" / "不能治理" / "需要人类介入" matrices.
- **governance_stories.md** (137 lines) — 4 narrative stories.
- **governance_audit_log.md** (211 lines) — Full AuditLog schema, action enums, Prometheus integration.
- **UPGRADE_GUIDE.md** (138 lines) — v1.0→v1.5 migration, compatibility matrix.
- **CONTRIBUTING.md** (95 lines) — Contribution types, PR checklist, AI Agent team workflow.

### 🔧 General
- **Ruff lint**: 303→0 errors (15 categories) across entire codebase.
- **Observability**: `get_state()` added to all 5 core modules + `get_dashboard()` for MetaCognitiveLoop.
- **Anti-premature-convergence**: SUSPICIOUS state, perturbation annealing, A/B dual-track strategies, external dependency decay.
- **pyproject.toml**: Version 1.0.0→1.5.0, Development Status 4→5 (Production/Stable).

---

## [1.0.0] — Initial Release

- Core governance framework skeleton
- Basic CI/CD pipeline (4-stage GitHub Actions)
- pyproject.toml packaging
