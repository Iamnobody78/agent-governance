"""Tests for GitHub Operations Guardian v2.0."""

import json
import os
import pytest
from tools.github_guardian import (
    GitHubGuardian,
    GuardianReport,
    GuardianStatus,
    IssueMetrics,
    PRMetrics,
    DiscussionMetrics,
    CommitMetrics,
    CIMetrics,
    DEFAULT_THRESHOLDS,
)


class TestGuardianReport:
    """Test GuardianReport data structure."""

    def test_report_creation_defaults(self):
        report = GuardianReport()
        assert report.status == GuardianStatus.UNKNOWN
        assert report.repo == ""
        assert report.total_score == 0.0
        assert isinstance(report.issues, IssueMetrics)
        assert isinstance(report.prs, PRMetrics)
        assert isinstance(report.discussions, DiscussionMetrics)
        assert isinstance(report.commits, CommitMetrics)
        assert isinstance(report.ci, CIMetrics)

    def test_to_dict(self):
        report = GuardianReport(
            repo="owner/repo",
            status=GuardianStatus.HEALTHY,
            total_score=85.0,
            issues=IssueMetrics(total_open=10, good_first_issues=5, bugs=3),
            prs=PRMetrics(total_open=5, awaiting_review=2),
            discussions=DiscussionMetrics(total_open=4, answered=3),
            commits=CommitMetrics(commits_last_week=10, active_contributors=3),
            ci=CIMetrics(pass_rate=0.95),
            alerts=[
                {"severity": "warning", "message": "Test alert"}
            ],
            recommendations=["Test recommendation"],
        )

        d = report.to_dict()
        assert d["repo"] == "owner/repo"
        assert d["status"] == "healthy"
        assert d["total_score"] == 85.0
        assert d["issues"]["total_open"] == 10
        assert d["issues"]["good_first_issues"] == 5
        assert d["prs"]["total_open"] == 5
        assert d["discussions"]["total_open"] == 4
        assert d["commits"]["commits_last_week"] == 10
        assert d["ci"]["pass_rate"] == 0.95
        assert len(d["alerts"]) == 1
        assert len(d["recommendations"]) == 1

    def test_to_markdown_healthy(self):
        report = GuardianReport(
            repo="owner/repo",
            status=GuardianStatus.HEALTHY,
            total_score=85.0,
            issues=IssueMetrics(good_first_issues=5),
            prs=PRMetrics(),
            discussions=DiscussionMetrics(),
            commits=CommitMetrics(),
        )
        md = report.to_markdown()
        assert "Repository Health Report" in md
        assert "owner/repo" in md
        assert "🟢" in md
        assert "HEALTHY" in md

    def test_to_markdown_critical(self):
        report = GuardianReport(
            repo="owner/repo",
            status=GuardianStatus.CRITICAL,
            total_score=25.0,
            alerts=[{"severity": "critical", "message": "Repo inactive"}],
            recommendations=["Fix CI failures"],
        )
        md = report.to_markdown()
        assert "🔴" in md
        assert "CRITICAL" in md
        assert "Repo inactive" in md
        assert "Fix CI failures" in md


class TestGuardianStatus:
    """Test GuardianStatus enum and classification."""

    @pytest.mark.parametrize("score,expected", [
        (90, GuardianStatus.HEALTHY),
        (70, GuardianStatus.HEALTHY),
        (69, GuardianStatus.WARNING),
        (50, GuardianStatus.WARNING),
        (40, GuardianStatus.WARNING),
        (39, GuardianStatus.CRITICAL),
        (0, GuardianStatus.CRITICAL),
    ])
    def test_classify_status(self, score, expected):
        guardian = GitHubGuardian(repo_owner="o", repo_name="r")
        report = GuardianReport(total_score=score)
        result = guardian._classify_status(report)
        assert result == expected


class TestDefaultThresholds:
    """Test default threshold values."""

    def test_thresholds_are_sensible(self):
        t = DEFAULT_THRESHOLDS
        assert t["min_open_issues"] >= 3
        assert t["min_good_first_issues"] >= 1
        assert t["min_open_prs"] >= 1
        assert t["min_discussions"] >= 1
        assert t["max_response_hours"] > 0
        assert t["max_stale_days"] > 7
        assert t["min_weekly_commits"] >= 1
        assert t["ci_pass_rate_min"] > 0 and t["ci_pass_rate_min"] <= 1


class TestScoring:
    """Test health score calculation."""

    def test_perfect_score(self):
        guardian = GitHubGuardian(repo_owner="o", repo_name="r")
        report = GuardianReport(
            issues=IssueMetrics(total_open=10, good_first_issues=5, avg_response_hours=1),
            prs=PRMetrics(total_open=5, avg_review_hours=2),
            discussions=DiscussionMetrics(total_open=5, answered=5),
            commits=CommitMetrics(commits_last_week=10, active_contributors=5, last_commit_age_hours=1),
            ci=CIMetrics(pass_rate=1.0),
        )
        score = guardian._calculate_score(report)
        assert score >= 90, f"Expected >=90, got {score}"

    def test_failing_score(self):
        guardian = GitHubGuardian(repo_owner="o", repo_name="r")
        report = GuardianReport(
            issues=IssueMetrics(total_open=0, good_first_issues=0, avg_response_hours=100, stale_count=10),
            prs=PRMetrics(total_open=0, avg_review_hours=100, stale_count=5),
            discussions=DiscussionMetrics(total_open=0, answered=0),
            commits=CommitMetrics(commits_last_week=0, active_contributors=0, last_commit_age_hours=500),
            ci=CIMetrics(pass_rate=0.0),
        )
        score = guardian._calculate_score(report)
        assert score < 50, f"Expected <50, got {score}"


class TestGitHubGuardianOffline:
    """Test guardian without gh CLI (offline mode)."""

    def test_offline_mode(self):
        guardian = GitHubGuardian(repo_owner="test", repo_name="test")
        # gh isn't available in test environments, so this should work offline
        report = guardian.run_full_scan()
        assert isinstance(report, GuardianReport)
        # Offline mode will have at least one alert about gh not being available
        # or will be UNKNOWN status

    def test_custom_thresholds(self):
        guardian = GitHubGuardian(
            repo_owner="test", repo_name="test",
            thresholds={"min_good_first_issues": 1, "max_response_hours": 12}
        )
        assert guardian.thresholds["min_good_first_issues"] == 1
        assert guardian.thresholds["max_response_hours"] == 12
        # Default values still present
        assert guardian.thresholds["min_open_issues"] == 5

    def test_save_report(self, tmp_path):
        guardian = GitHubGuardian(repo_owner="test", repo_name="test")
        report = GuardianReport(repo="test/test", status=GuardianStatus.HEALTHY)

        md_path = tmp_path / "GUARDIAN_REPORT.md"
        guardian.save_report(report, str(md_path))
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "test/test" in content

    def test_save_json(self, tmp_path):
        guardian = GitHubGuardian(repo_owner="test", repo_name="test")
        report = GuardianReport(repo="test/test", status=GuardianStatus.HEALTHY)

        json_path = tmp_path / "guardian_report.json"
        guardian.save_json(report, str(json_path))
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["repo"] == "test/test"
        assert data["status"] == "healthy"
