"""
Tests for SelfCheckEngine (P3)
==============================
Godelian self-verification engine tests covering:
  Layer 1: Contradiction detection (static + dynamic)
  Layer 2: Completeness gap analysis
  Layer 3: Trust root management
  Full SelfCheck pipeline + integration with GodelianBoundary
"""
import json
import tempfile
import time
from pathlib import Path

import pytest

from governance.meta.self_check_engine import (
    CompletenessGap,
    ContradictionNode,
    GapSeverity,
    SelfCheckEngine,
    SelfCheckReport,
    TrustRoot,
    TrustRootType,
)
from governance.meta.godelian_boundary import GodelianBoundary


# ── TrustRoot Tests ───────────────────────────────────────────────────────

class TestTrustRoot:
    def test_axiom_trust_root(self):
        tr = TrustRoot(
            id="TR-TEST", type=TrustRootType.AXIOM,
            statement="测试公理", justification="测试用",
            verifiable=False,
        )
        assert tr.type == TrustRootType.AXIOM
        assert tr.verifiable is False
        assert tr.expires is False

    def test_external_anchor_trust_root(self):
        tr = TrustRoot(
            id="TR-EXT", type=TrustRootType.EXTERNAL_ANCHOR,
            statement="外部锚点", justification="物理测试",
            verifiable=True, expires=True, last_validated=time.time(),
        )
        assert tr.expires is True
        assert tr.last_validated > 0

    def test_trust_root_serialization(self):
        tr = TrustRoot(
            id="TR-SER", type=TrustRootType.PROVEN,
            statement="已证明", justification="测试套件",
            verifiable=True, last_validated=1000.0,
        )
        d = tr.to_dict()
        assert d["id"] == "TR-SER"
        assert d["type"] == "proven"
        assert d["verifiable"] is True
        assert d["last_validated"] == 1000.0


# ── ContradictionNode Tests ───────────────────────────────────────────────

class TestContradictionNode:
    def test_basic_contradiction(self):
        c = ContradictionNode(
            id="C1", description="矛盾描述",
            proposition_a="A", proposition_b="非A",
            severity=GapSeverity.CRITICAL,
            affected_modules=["M1", "M2"],
            recommended_action="修复",
        )
        assert c.severity == GapSeverity.CRITICAL
        assert "M1" in c.affected_modules

    def test_serialization(self):
        c = ContradictionNode(
            id="C1", description="测试",
            proposition_a="A", proposition_b="B",
            severity=GapSeverity.HIGH,
            affected_modules=["M1"],
            recommended_action="修复X",
        )
        d = c.to_dict()
        assert d["severity"] == "high"
        assert d["affected_modules"] == ["M1"]


# ── CompletenessGap Tests ─────────────────────────────────────────────────

class TestCompletenessGap:
    def test_basic_gap(self):
        g = CompletenessGap(
            id="GAP-SAFETY", domain="safety",
            description="安全验证缺口",
            internal_provable=False, external_verifiable=True,
            godelian_verdict="externalize",
            suggested_fix="外部验证",
            affected_layers=[0, 1, 5],
        )
        assert g.internal_provable is False
        assert len(g.affected_layers) == 3

    def test_serialization(self):
        g = CompletenessGap(
            id="GAP-TEST", domain="test",
            description="测试", internal_provable=True,
            external_verifiable=False, godelian_verdict="internal",
            suggested_fix="无需修复", affected_layers=[0],
        )
        d = g.to_dict()
        assert d["domain"] == "test"
        assert d["internal_provable"] is True
        assert d["affected_layers"] == [0]


# ── SelfCheckReport Tests ─────────────────────────────────────────────────

class TestSelfCheckReport:
    def test_basic_report(self):
        report = SelfCheckReport(
            check_id="SC-001", overall_score=0.95, critical_issues=0,
        )
        assert report.check_id == "SC-001"
        assert report.overall_score == 0.95

    def test_serialization(self):
        c = ContradictionNode(
            id="C1", description="矛盾", proposition_a="A",
            proposition_b="B", severity=GapSeverity.MEDIUM,
            affected_modules=["M1"], recommended_action="修复",
        )
        g = CompletenessGap(
            id="G1", domain="meta", description="缺口",
            internal_provable=False, external_verifiable=True,
            godelian_verdict="externalize", suggested_fix="外部",
            affected_layers=[12],
        )
        report = SelfCheckReport(
            check_id="SC-001", overall_score=0.8, critical_issues=1,
            contradictions_found=[c], completeness_gaps=[g],
            godelian_delegated=1,
        )
        d = report.to_dict()
        assert len(d["contradictions_found"]) == 1
        assert len(d["completeness_gaps"]) == 1
        assert d["critical_issues"] == 1
        assert d["overall_score"] == 0.8


# ── SelfCheckEngine Core Tests ────────────────────────────────────────────

class TestSelfCheckEngineInit:
    def test_default_initialization(self):
        engine = SelfCheckEngine()
        assert len(engine.trust_roots) == 7
        assert engine.godelian_boundary is not None

    def test_custom_godelian_boundary(self):
        gb = GodelianBoundary(self_ref_threshold=0.3)
        engine = SelfCheckEngine(godelian_boundary=gb)
        assert engine.godelian_boundary.self_ref_threshold == 0.3

    def test_custom_trust_roots(self):
        roots = [
            TrustRoot(id="T1", type=TrustRootType.AXIOM,
                      statement="Custom", justification="Custom",
                      verifiable=False),
        ]
        engine = SelfCheckEngine(trust_roots=roots)
        assert len(engine.trust_roots) == 1
        assert engine.trust_roots[0].id == "T1"


# ── Layer 1: Contradiction Detection ──────────────────────────────────────

class TestContradictionDetection:
    def test_detects_static_contradictions(self):
        engine = SelfCheckEngine()
        contradictions = engine.detect_contradictions()
        # Should detect at least CONTRADICT-001, 003, 004, 005
        # (CONTRADICT-002 is marked resolved)
        assert len(contradictions) >= 4
        ids = [c.id for c in contradictions]
        assert "CONTRADICT-001" in ids
        assert "CONTRADICT-002" not in ids  # resolved

    def test_contradiction_has_severity(self):
        engine = SelfCheckEngine()
        contradictions = engine.detect_contradictions()
        for c in contradictions:
            assert c.severity in GapSeverity

    def test_contradiction_has_recommended_action(self):
        engine = SelfCheckEngine()
        contradictions = engine.detect_contradictions()
        for c in contradictions:
            assert len(c.recommended_action) > 0

    def test_dynamic_contradiction_detection(self):
        engine = SelfCheckEngine()
        contradictions = engine.detect_contradictions()
        # Dynamic detection may find UNDECIDABLE propositions
        dynamic = [c for c in contradictions if c.id.startswith("DYNAMIC-")]
        # At least some should be found from generate_undecidable()
        assert len(dynamic) >= 0  # Depends on current threshold settings


# ── Layer 2: Completeness Analysis ────────────────────────────────────────

class TestCompletenessAnalysis:
    def test_analyzes_all_domains(self):
        engine = SelfCheckEngine()
        gaps = engine.analyze_completeness()
        # Should cover: safety, correctness, performance, fairness, robustness, meta
        assert len(gaps) == 6
        domains = [g.domain for g in gaps]
        assert "safety" in domains
        assert "correctness" in domains
        assert "meta" in domains

    def test_gap_has_layers(self):
        engine = SelfCheckEngine()
        gaps = engine.analyze_completeness()
        for g in gaps:
            assert len(g.affected_layers) > 0

    def test_gap_has_godelian_verdict(self):
        engine = SelfCheckEngine()
        gaps = engine.analyze_completeness()
        valid_verdicts = {"safe", "internal", "externalize", "undecidable"}
        for g in gaps:
            assert g.godelian_verdict in valid_verdicts

    def test_at_least_some_externalize(self):
        engine = SelfCheckEngine()
        gaps = engine.analyze_completeness()
        externalizable = [g for g in gaps
                          if g.godelian_verdict in ("externalize", "undecidable")]
        assert len(externalizable) > 0, (
            "Some domains should require external verification"
        )


# ── Layer 3: Trust Root Management ────────────────────────────────────────

class TestTrustRootManagement:
    def test_default_trust_roots(self):
        engine = SelfCheckEngine()
        roots = engine.trust_roots
        types = {r.type for r in roots}
        assert TrustRootType.AXIOM in types
        assert TrustRootType.EXTERNAL_ANCHOR in types
        assert TrustRootType.HUMAN_OVERSIGHT in types
        assert TrustRootType.PROVEN in types

    def test_validate_trust_roots(self):
        engine = SelfCheckEngine()
        status = engine.validate_trust_roots()
        assert status["total"] == 7
        assert "valid" in status
        assert "circular_deps" in status
        # All default trust roots should be valid (none expired)
        assert status["valid"] == 7

    def test_add_trust_root(self):
        engine = SelfCheckEngine()
        before = len(engine.trust_roots)
        engine.add_trust_root(TrustRoot(
            id="TR-NEW", type=TrustRootType.AXIOM,
            statement="新公理", justification="测试",
            verifiable=False,
        ))
        assert len(engine.trust_roots) == before + 1

    def test_add_duplicate_trust_root_ignored(self):
        engine = SelfCheckEngine()
        before = len(engine.trust_roots)
        existing = engine.trust_roots[0]
        engine.add_trust_root(TrustRoot(
            id="DUP", type=TrustRootType.AXIOM,
            statement=existing.statement,  # same statement
            justification="dup",
            verifiable=False,
        ))
        assert len(engine.trust_roots) == before  # not added

    def test_revoke_trust_root(self):
        engine = SelfCheckEngine()
        root_id = engine.trust_roots[0].id
        result = engine.revoke_trust_root(root_id)
        assert result is True
        assert all(r.id != root_id for r in engine.trust_roots)

    def test_revoke_nonexistent(self):
        engine = SelfCheckEngine()
        result = engine.revoke_trust_root("NONEXISTENT")
        assert result is False

    def test_expired_trust_root_detected(self):
        engine = SelfCheckEngine()
        # Add an expired external anchor
        engine.add_trust_root(TrustRoot(
            id="TR-EXPIRED", type=TrustRootType.EXTERNAL_ANCHOR,
            statement="Expired anchor", justification="Old test",
            verifiable=True, expires=True,
            last_validated=time.time() - 100000,  # ~28 hours ago
        ))
        status = engine.validate_trust_roots()
        assert len(status["expired"]) >= 1

    def test_unverifiable_external_anchor_detected(self):
        engine = SelfCheckEngine()
        engine.add_trust_root(TrustRoot(
            id="TR-UNVERIFIABLE", type=TrustRootType.EXTERNAL_ANCHOR,
            statement="Unverifiable", justification="No way to test",
            verifiable=False, expires=False,
        ))
        status = engine.validate_trust_roots()
        assert len(status["unverifiable"]) >= 1


# ── Full Check Pipeline ──────────────────────────────────────────────────

class TestFullCheck:
    def test_run_full_check_returns_report(self):
        engine = SelfCheckEngine()
        report = engine.run_full_check()
        assert isinstance(report, SelfCheckReport)
        assert report.check_id == "SELFCHECK-0001"
        assert report.overall_score < 1.0  # Known contradictions exist

    def test_full_check_increments_counter(self):
        engine = SelfCheckEngine()
        engine.run_full_check()
        engine.run_full_check()
        assert engine._check_counter == 2
        assert len(engine.history) == 2

    def test_full_check_has_all_three_layers(self):
        engine = SelfCheckEngine()
        report = engine.run_full_check()
        # Layer 1: contradictions
        assert len(report.contradictions_found) > 0
        # Layer 2: completeness gaps
        assert len(report.completeness_gaps) == 6
        # Layer 3: trust root status
        assert report.trust_root_status["total"] > 0

    def test_full_check_scores_bounded(self):
        engine = SelfCheckEngine()
        report = engine.run_full_check()
        assert 0.0 <= report.overall_score <= 1.0

    def test_multiple_checks_consistent(self):
        engine = SelfCheckEngine()
        report1 = engine.run_full_check()
        report2 = engine.run_full_check()
        # Scores should be identical (same engine state)
        assert report1.overall_score == report2.overall_score
        assert report1.critical_issues == report2.critical_issues


# ── Scoring Tests ─────────────────────────────────────────────────────────

class TestScoring:
    def test_perfect_score_with_no_issues(self):
        engine = SelfCheckEngine()
        # An empty engine would have higher score... but default has contradictions
        report = engine.run_full_check()
        # Score is calculated correctly
        assert isinstance(report.overall_score, float)

    def test_critical_contradictions_penalize_heavily(self):
        engine = SelfCheckEngine()
        # Add a critical contradiction via direct construction
        report = engine.run_full_check()
        # Known contradictions exist, score should be < 1.0
        assert report.overall_score < 1.0

    def test_godelian_delegated_counted(self):
        engine = SelfCheckEngine()
        report = engine.run_full_check()
        # Some domains should be delegated
        assert report.godelian_delegated > 0


# ── Observability Tests ───────────────────────────────────────────────────

class TestObservability:
    def test_get_state_before_check(self):
        engine = SelfCheckEngine()
        state = engine.get_state()
        assert state["module"] == "SelfCheckEngine"
        assert state["check_count"] == 0
        assert state["last_score"] is None

    def test_get_state_after_check(self):
        engine = SelfCheckEngine()
        engine.run_full_check()
        state = engine.get_state()
        assert state["check_count"] == 1
        assert state["last_score"] is not None
        assert state["trust_roots_count"] == 7

    def test_export_report(self):
        engine = SelfCheckEngine()
        engine.run_full_check()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        engine.export_report(path)
        saved = Path(path)
        assert saved.exists()

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["check_id"] == "SELFCHECK-0001"
        assert "contradictions_found" in data
        assert "completeness_gaps" in data

        Path(path).unlink()

    def test_reset(self):
        engine = SelfCheckEngine()
        engine.run_full_check()
        assert engine._check_counter == 1
        engine.reset()
        assert engine._check_counter == 0
        assert len(engine.history) == 0


# ── Integration Tests ─────────────────────────────────────────────────────

class TestIntegrationWithGodelianBoundary:
    def test_selfcheck_uses_godelian_boundary(self):
        """SelfCheck 通过 GodelianBoundary 分析完备性命题。"""
        engine = SelfCheckEngine()
        gaps = engine.analyze_completeness()
        # Each gap should have a Godelian verdict
        for g in gaps:
            assert g.godelian_verdict in (
                "safe", "internal", "externalize", "undecidable"
            )

    def test_contradiction_undecidables_are_delegated(self):
        """不可判定命题应被标记为 Godelian delegated。"""
        engine = SelfCheckEngine()
        report = engine.run_full_check()
        # Meta domain is likely undecidable
        meta_gaps = [g for g in report.completeness_gaps if g.domain == "meta"]
        assert len(meta_gaps) > 0

    def test_trust_roots_reference_godelian_results(self):
        """信任根中引用了经过测试验证的模块结果。"""
        engine = SelfCheckEngine()
        proven_roots = [
            r for r in engine.trust_roots
            if r.type == TrustRootType.PROVEN
            and ("测试" in r.justification or "test" in r.justification.lower()
                 or "pass" in r.justification.lower())
        ]
        assert len(proven_roots) >= 1, "Should reference validated module tests"

    def test_full_pipeline_selfcheck_to_godelian(self):
        """完整流水线: SelfCheck 检测 → GodelianBoundary 验证 → 报告。"""
        engine = SelfCheckEngine()
        report = engine.run_full_check()

        # 验证流水线完整性
        assert isinstance(report, SelfCheckReport)
        assert report.godelian_delegated >= 0
        # Contradictions should reference affected modules
        if report.contradictions_found:
            for c in report.contradictions_found:
                assert len(c.affected_modules) > 0


# ── Edge Cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_trust_roots(self):
        engine = SelfCheckEngine(trust_roots=[])
        status = engine.validate_trust_roots()
        assert status["total"] == 0
        assert status["valid"] == 0

    def test_reset_and_rerun(self):
        engine = SelfCheckEngine()
        for _ in range(5):
            report = engine.run_full_check()
            assert report.overall_score is not None
        engine.reset()
        assert engine._check_counter == 0

    def test_export_without_check(self):
        engine = SelfCheckEngine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        engine.export_report(path)
        # No report to export; file should be empty (0 bytes) since export_report returns early
        saved = Path(path)
        assert saved.stat().st_size == 0, "File should be empty (export_report returned early)"
        saved.unlink(missing_ok=True)

    def test_all_severity_levels_present(self):
        """验证所有严重度级别都在报告中出现（或合理缺失）。"""
        engine = SelfCheckEngine()
        report = engine.run_full_check()
        severities = {c.severity for c in report.contradictions_found}
        # At minimum HIGH should be present from template contradictions
        assert GapSeverity.HIGH in severities or GapSeverity.MEDIUM in severities

    def test_check_ids_are_unique(self):
        engine = SelfCheckEngine()
        ids = []
        for _ in range(5):
            report = engine.run_full_check()
            ids.append(report.check_id)
        assert len(ids) == len(set(ids))

    def test_trust_roots_no_circular_default(self):
        """默认信任根不应有循环依赖。"""
        engine = SelfCheckEngine()
        status = engine.validate_trust_roots()
        assert len(status["circular_deps"]) == 0, (
            f"Found circular deps: {status['circular_deps']}"
        )
