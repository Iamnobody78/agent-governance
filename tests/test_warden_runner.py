"""Tests for Warden Governance Posture Scanner."""

import json
import os
import pytest
import tempfile
from pathlib import Path
from benchmarks.warden_runner import (
    WardenRunner,
    WardenReport,
    WardenLayer,
    WardenFinding,
    RiskLevel,
    LayerReport,
)


class TestWardenRunner:
    """Test WardenRunner core functionality."""

    def test_scan_empty_project(self, tmp_path):
        """Scan a project with only minimal files."""
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")

        runner = WardenRunner()
        report = runner.scan_project(str(tmp_path))
        assert isinstance(report, WardenReport)
        assert report.project_name == tmp_path.name
        assert report.overall_score > 0
        assert report.scan_duration_seconds >= 0

    def test_scan_governed_project(self, tmp_path):
        """Scan a project with good governance structure."""
        # Create required files
        (tmp_path / "README.md").write_text("# Test Project")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\nversion='1.0.0'")
        (tmp_path / "LICENSE").write_text("MIT")
        (tmp_path / "CONTRIBUTING.md").write_text("# Contributing")
        (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/")

        # Create governance directory
        gov = tmp_path / "governance"
        gov.mkdir()
        (gov / "__init__.py").write_text("")
        meta = gov / "meta"
        meta.mkdir()
        (meta / "__init__.py").write_text("")
        (meta / "godelian_boundary.py").write_text(
            "class GodelianBoundary:\n"
            "    def get_state(self): return {}\n"
            "    def audit_trail(self): return []\n"
            "    def stop(self): pass\n"
            "    def override(self, id): pass\n"
        )

        # Create tests directory
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "test_example.py").write_text("def test_pass(): assert True\n")
        (tests_dir / "test_godelian.py").write_text("def test_boundary(): assert True\n")
        (tests_dir / "test_security.py").write_text("def test_security(): assert True\n")

        # Create config
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "settings.yaml").write_text("threshold: 0.7\n")

        # Create .github
        github = tmp_path / ".github"
        github.mkdir()
        (github / "workflows").mkdir()
        (github / "workflows" / "ci.yml").write_text("name: CI\non: [push]\n")

        # Create docs
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "README.md").write_text("# Documentation")

        runner = WardenRunner()
        report = runner.scan_project(str(tmp_path))
        assert report.overall_score >= 50, f"Expected >=50, got {report.overall_score}"
        assert report.posture_grade in ("A+", "A", "B", "C", "D", "F")

    def test_scan_detects_secrets(self, tmp_path):
        """Test that hardcoded secrets are detected."""
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "config.py").write_text(
            'API_KEY = "sk-1234567890abcdef"\n'
            'password = "super_secret_123"\n'
        )

        runner = WardenRunner()
        report = runner.scan_project(str(tmp_path))
        # Should have critical findings for hardcoded secrets
        assert report.critical_count > 0 or any(
            f.severity == RiskLevel.CRITICAL
            for lr in report.layers.values()
            for f in lr.findings
        ), "Secrets should be detected as CRITICAL"

    def test_all_layers_present(self, tmp_path):
        """Test that all 12 layers are reported."""
        (tmp_path / "README.md").write_text("# Test")
        runner = WardenRunner()
        report = runner.scan_project(str(tmp_path))
        for layer in WardenLayer:
            assert layer.value in report.layers, f"Missing layer: {layer.value}"
            assert isinstance(report.layers[layer.value], LayerReport)


class TestWardenReport:
    """Test WardenReport data structure."""

    def test_report_creation(self):
        report = WardenReport(
            project_name="test",
            overall_score=85.0,
            posture_grade="A",
            critical_count=1,
            high_count=2,
            medium_count=3,
            low_count=4,
            total_findings=10,
        )
        assert report.project_name == "test"
        assert report.overall_score == 85.0
        assert report.posture_grade == "A"
        assert report.critical_count == 1
        assert report.total_findings == 10

    def test_to_dict(self):
        report = WardenReport(
            project_name="test",
            overall_score=75.0,
            posture_grade="B",
        )
        d = report.to_dict()
        assert d["project"] == "test"
        assert d["overall_score"] == 75.0
        assert d["posture_grade"] == "B"
        assert "findings" in d

    def test_to_markdown(self):
        report = WardenReport(
            project_name="test-project",
            overall_score=90.0,
            posture_grade="A",
            total_findings=5,
            critical_count=0,
            high_count=0,
            medium_count=2,
            low_count=3,
        )
        md = report.to_markdown()
        assert "Warden Governance Posture" in md
        assert "test-project" in md
        assert "90.0/100" in md

    def test_empty_markdown(self):
        report = WardenReport(project_name="empty")
        md = report.to_markdown()
        assert "Warden Governance Posture" in md
        assert "empty" in md


class TestScoreToGrade:
    """Test score-to-grade conversion."""

    @pytest.mark.parametrize("score,expected", [
        (95, "A+"),
        (90, "A"),
        (85, "A"),
        (80, "B"),
        (75, "B"),
        (70, "C"),
        (65, "C"),
        (55, "D"),
        (50, "D"),
        (40, "F"),
        (0, "F"),
    ])
    def test_grade_conversion(self, score, expected):
        runner = WardenRunner()
        assert runner._score_to_grade(score) == expected


class TestFileCollection:
    """Test file collection and filtering."""

    def test_excludes_git(self, tmp_path):
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("fake")

        runner = WardenRunner()
        files = runner._collect_files(tmp_path)
        assert "README.md" in files
        assert ".git/config" not in files

    def test_excludes_pycache(self, tmp_path):
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cached.pyc").write_text("fake")

        runner = WardenRunner()
        files = runner._collect_files(tmp_path)
        assert "README.md" in files
        assert not any("__pycache__" in f for f in files)


class TestPersistence:
    """Test report persistence."""

    def test_save_report_json(self, tmp_path):
        runner = WardenRunner()
        report = runner.scan_project(str(tmp_path))
        json_path = tmp_path / ".warden" / "reports" / "warden-report.json"
        runner.save_report(report, str(json_path))
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["project"] == tmp_path.name

    def test_save_report_markdown(self, tmp_path):
        runner = WardenRunner()
        report = runner.scan_project(str(tmp_path))
        md_path = tmp_path / ".warden" / "reports" / "warden-report.md"
        runner.save_markdown(report, str(md_path))
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "Warden Governance Posture" in content
