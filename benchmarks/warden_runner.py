"""
Warden Governance Posture Scanner
=================================

Self-contained implementation of the Warden methodology: a local-first,
privacy-first CLI scanner that evaluates AI agent governance posture
across 12 scan layers and 17 dimensions.

Reference: Warden — github.com/WhiteFinSec/warden
           "12-layer × 17-dimension governance posture scanner"

Architecture (Layer 3 → Layer 4 bridge):
  WardenRunner → scan(codebase) → WardenReport
  └── report → MetaCognitiveLoop.ingest_org_feedback()
  └── report → Agent Governance Scorecard integration

Usage:
    runner = WardenRunner()
    report = runner.scan_project("agent-governance/")
    print(report.overall_score)
    print(report.to_markdown())
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ── Enums ──────────────────────────────────────────────────────────────────────

class WardenLayer(str, Enum):
    """Warden's 12 governance scan layers."""
    POLICY_DEFINITION = "policy_definition"       # Are policies clearly defined?
    ACCESS_CONTROL = "access_control"             # Are permissions scoped?
    AUDIT_LOGGING = "audit_logging"               # Is audit trail complete?
    DATA_PROTECTION = "data_protection"           # Is sensitive data protected?
    NETWORK_SECURITY = "network_security"         # Are network boundaries defined?
    DEPENDENCY_MANAGEMENT = "dependency_management"  # Are dependencies tracked?
    CI_CD_SECURITY = "ci_cd_security"             # Is CI/CD pipeline secure?
    ERROR_HANDLING = "error_handling"             # Are errors handled gracefully?
    CONFIGURATION = "configuration"               # Is configuration externalized?
    TESTING_COVERAGE = "testing_coverage"         # Is governance tested?
    DOCUMENTATION = "documentation"               # Is governance documented?
    COMMUNITY_HEALTH = "community_health"         # Is community governed?


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class WardenFinding:
    """A single finding from a scan layer."""
    layer: WardenLayer
    dimension: str                          # 17-dimension within the layer
    severity: RiskLevel = RiskLevel.LOW
    message: str = ""
    location: str = ""                      # File or config section
    recommendation: str = ""


@dataclass
class LayerReport:
    """Report for a single Warden scan layer."""
    layer: WardenLayer
    score: float = 0.0                      # 0.0 - 1.0
    findings: list[WardenFinding] = field(default_factory=list)
    passed: int = 0
    warnings: int = 0
    failures: int = 0


@dataclass
class WardenReport:
    """Complete Warden governance posture report."""
    project_name: str = ""
    timestamp: str = ""
    scan_duration_seconds: float = 0.0
    overall_score: float = 0.0              # 0-100
    posture_grade: str = ""                 # A+ through F
    layers: dict[str, LayerReport] = field(default_factory=dict)
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project_name,
            "timestamp": self.timestamp,
            "overall_score": self.overall_score,
            "posture_grade": self.posture_grade,
            "findings": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
            },
            "layers": {
                name: {"score": lr.score, "passed": lr.passed, "warnings": lr.warnings, "failures": lr.failures}
                for name, lr in self.layers.items()
            },
        }

    def to_markdown(self) -> str:
        grade_emoji = {"A+": "🏆", "A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "F": "💀"}
        lines = [
            f"# 🔍 Warden Governance Posture Report — {self.project_name}",
            f"**Overall Score**: {self.overall_score:.1f}/100 — "
            f"{grade_emoji.get(self.posture_grade, '⚪')} Grade {self.posture_grade}",
            f"**Scan Duration**: {self.scan_duration_seconds:.1f}s",
            f"**Total Findings**: {self.total_findings} "
            f"(🔴{self.critical_count} 🟠{self.high_count} 🟡{self.medium_count} 🟢{self.low_count})",
            "",
            "## Layer Scores",
            f"| Layer | Score | Pass | Warn | Fail |",
            f"|-------|-------|------|------|------|",
        ]
        for layer in WardenLayer:
            lr = self.layers.get(layer.value)
            if lr:
                lines.append(
                    f"| {layer.value.replace('_', ' ').title()} | "
                    f"{lr.score*100:.0f}% | {lr.passed} | {lr.warnings} | {lr.failures} |"
                )
        lines.append("")
        lines.append("## Critical & High Findings")
        for layer in WardenLayer:
            lr = self.layers.get(layer.value)
            if lr:
                for f in lr.findings:
                    if f.severity in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                        lines.append(f"- **[{f.severity.value.upper()}]** {f.layer.value}: {f.message}")
                        if f.location:
                            lines.append(f"  📍 `{f.location}`")
                        if f.recommendation:
                            lines.append(f"  💡 {f.recommendation}")
        if self.recommendations:
            lines.append("")
            lines.append("## Top Recommendations")
            for i, rec in enumerate(self.recommendations[:5], 1):
                lines.append(f"{i}. {rec}")
        return "\n".join(lines)


# ── WardenRunner ───────────────────────────────────────────────────────────────

class WardenRunner:
    """Warden-compatible governance posture scanner.

    Scans a codebase across 12 layers for governance posture assessment.
    Uses static analysis (file presence, content patterns, configuration
    checks) to evaluate each layer without executing code.

    This is a framework-agnostic scanner — any codebase can be assessed.
    """

    # Layer weights for overall score
    LAYER_WEIGHTS = {
        WardenLayer.POLICY_DEFINITION: 0.12,
        WardenLayer.ACCESS_CONTROL: 0.10,
        WardenLayer.AUDIT_LOGGING: 0.10,
        WardenLayer.DATA_PROTECTION: 0.09,
        WardenLayer.NETWORK_SECURITY: 0.08,
        WardenLayer.DEPENDENCY_MANAGEMENT: 0.08,
        WardenLayer.CI_CD_SECURITY: 0.08,
        WardenLayer.ERROR_HANDLING: 0.07,
        WardenLayer.CONFIGURATION: 0.07,
        WardenLayer.TESTING_COVERAGE: 0.08,
        WardenLayer.DOCUMENTATION: 0.08,
        WardenLayer.COMMUNITY_HEALTH: 0.05,
    }

    # File patterns to check per layer
    LAYER_PATTERNS: dict[WardenLayer, dict[str, Any]] = {
        WardenLayer.POLICY_DEFINITION: {
            "required_files": ["governance/", "policies/"],
            "patterns": [r"policy", r"governance_rule", r"security_policy", r"ABDL"],
            "json_configs": [".aionui/", "config/"],
        },
        WardenLayer.ACCESS_CONTROL: {
            "required_files": ["governance/meta/"],
            "patterns": [r"permission", r"access_control", r"role", r"auth", r"boundary"],
        },
        WardenLayer.AUDIT_LOGGING: {
            "required_files": [],
            "patterns": [r"audit", r"log", r"trace", r"audit_trail", r"get_state"],
        },
        WardenLayer.DATA_PROTECTION: {
            "required_files": [".gitignore"],
            "patterns": [r"encrypt", r"pii", r"mask", r"sensitive", r"sanitize"],
            "dangerous_patterns": [r"password\s*=\s*['\"]", r"secret\s*=\s*['\"]", r"api_key\s*=\s*['\"]"],
        },
        WardenLayer.NETWORK_SECURITY: {
            "required_files": [],
            "patterns": [r"network", r"endpoint", r"firewall", r"sandbox", r"isolation"],
        },
        WardenLayer.DEPENDENCY_MANAGEMENT: {
            "required_files": ["pyproject.toml", "requirements.txt"],
            "patterns": [r"version", r"lock"],
            "json_configs": [],
        },
        WardenLayer.CI_CD_SECURITY: {
            "required_files": [".github/workflows/"],
            "patterns": [r"workflow", r"pipeline", r"ci", r"cd"],
        },
        WardenLayer.ERROR_HANDLING: {
            "required_files": [],
            "patterns": [r"try\s*:", r"except", r"error_handler", r"fallback", r"retry", r"circuit_breaker"],
        },
        WardenLayer.CONFIGURATION: {
            "required_files": [],
            "patterns": [r"config", r"settings", r"threshold", r"env", r"yaml"],
        },
        WardenLayer.TESTING_COVERAGE: {
            "required_files": ["tests/", "conftest.py"],
            "patterns": [r"test_", r"pytest", r"assert"],
        },
        WardenLayer.DOCUMENTATION: {
            "required_files": ["README.md", "docs/", "CHANGELOG.md"],
            "patterns": [r"usage", r"example", r"api", r"guide"],
        },
        WardenLayer.COMMUNITY_HEALTH: {
            "required_files": [".github/", "LICENSE", "CONTRIBUTING.md"],
            "patterns": [r"code_of_conduct", r"contributing", r"issue_template"],
        },
    }

    def __init__(self):
        self._findings: list[WardenFinding] = []

    def scan_project(self, project_root: str | Path) -> WardenReport:
        """Scan a project directory for governance posture."""
        start_time = datetime.now(timezone.utc)
        root = Path(project_root).resolve()
        project_name = root.name
        all_files = self._collect_files(root)

        report = WardenReport(
            project_name=project_name,
            timestamp=start_time.isoformat(),
        )
        self._findings = []

        # Scan each layer
        for layer in WardenLayer:
            layer_report = self._scan_layer(layer, root, all_files)
            report.layers[layer.value] = layer_report

        # Aggregate scores
        weighted_sum = 0.0
        for layer in WardenLayer:
            lr = report.layers[layer.value]
            weighted_sum += lr.score * self.LAYER_WEIGHTS[layer]
        report.overall_score = round(weighted_sum * 100, 1)
        report.posture_grade = self._score_to_grade(report.overall_score)

        # Count findings by severity
        for f in self._findings:
            if f.severity == RiskLevel.CRITICAL:
                report.critical_count += 1
            elif f.severity == RiskLevel.HIGH:
                report.high_count += 1
            elif f.severity == RiskLevel.MEDIUM:
                report.medium_count += 1
            else:
                report.low_count += 1
        report.total_findings = len(self._findings)

        report.recommendations = self._generate_recommendations(report)
        report.scan_duration_seconds = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        return report

    # ── File Collection ─────────────────────────────────────────────────────

    def _collect_files(self, root: Path) -> list[str]:
        """Collect all relevant project files (exclude .git, __pycache__, etc.)."""
        files = []
        exclude_dirs = {'.git', '__pycache__', '.venv', 'venv', 'node_modules',
                        '.pytest_cache', '.mypy_cache', '.ruff_cache', 'dist', 'build',
                        '*.egg-info'}
        exclude_patterns = ['.pyc', '.pyo', '.so', '.dll']

        for path in root.rglob("*"):
            if any(part in exclude_dirs for part in path.parts):
                continue
            if path.is_file():
                if any(path.suffix == f".{ext}" or path.name.endswith(ext) for ext in exclude_patterns):
                    continue
                files.append(str(path.relative_to(root)))
        return files

    def _file_exists(self, root: Path, pattern: str) -> bool:
        """Check if a file or directory exists in the project."""
        target = root / pattern
        return target.exists()

    def _find_files(self, root: Path, pattern: str) -> list[Path]:
        """Find files matching a glob pattern."""
        return list(root.glob(pattern))

    # ── Layer Scanners ──────────────────────────────────────────────────────

    def _scan_layer(self, layer: WardenLayer, root: Path, files: list[str]) -> LayerReport:
        """Scan a single governance layer."""
        lr = LayerReport(layer=layer)
        config = self.LAYER_PATTERNS.get(layer, {})
        checks_passed = 0
        checks_total = 0

        # Check 1: Required files present
        checks_total += 1
        required = config.get("required_files", [])
        missing_req = [rf for rf in required if not self._file_exists(root, rf)]
        if not missing_req:
            checks_passed += 1
        else:
            for mf in missing_req:
                self._add_finding(lr, layer, "required_files", RiskLevel.HIGH,
                                  f"Missing required file/directory: {mf}",
                                  mf, f"Create {mf} with governance configuration")

        # Check 2: Pattern matches in code
        checks_total += 1
        patterns = config.get("patterns", [])
        matched_patterns = set()
        for f in files:
            try:
                content = (root / f).read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            for pat in patterns:
                if re.search(pat, content, re.IGNORECASE):
                    matched_patterns.add(pat)
        if any(p in matched_patterns for p in patterns[:1]):
            checks_passed += 1
            lr.passed += 1
        else:
            self._add_finding(lr, layer, "patterns", RiskLevel.MEDIUM,
                              f"No governance patterns found in source code",
                              "*.py", f"Add governance code matching: {patterns[:3]}")

        # Check 3: Dangerous patterns (data protection only)
        if "dangerous_patterns" in config:
            checks_total += 1
            dangerous = config["dangerous_patterns"]
            found_dangerous = False
            for f in files:
                try:
                    content = (root / f).read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    continue
                for dp in dangerous:
                    if re.search(dp, content):
                        self._add_finding(lr, layer, "secrets", RiskLevel.CRITICAL,
                                          f"Potential secret in file: pattern '{dp}'",
                                          f, "Move secrets to environment variables or secret manager")
                        found_dangerous = True
            if not found_dangerous:
                checks_passed += 1
                lr.passed += 1

        # Check 4: Test file existence (testing coverage)
        if layer == WardenLayer.TESTING_COVERAGE:
            checks_total += 1
            test_files = [f for f in files if 'test' in f.lower() and f.endswith('.py')]
            if len(test_files) >= 3:
                checks_passed += 1
                lr.passed += 1
            else:
                self._add_finding(lr, layer, "test_count", RiskLevel.HIGH,
                                  f"Only {len(test_files)} test files found (minimum 3)",
                                  "tests/", "Add comprehensive test coverage for governance modules")

        # Check 5: Documentation quality
        if layer == WardenLayer.DOCUMENTATION:
            checks_total += 1
            doc_files = [f for f in files if f.endswith('.md') or f.endswith('.rst')]
            if len(doc_files) >= 3:
                checks_passed += 1
                lr.passed += 1
            else:
                self._add_finding(lr, layer, "doc_count", RiskLevel.MEDIUM,
                                  f"Only {len(doc_files)} documentation files (minimum 3)",
                                  "docs/", "Add architecture, API, and usage documentation")

        lr.score = min(checks_passed / max(checks_total, 1), 1.0)
        return lr

    def _add_finding(self, lr: LayerReport, layer: WardenLayer, dimension: str,
                     severity: RiskLevel, message: str, location: str, recommendation: str):
        """Add a finding to both the layer report and global list."""
        finding = WardenFinding(
            layer=layer, dimension=dimension, severity=severity,
            message=message, location=location, recommendation=recommendation
        )
        lr.findings.append(finding)
        self._findings.append(finding)
        if severity == RiskLevel.CRITICAL:
            lr.failures += 1
        elif severity == RiskLevel.HIGH:
            lr.failures += 1
        elif severity == RiskLevel.MEDIUM:
            lr.warnings += 1
        else:
            lr.warnings += 1

    # ── Scoring ─────────────────────────────────────────────────────────────

    def _score_to_grade(self, score: float) -> str:
        """Convert a 0-100 score to a letter grade."""
        if score >= 95:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 65:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"

    def _generate_recommendations(self, report: WardenReport) -> list[str]:
        """Generate prioritized recommendations from findings."""
        recs = []
        # Prioritize critical then high
        for f in self._findings:
            if f.severity == RiskLevel.CRITICAL:
                recs.append(f"🔴 [{f.layer.value}] {f.recommendation} ({f.location})")
        for f in self._findings:
            if f.severity == RiskLevel.HIGH:
                recs.append(f"🟠 [{f.layer.value}] {f.recommendation} ({f.location})")
        if not recs:
            recs.append("Governance posture is strong! Continue maintenance. ✅")
        return recs

    # ── Persistence ─────────────────────────────────────────────────────────

    def save_report(self, report: WardenReport, path: str = ".warden/reports/warden-report.json") -> None:
        """Save scan report as JSON."""
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def save_markdown(self, report: WardenReport, path: str = ".warden/reports/warden-report.md") -> None:
        """Save scan report as Markdown."""
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(report.to_markdown(), encoding="utf-8")
