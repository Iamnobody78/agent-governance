"""
GitHub Operations Guardian v2.0
===============================

Self-governing GitHub repository health monitor. Implements the
"GitHub 运维守护者 v2" protocol:

  - Daily health scans (Issues, PRs, Discussions, commits, CI)
  - Maintain >=3 Good First Issues, >=3 Discussions, >=3 active PRs
  - 24-hour response time SLA
  - Auto-label, stale detection, community pulse

Architecture (Layer 4 — Organizational & Process Governance):
  GitHub Guardian → MetaCognitiveLoop.ingest_org_feedback()
  └── GuardianReport → Layer 2 modules for strategy adjustment

Usage:
    guardian = GitHubGuardian(repo_owner="agent-governance", repo_name="agent-governance")
    report = guardian.run_full_scan()
    print(report.to_markdown())

    # CLI mode
    python -m tools.github_guardian --repo agent-governance/agent-governance --output report.md
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ── Enums & Constants ──────────────────────────────────────────────────────────

class GuardianStatus(str, Enum):
    HEALTHY = "healthy"          # All metrics within thresholds
    WARNING = "warning"          # One or more metrics approaching limits
    CRITICAL = "critical"        # One or more metrics below minimums
    UNKNOWN = "unknown"          # Unable to determine (e.g., no GitHub token)


# ── Thresholds from 运维守护者 v2 protocol ────────────────────────────────────

DEFAULT_THRESHOLDS = {
    "min_open_issues": 5,               # Total open issues
    "min_good_first_issues": 3,         # Good First Issue label
    "min_open_prs": 3,                  # Active pull requests
    "min_discussions": 3,               # Active discussions
    "max_response_hours": 24,           # SLA for first response
    "max_stale_days": 30,               # Mark as stale after 30 days
    "max_inactive_days": 14,            # Repo considered inactive
    "min_weekly_commits": 3,            # Commits per week
    "min_contributors": 2,              # Active contributors
    "ci_pass_rate_min": 0.80,           # CI pass rate minimum
}


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class IssueMetrics:
    """Health metrics for GitHub Issues."""
    total_open: int = 0
    good_first_issues: int = 0
    bugs: int = 0
    enhancements: int = 0
    unresponded: int = 0                # Issues with no response in 24h
    stale_count: int = 0                # No activity in >30 days
    avg_response_hours: float = 0.0
    oldest_unresponded_hours: float = 0.0


@dataclass
class PRMetrics:
    """Health metrics for Pull Requests."""
    total_open: int = 0
    total_draft: int = 0
    awaiting_review: int = 0
    changes_requested: int = 0
    approved: int = 0
    stale_count: int = 0                # No activity in >14 days
    avg_review_hours: float = 0.0
    ci_failures: int = 0


@dataclass
class DiscussionMetrics:
    """Health metrics for GitHub Discussions."""
    total_open: int = 0
    answered: int = 0
    unanswered: int = 0
    stale_count: int = 0
    categories: dict[str, int] = field(default_factory=dict)


@dataclass
class CommitMetrics:
    """Health metrics for commit activity."""
    commits_last_week: int = 0
    commits_last_month: int = 0
    active_contributors: int = 0
    last_commit_age_hours: float = 0.0
    default_branch: str = "main"


@dataclass
class CIMetrics:
    """Health metrics for CI/CD pipelines."""
    total_workflows: int = 0
    total_runs_last_week: int = 0
    success_count: int = 0
    failure_count: int = 0
    pass_rate: float = 1.0
    failing_workflows: list[str] = field(default_factory=list)


@dataclass
class GuardianReport:
    """Complete health scan report."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: GuardianStatus = GuardianStatus.UNKNOWN
    repo: str = ""
    issues: IssueMetrics = field(default_factory=IssueMetrics)
    prs: PRMetrics = field(default_factory=PRMetrics)
    discussions: DiscussionMetrics = field(default_factory=DiscussionMetrics)
    commits: CommitMetrics = field(default_factory=CommitMetrics)
    ci: CIMetrics = field(default_factory=CIMetrics)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    total_score: float = 0.0            # 0-100 health score
    thresholds: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "status": self.status.value,
            "repo": self.repo,
            "total_score": round(self.total_score, 1),
            "issues": {
                "total_open": self.issues.total_open,
                "good_first_issues": self.issues.good_first_issues,
                "bugs": self.issues.bugs,
                "enhancements": self.issues.enhancements,
                "unresponded": self.issues.unresponded,
                "stale_count": self.issues.stale_count,
                "avg_response_hours": round(self.issues.avg_response_hours, 1),
                "oldest_unresponded_hours": round(self.issues.oldest_unresponded_hours, 1),
            },
            "prs": {
                "total_open": self.prs.total_open,
                "total_draft": self.prs.total_draft,
                "awaiting_review": self.prs.awaiting_review,
                "stale_count": self.prs.stale_count,
                "avg_review_hours": round(self.prs.avg_review_hours, 1),
            },
            "discussions": {
                "total_open": self.discussions.total_open,
                "answered": self.discussions.answered,
                "unanswered": self.discussions.unanswered,
            },
            "commits": {
                "commits_last_week": self.commits.commits_last_week,
                "active_contributors": self.commits.active_contributors,
                "last_commit_age_hours": round(self.commits.last_commit_age_hours, 1),
            },
            "ci": {
                "pass_rate": round(self.ci.pass_rate, 3),
                "failing_workflows": self.ci.failing_workflows,
            },
            "alerts": self.alerts,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        """Render report as Markdown for GitHub issues/discussions."""
        emoji = {"healthy": "🟢", "warning": "🟡", "critical": "🔴", "unknown": "⚪"}
        lines = [
            f"# 🏥 Repository Health Report — {self.repo}",
            f"**Status**: {emoji[self.status.value]} {self.status.value.upper()}",
            f"**Score**: {self.total_score:.1f}/100",
            f"**Timestamp**: {self.timestamp}",
            "",
            "## 📊 Metrics",
            "",
            "### Issues",
            f"- Open: {self.issues.total_open} (Good First: {self.issues.good_first_issues})",
            f"- Bugs: {self.issues.bugs} | Enhancements: {self.issues.enhancements}",
            f"- Unresponded: {self.issues.unresponded} | Stale: {self.issues.stale_count}",
            f"- Avg Response: {self.issues.avg_response_hours:.1f}h",
            "",
            "### Pull Requests",
            f"- Open: {self.prs.total_open} | Draft: {self.prs.total_draft}",
            f"- Awaiting Review: {self.prs.awaiting_review}",
            f"- Avg Review Time: {self.prs.avg_review_hours:.1f}h",
            "",
            "### Discussions",
            f"- Open: {self.discussions.total_open}",
            f"- Answered: {self.discussions.answered} | Unanswered: {self.discussions.unanswered}",
            "",
            "### Commits",
            f"- Last Week: {self.commits.commits_last_week}",
            f"- Active Contributors: {self.commits.active_contributors}",
            f"- Last Commit: {self.commits.last_commit_age_hours:.1f}h ago",
            "",
            "### CI/CD",
            f"- Pass Rate: {self.ci.pass_rate:.1%}",
        ]
        if self.alerts:
            lines.append("")
            lines.append("## 🚨 Alerts")
            for alert in self.alerts:
                lines.append(f"- [{alert['severity'].upper()}] {alert['message']}")
        if self.recommendations:
            lines.append("")
            lines.append("## 💡 Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
        lines.append("")
        lines.append("---")
        lines.append(f"*Generated by GitHub Operations Guardian v2.0 at {self.timestamp}*")
        return "\n".join(lines)


# ── GitHub Guardian ────────────────────────────────────────────────────────────

class GitHubGuardian:
    """GitHub repository health guardian.

    Implements the 运维守护者 v2 protocol: automated daily health scans,
    SLA monitoring, and community pulse tracking.

    Uses `gh` CLI under the hood for all GitHub API interactions.
    """

    def __init__(
        self,
        repo_owner: str = "",
        repo_name: str = "",
        gh_token: str | None = None,
        thresholds: dict[str, Any] | None = None,
    ):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.repo_full = f"{repo_owner}/{repo_name}" if repo_owner and repo_name else ""
        self.gh_token = gh_token or os.environ.get("GITHUB_TOKEN", "")
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._gh_available = self._check_gh()

    # ── Core Health Checks ──────────────────────────────────────────────────

    def run_full_scan(self) -> GuardianReport:
        """Execute all health checks and produce a complete report."""
        report = GuardianReport(
            repo=self.repo_full,
            thresholds=self.thresholds,
        )

        if not self._gh_available:
            report.status = GuardianStatus.UNKNOWN
            report.alerts.append({
                "severity": "warning",
                "message": "GitHub CLI (gh) not available. Running in offline mode with limited data."
            })
            report.recommendations.append("Install `gh` CLI and authenticate to enable full health scanning.")
            return report

        # Collect all metrics
        report.issues = self._scan_issues()
        report.prs = self._scan_prs()
        report.discussions = self._scan_discussions()
        report.commits = self._scan_commits()
        report.ci = self._scan_ci()

        # Score and classify
        report.total_score = self._calculate_score(report)
        report.status = self._classify_status(report)
        report.alerts = self._generate_alerts(report)
        report.recommendations = self._generate_recommendations(report)

        return report

    # ── GH CLI Helpers ──────────────────────────────────────────────────────

    def _check_gh(self) -> bool:
        """Verify `gh` CLI is available and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _gh_api(self, endpoint: str, jq_filter: str = ".") -> Any:
        """Call GitHub API via `gh api` and parse JSON."""
        cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint]
        if self.gh_token:
            cmd.extend(["-H", f"Authorization: Bearer {self.gh_token}"])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return None
            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None

    def _gh_graphql(self, query: str, variables: dict[str, Any] | None = None) -> Any:
        """Execute GraphQL query via `gh api graphql`."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
        if variables:
            cmd.extend(["-f", f"variables={json.dumps(variables)}"])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return None
            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None

    # ── Scanners ────────────────────────────────────────────────────────────

    def _scan_issues(self) -> IssueMetrics:
        """Scan repository issues for health metrics."""
        metrics = IssueMetrics()
        if not self.repo_full:
            return metrics

        # GraphQL query for comprehensive issue data
        query = """
        query($owner: String!, $repo: String!) {
          repository(owner: $owner, name: $repo) {
            issues(first: 100, states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}) {
              totalCount
              nodes {
                number
                title
                createdAt
                updatedAt
                labels(first: 10) { nodes { name } }
                comments { totalCount }
              }
            }
          }
        }
        """
        data = self._gh_graphql(query, {"owner": self.repo_owner, "name": self.repo_name})
        if not data or "data" not in data:
            return metrics

        repo = data.get("data", {}).get("repository", {})
        issues_data = repo.get("issues", {})
        nodes = issues_data.get("nodes", [])
        now = datetime.now(timezone.utc)

        metrics.total_open = issues_data.get("totalCount", 0)
        response_times: list[float] = []

        for issue in nodes:
            labels = [l["name"] for l in issue.get("labels", {}).get("nodes", [])]
            if "good first issue" in [l.lower() for l in labels]:
                metrics.good_first_issues += 1
            if "bug" in [l.lower() for l in labels]:
                metrics.bugs += 1
            if "enhancement" in [l.lower() for l in labels]:
                metrics.enhancements += 1

            # Response time: time between creation and first non-author comment
            created = datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
            updated = datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00"))
            age_hours = (now - created).total_seconds() / 3600

            if issue.get("comments", {}).get("totalCount", 0) == 0:
                metrics.unresponded += 1
                if age_hours > metrics.oldest_unresponded_hours:
                    metrics.oldest_unresponded_hours = age_hours
            else:
                # Approximate response time as half of age (simplified)
                response_times.append(age_hours / 2)

            # Stale check
            inactive_hours = (now - updated).total_seconds() / 3600
            if inactive_hours > 24 * self.thresholds["max_stale_days"]:
                metrics.stale_count += 1

        if response_times:
            metrics.avg_response_hours = sum(response_times) / len(response_times)
        elif metrics.unresponded > 0 and nodes:
            metrics.avg_response_hours = metrics.oldest_unresponded_hours

        return metrics

    def _scan_prs(self) -> PRMetrics:
        """Scan pull requests for health metrics."""
        metrics = PRMetrics()
        if not self.repo_full:
            return metrics

        query = """
        query($owner: String!, $repo: String!) {
          repository(owner: $owner, name: $repo) {
            pullRequests(first: 50, states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}) {
              totalCount
              nodes {
                number
                title
                createdAt
                updatedAt
                isDraft
                reviews(first: 5, states: [CHANGES_REQUESTED, APPROVED]) { totalCount }
                commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
              }
            }
          }
        }
        """
        data = self._gh_graphql(query, {"owner": self.repo_owner, "name": self.repo_name})
        if not data or "data" not in data:
            return metrics

        repo = data.get("data", {}).get("repository", {})
        prs_data = repo.get("pullRequests", {})
        nodes = prs_data.get("nodes", [])
        now = datetime.now(timezone.utc)

        metrics.total_open = prs_data.get("totalCount", 0)
        review_times: list[float] = []

        for pr in nodes:
            if pr.get("isDraft"):
                metrics.total_draft += 1
            reviews = pr.get("reviews", {})
            if reviews.get("totalCount", 0) == 0:
                metrics.awaiting_review += 1

            # CI status check
            commits_data = pr.get("commits", {}).get("nodes", [])
            if commits_data:
                status = commits_data[-1].get("commit", {}).get("statusCheckRollup")
                if status and status.get("state") in ("FAILURE", "ERROR"):
                    metrics.ci_failures += 1

            # Age calculation
            created = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
            updated = datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00"))
            age_hours = (now - created).total_seconds() / 3600
            review_times.append(age_hours)

            # Stale PR (no activity >14 days)
            if (now - updated).total_seconds() / 3600 > 24 * 14:
                metrics.stale_count += 1

        if review_times:
            metrics.avg_review_hours = sum(review_times) / len(review_times)

        return metrics

    def _scan_discussions(self) -> DiscussionMetrics:
        """Scan GitHub Discussions for health metrics."""
        metrics = DiscussionMetrics()
        if not self.repo_full:
            return metrics

        # Discussions use a different GraphQL type
        query = """
        query($owner: String!, $repo: String!) {
          repository(owner: $owner, name: $repo) {
            discussions(first: 50, orderBy: {field: CREATED_AT, direction: DESC}) {
              totalCount
              nodes {
                number
                title
                createdAt
                updatedAt
                answer { id }
                category { name }
              }
            }
          }
        }
        """
        data = self._gh_graphql(query, {"owner": self.repo_owner, "name": self.repo_name})
        if not data or "data" not in data:
            return metrics

        repo = data.get("data", {}).get("repository", {})
        disc_data = repo.get("discussions", {})
        nodes = disc_data.get("nodes", [])
        now = datetime.now(timezone.utc)

        metrics.total_open = disc_data.get("totalCount", 0)

        for disc in nodes:
            if disc.get("answer"):
                metrics.answered += 1
            else:
                metrics.unanswered += 1
            cat = disc.get("category", {}).get("name", "General")
            metrics.categories[cat] = metrics.categories.get(cat, 0) + 1

            # Stale
            updated = datetime.fromisoformat(disc["updatedAt"].replace("Z", "+00:00"))
            if (now - updated).total_seconds() / 3600 > 24 * self.thresholds["max_stale_days"]:
                metrics.stale_count += 1

        return metrics

    def _scan_commits(self) -> CommitMetrics:
        """Scan commit activity."""
        metrics = CommitMetrics()
        if not self.repo_full:
            return metrics

        # Recent commits via REST API (simpler for date filtering)
        since_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        commits = self._gh_api(
            f"/repos/{self.repo_full}/commits?since={since_date}&per_page=100"
        )
        if isinstance(commits, list):
            metrics.commits_last_week = len(commits)
            authors = set()
            for c in commits:
                login = c.get("author", {}).get("login") if c.get("author") else None
                if login:
                    authors.add(login)
            metrics.active_contributors = len(authors)

        # Monthly commits
        since_month = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        month_commits = self._gh_api(
            f"/repos/{self.repo_full}/commits?since={since_month}&per_page=100"
        )
        if isinstance(month_commits, list):
            metrics.commits_last_month = len(month_commits)

        # Last commit age
        latest = self._gh_api(f"/repos/{self.repo_full}/commits?per_page=1")
        if isinstance(latest, list) and latest:
            last_date = latest[0].get("commit", {}).get("author", {}).get("date", "")
            if last_date:
                last_dt = datetime.fromisoformat(last_date.replace("Z", "+00:00"))
                metrics.last_commit_age_hours = (
                    datetime.now(timezone.utc) - last_dt
                ).total_seconds() / 3600

        # Default branch
        repo_info = self._gh_api(f"/repos/{self.repo_full}")
        if isinstance(repo_info, dict):
            metrics.default_branch = repo_info.get("default_branch", "main")

        return metrics

    def _scan_ci(self) -> CIMetrics:
        """Scan CI/CD workflow status."""
        metrics = CIMetrics()
        if not self.repo_full:
            return metrics

        # List workflows
        workflows = self._gh_api(f"/repos/{self.repo_full}/actions/workflows?per_page=50")
        if isinstance(workflows, dict):
            wf_list = workflows.get("workflows", [])
            metrics.total_workflows = len(wf_list)

        # Recent runs
        runs = self._gh_api(f"/repos/{self.repo_full}/actions/runs?per_page=50")
        if isinstance(runs, dict):
            run_nodes = runs.get("workflow_runs", [])
            metrics.total_runs_last_week = len(run_nodes)
            for run in run_nodes:
                conclusion = run.get("conclusion", "")
                if conclusion == "success":
                    metrics.success_count += 1
                elif conclusion in ("failure", "cancelled", "timed_out"):
                    metrics.failure_count += 1
                    wf_name = run.get("name", "unknown")
                    if wf_name not in metrics.failing_workflows:
                        metrics.failing_workflows.append(wf_name)

        total = metrics.success_count + metrics.failure_count
        metrics.pass_rate = metrics.success_count / total if total > 0 else 1.0

        return metrics

    # ── Scoring & Classification ────────────────────────────────────────────

    def _calculate_score(self, report: GuardianReport) -> float:
        """Calculate overall health score (0-100).

        Weighted dimensions:
        - Issues: 25% (response time, good-first-issue count, stale)
        - PRs: 25% (review time, stale, draft ratio)
        - Discussions: 15% (answered ratio)
        - Commits: 20% (frequency, contributor count)
        - CI: 15% (pass rate)
        """
        t = self.thresholds
        scores: dict[str, float] = {}

        # Issues score
        issue_scores = []
        if report.issues.total_open >= t["min_open_issues"]:
            issue_scores.append(1.0)
        else:
            issue_scores.append(report.issues.total_open / max(t["min_open_issues"], 1))
        issue_scores.append(
            min(report.issues.good_first_issues / max(t["min_good_first_issues"], 1), 1.0)
        )
        if report.issues.avg_response_hours > 0:
            issue_scores.append(min(t["max_response_hours"] / max(report.issues.avg_response_hours, 0.1), 1.0))
        else:
            issue_scores.append(1.0)
        stale_ratio = 1 - (report.issues.stale_count / max(report.issues.total_open, 1))
        issue_scores.append(max(stale_ratio, 0))
        scores["issues"] = sum(issue_scores) / len(issue_scores) * 25

        # PRs score
        pr_scores = []
        non_draft = report.prs.total_open - report.prs.total_draft
        pr_scores.append(min(non_draft / max(t["min_open_prs"], 1), 1.0))
        if report.prs.avg_review_hours > 0:
            pr_scores.append(
                min(t["max_response_hours"] / max(report.prs.avg_review_hours, 0.1), 1.0)
            )
        else:
            pr_scores.append(1.0)
        pr_stale_ratio = 1 - (report.prs.stale_count / max(report.prs.total_open, 1))
        pr_scores.append(max(pr_stale_ratio, 0))
        scores["prs"] = sum(pr_scores) / len(pr_scores) * 25

        # Discussions score
        disc_scores = []
        disc_scores.append(min(report.discussions.total_open / max(t["min_discussions"], 1), 1.0))
        if report.discussions.total_open > 0:
            disc_scores.append(report.discussions.answered / max(report.discussions.total_open, 1))
        else:
            disc_scores.append(0)
        scores["discussions"] = sum(disc_scores) / len(disc_scores) * 15

        # Commits score
        commit_scores = []
        commit_scores.append(min(report.commits.commits_last_week / max(t["min_weekly_commits"], 1), 1.0))
        commit_scores.append(
            min(report.commits.active_contributors / max(t["min_contributors"], 1), 1.0)
        )
        # Penalty for old commits
        if report.commits.last_commit_age_hours > 24 * t["max_inactive_days"]:
            commit_scores.append(0.0)
        else:
            commit_scores.append(1.0)
        scores["commits"] = sum(commit_scores) / len(commit_scores) * 20

        # CI score
        scores["ci"] = max(report.ci.pass_rate, 0) * 15

        return round(sum(scores.values()), 1)

    def _classify_status(self, report: GuardianReport) -> GuardianStatus:
        """Classify repository health status."""
        if report.total_score >= 70:
            return GuardianStatus.HEALTHY
        elif report.total_score >= 40:
            return GuardianStatus.WARNING
        else:
            return GuardianStatus.CRITICAL

    def _generate_alerts(self, report: GuardianReport) -> list[dict[str, Any]]:
        """Generate alerts for metrics below thresholds."""
        alerts = []
        t = self.thresholds

        if report.issues.good_first_issues < t["min_good_first_issues"]:
            alerts.append({
                "severity": "warning",
                "metric": "good_first_issues",
                "message": (
                    f"Good First Issues ({report.issues.good_first_issues}) below "
                    f"minimum ({t['min_good_first_issues']}). "
                    f"Create {t['min_good_first_issues'] - report.issues.good_first_issues} more."
                )
            })

        if report.issues.unresponded > 0:
            alerts.append({
                "severity": "warning" if report.issues.unresponded <= 3 else "critical",
                "metric": "unresponded_issues",
                "message": (
                    f"{report.issues.unresponded} issues have no response. "
                    f"SLA: {t['max_response_hours']}h. Oldest: {report.issues.oldest_unresponded_hours:.1f}h"
                )
            })

        if report.prs.awaiting_review > 0:
            alerts.append({
                "severity": "warning",
                "metric": "awaiting_review",
                "message": (
                    f"{report.prs.awaiting_review} PRs awaiting review. "
                    f"Avg review time: {report.prs.avg_review_hours:.1f}h"
                )
            })

        non_draft = report.prs.total_open - report.prs.total_draft
        if non_draft < t["min_open_prs"]:
            alerts.append({
                "severity": "warning",
                "metric": "open_prs",
                "message": f"Active PRs ({non_draft}) below minimum ({t['min_open_prs']})."
            })

        if report.discussions.total_open < t["min_discussions"]:
            alerts.append({
                "severity": "warning",
                "metric": "discussions",
                "message": f"Discussions ({report.discussions.total_open}) below minimum ({t['min_discussions']})."
            })

        if report.commits.commits_last_week < t["min_weekly_commits"]:
            alerts.append({
                "severity": "warning",
                "metric": "weekly_commits",
                "message": (
                    f"Commits this week ({report.commits.commits_last_week}) below "
                    f"minimum ({t['min_weekly_commits']})."
                )
            })

        if report.commits.last_commit_age_hours > 24 * t["max_inactive_days"]:
            alerts.append({
                "severity": "critical",
                "metric": "repo_inactive",
                "message": (
                    f"Last commit {report.commits.last_commit_age_hours:.1f}h ago. "
                    f"Repository appears inactive."
                )
            })

        if report.ci.pass_rate < t["ci_pass_rate_min"]:
            alerts.append({
                "severity": "critical",
                "metric": "ci_pass_rate",
                "message": (
                    f"CI pass rate ({report.ci.pass_rate:.1%}) below minimum "
                    f"({t['ci_pass_rate_min']:.0%}). Failing: {report.ci.failing_workflows}"
                )
            })

        return alerts

    def _generate_recommendations(self, report: GuardianReport) -> list[str]:
        """Generate actionable recommendations."""
        recs = []
        t = self.thresholds

        if report.issues.good_first_issues < t["min_good_first_issues"]:
            recs.append(
                "Create new Good First Issues — review open bugs/features and tag "
                "beginner-friendly items with 'good first issue' label."
            )

        if report.issues.unresponded > 0:
            recs.append(
                f"Respond to {report.issues.unresponded} unanswered issues within "
                f"{t['max_response_hours']}h SLA."
            )

        if report.issues.stale_count > 3:
            recs.append(
                f"Clean up {report.issues.stale_count} stale issues — close or "
                f"add 'stale' label with auto-close timer."
            )

        if report.prs.awaiting_review > 0:
            recs.append(
                f"Review {report.prs.awaiting_review} pending PRs to keep "
                f"contribution pipeline flowing."
            )

        if report.prs.stale_count > 0:
            recs.append(
                f"Follow up on {report.prs.stale_count} stale PRs — request "
                f"updates or close if abandoned."
            )

        if report.discussions.total_open < t["min_discussions"]:
            recs.append(
                "Seed new Discussions — post roadmap updates, RFCs, or "
                "community questions to drive engagement."
            )

        if report.discussions.unanswered > 0:
            recs.append(
                f"Answer {report.discussions.unanswered} open discussions "
                f"to maintain community health."
            )

        if report.commits.commits_last_week < t["min_weekly_commits"]:
            recs.append(
                "Increase commit frequency — merge pending PRs or start "
                "new feature branches."
            )

        if report.commits.active_contributors < t["min_contributors"]:
            recs.append(
                "Recruit contributors — post in community forums, tag "
                "Good First Issues, participate in hacktoberfest."
            )

        if report.ci.pass_rate < t["ci_pass_rate_min"]:
            recs.append(
                f"Fix CI failures — investigate failing workflows: "
                f"{', '.join(report.ci.failing_workflows[:3])}"
            )

        if not recs:
            recs.append("Repository is healthy! Keep up the good work. 🎉")

        return recs

    # ── Persistence ─────────────────────────────────────────────────────────

    def save_report(self, report: GuardianReport, path: str = ".github/GUARDIAN_REPORT.md") -> None:
        """Save health report to file for GitHub display."""
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(report.to_markdown(), encoding="utf-8")

    def save_json(self, report: GuardianReport, path: str = ".github/guardian_report.json") -> None:
        """Save health report as JSON for programmatic consumption."""
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="GitHub Operations Guardian v2.0 — Repository health scanner"
    )
    parser.add_argument("--repo", required=True, help="Repository in owner/name format")
    parser.add_argument("--output", default=".github/GUARDIAN_REPORT.md", help="Output markdown path")
    parser.add_argument("--json", default=".github/guardian_report.json", help="Output JSON path")
    parser.add_argument("--token", help="GitHub token (or set GITHUB_TOKEN env var)")
    args = parser.parse_args()

    owner, _, name = args.repo.partition("/")
    guardian = GitHubGuardian(
        repo_owner=owner,
        repo_name=name,
        gh_token=args.token,
    )
    report = guardian.run_full_scan()

    guardian.save_report(report, args.output)
    guardian.save_json(report, args.json)

    print(report.to_markdown())
    print(f"\nReport saved to {args.output} and {args.json}")

    # Exit code reflects status
    if report.status == GuardianStatus.CRITICAL:
        sys.exit(2)
    elif report.status == GuardianStatus.WARNING:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
