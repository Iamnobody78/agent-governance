"""
Tests for GodelianBoundary
==========================
Comprehensive tests for GodelianBoundary, Proposition, BoundaryReport,
RealityBridgeRouter, and PropositionGenerator.
"""
import pytest

from governance.meta.godelian_boundary import (
    BoundaryReport,
    GodelianBoundary,
    GodelianVerdict,
    Proposition,
    PropositionGenerator,
    RealityBridgeRouter,
)


# ── Proposition Tests ────────────────────────────────────────────────────────

class TestProposition:
    def test_basic_creation(self):
        p = Proposition(id="p1", content="The system is safe")
        assert p.id == "p1"
        assert p.content == "The system is safe"
        assert p.category == ""
        assert p.assertions == []

    def test_full_creation(self):
        p = Proposition(
            id="p2",
            content="This agent never fails",
            category="safety",
            assertions=["agent is reliable", "agent is safe"],
            context={"domain": "testing"},
            source="test_module",
        )
        assert p.category == "safety"
        assert len(p.assertions) == 2
        assert p.context == {"domain": "testing"}

    def test_serialization(self):
        p = Proposition(
            id="p3",
            content="Test",
            category="perf",
            assertions=["a1"],
        )
        d = p.to_dict()
        assert d["id"] == "p3"
        assert d["content"] == "Test"
        assert d["category"] == "perf"
        assert d["assertions"] == ["a1"]


# ── GodelianBoundary Core Tests ────────────────────────────────────────────

class TestGodelianBoundaryBasic:
    def test_default_initialization(self):
        boundary = GodelianBoundary()
        assert boundary.self_ref_threshold == 0.25
        assert boundary.undecidable_threshold == 0.60

    def test_custom_thresholds(self):
        boundary = GodelianBoundary(
            self_ref_threshold=0.3,
            undecidable_threshold=0.7,
        )
        assert boundary.self_ref_threshold == 0.3
        assert boundary.undecidable_threshold == 0.7

    def test_reset(self):
        boundary = GodelianBoundary()
        prop = Proposition("p1", "This system is always safe")
        boundary.analyze(prop)
        assert len(boundary.history) == 1
        boundary.reset()
        assert len(boundary.history) == 0


class TestGodelianBoundarySafe:
    """Tests for non-self-referential (SAFE) propositions."""

    def test_simple_non_self_ref(self):
        boundary = GodelianBoundary()
        prop = Proposition("p1", "Calculate the sum of two numbers")
        report = boundary.analyze(prop)
        assert report.verdict == GodelianVerdict.SAFE
        assert report.self_reference_score < 0.1

    def test_external_world_fact(self):
        boundary = GodelianBoundary()
        prop = Proposition("p2", "The capital of France is Paris")
        report = boundary.analyze(prop)
        assert report.verdict == GodelianVerdict.SAFE

    def test_math_statement(self):
        boundary = GodelianBoundary()
        prop = Proposition("p3", "2 + 2 equals 4")
        report = boundary.analyze(prop)
        assert report.verdict == GodelianVerdict.SAFE

    def test_code_behavior_no_self_ref(self):
        boundary = GodelianBoundary()
        prop = Proposition("p4", "Function foo() returns an integer for typical inputs")
        report = boundary.analyze(prop)
        # Without "all", this should be safe or internal
        assert report.verdict in (GodelianVerdict.SAFE, GodelianVerdict.INTERNAL)


class TestGodelianBoundaryInternal:
    """Tests for INTERNAL verdict propositions."""

    def test_mild_self_reference(self):
        boundary = GodelianBoundary(self_ref_threshold=0.5)
        prop = Proposition("p1", "This module processes data correctly")
        report = boundary.analyze(prop)
        assert report.verdict in (GodelianVerdict.SAFE, GodelianVerdict.INTERNAL)


class TestGodelianBoundaryExternalize:
    """Tests for EXTERNALIZE verdict."""

    def test_strong_self_ref(self):
        boundary = GodelianBoundary()
        prop = Proposition("p1", "This system is always safe and never harms users")
        report = boundary.analyze(prop)
        # Should have high self-reference
        assert report.self_reference_score >= 0.1
        assert report.verdict in (
            GodelianVerdict.EXTERNALIZE,
            GodelianVerdict.UNDECIDABLE,
        )

    def test_self_modification_claim(self):
        boundary = GodelianBoundary()
        prop = Proposition(
            "p2",
            "The self-modification mechanism guarantees correctness",
            category="safety",
        )
        report = boundary.analyze(prop)
        assert report.self_reference_score > 0.0
        assert report.verdict != GodelianVerdict.SAFE

    def test_self_verification_claim(self):
        boundary = GodelianBoundary()
        prop = Proposition(
            "p3",
            "This self-audit system detects all its own errors",
            category="correctness",
        )
        report = boundary.analyze(prop)
        assert report.verdict in (
            GodelianVerdict.EXTERNALIZE,
            GodelianVerdict.UNDECIDABLE,
        )

    def test_recursive_improvement_claim(self):
        boundary = GodelianBoundary()
        prop = Proposition(
            "p4",
            "The self-evolution loop always improves the model without regression",
            category="performance",
        )
        report = boundary.analyze(prop)
        assert report.self_reference_score > 0.0

    def test_recommended_channel(self):
        boundary = GodelianBoundary()
        prop = Proposition("p5", "This system is always safe", category="safety")
        report = boundary.analyze(prop)
        if report.verdict == GodelianVerdict.EXTERNALIZE:
            assert report.recommended_channel == "simulation_channel"


class TestGodelianBoundaryUndecidable:
    """Tests for UNDECIDABLE verdict (true Gödel propositions)."""

    def test_godel_sentence(self):
        boundary = GodelianBoundary()
        prop = Proposition(
            "godel1",
            "This system can prove its own consistency and completeness",
            category="meta",
            assertions=[
                "The system is consistent",
                "The system can prove its own consistency",
            ],
        )
        report = boundary.analyze(prop)
        # A true Gödel sentence should be at least externalize
        assert report.verdict in (
            GodelianVerdict.EXTERNALIZE,
            GodelianVerdict.UNDECIDABLE,
        )

    def test_undecidable_recommends_all_channels(self):
        boundary = GodelianBoundary(undecidable_threshold=0.3)  # low threshold
        prop = Proposition(
            "godel2",
            "This self-modifying meta-meta-system always guarantees its own correctness",
        )
        report = boundary.analyze(prop)
        if report.verdict == GodelianVerdict.UNDECIDABLE:
            assert "human_review" in report.recommended_channel


class TestGodelianBoundaryCircularDependencies:
    """Tests for circular dependency detection."""

    def test_detect_simple_circular(self):
        boundary = GodelianBoundary()
        prop = Proposition(
            "p1",
            "The self_evolution module depends on meta_governance, "
            "and meta_governance depends on self_evolution",
        )
        report = boundary.analyze(prop)
        assert len(report.circular_dependencies) > 0

    def test_no_circular_for_linear(self):
        boundary = GodelianBoundary()
        prop = Proposition("p2", "Module A depends on B, B depends on C")
        report = boundary.analyze(prop)
        # No circular deps in this content
        assert len(report.circular_dependencies) == 0

    def test_meta_recursion_detected(self):
        boundary = GodelianBoundary()
        prop = Proposition("p3", "The meta-meta-meta governance layer")
        report = boundary.analyze(prop)
        # Should detect meta recursion
        assert len(report.circular_dependencies) > 0


# ── Batch Processing Tests ──────────────────────────────────────────────────

class TestBatchProcessing:
    def test_analyze_batch(self):
        boundary = GodelianBoundary()
        props = [
            Proposition("s1", "Calculate 1+1"),
            Proposition("s2", "This system is always safe"),
            Proposition("s3", "The capital of Germany is Berlin"),
        ]
        reports = boundary.analyze_batch(props)
        assert len(reports) == 3
        assert all(isinstance(r, BoundaryReport) for r in reports)

    def test_filter_externalizable(self):
        boundary = GodelianBoundary()
        props = [
            Proposition("safe1", "2+2=4"),
            Proposition("unsafe1", "This self-modifying system is always correct"),
        ]
        external = boundary.filter_externalizable(props)
        # Only the self-referential one should be externalized
        assert len(external) >= 1
        assert any(p.id == "unsafe1" for p, _ in external)

    def test_get_stats(self):
        boundary = GodelianBoundary()
        props = [
            Proposition("s1", "Simple math"),
            Proposition("s2", "This system is always safe"),
            Proposition("s3", "Another simple fact"),
        ]
        boundary.analyze_batch(props)
        stats = boundary.get_stats()
        assert stats["total_analyzed"] == 3
        assert isinstance(stats["avg_self_ref_score"], float)


# ── Report Tests ────────────────────────────────────────────────────────────

class TestBoundaryReport:
    def test_report_serialization(self):
        report = BoundaryReport(
            proposition_id="p1",
            verdict=GodelianVerdict.EXTERNALIZE,
            self_reference_score=0.7,
            circular_dependencies=["a↔b"],
            reasoning="Test reasoning",
            recommended_channel="simulation_channel",
            confidence=0.9,
        )
        d = report.to_dict()
        assert d["proposition_id"] == "p1"
        assert d["verdict"] == "externalize"
        assert d["self_reference_score"] == 0.7
        assert d["confidence"] == 0.9

    def test_report_has_reasoning(self):
        boundary = GodelianBoundary()
        prop = Proposition("p1", "This system is always safe")
        report = boundary.analyze(prop)
        assert len(report.reasoning) > 0

    def test_report_has_confidence(self):
        boundary = GodelianBoundary()
        prop = Proposition("p1", "This system is always safe")
        report = boundary.analyze(prop)
        assert 0 <= report.confidence <= 1.0


# ── RealityBridgeRouter Tests ──────────────────────────────────────────────

class TestRealityBridgeRouter:
    def test_router_initialization(self):
        router = RealityBridgeRouter()
        assert router.boundary is not None

    def test_route_safe_proposition_not_routed(self):
        router = RealityBridgeRouter()
        prop = Proposition("p1", "1+1=2")

        class MockBridge:
            pass

        result = router.route(prop, MockBridge())
        assert result["routed"] is False

    def test_route_externalize_routed(self):
        router = RealityBridgeRouter()
        prop = Proposition("p1", "This self-modifying system is always correct")

        class MockBridge:
            def simulation_channel(self, proposition):
                return "verified_externally"

        result = router.route(prop, MockBridge())
        assert result["routed"] is True
        assert "report" in result

    def test_route_missing_channel_graceful(self):
        router = RealityBridgeRouter()
        prop = Proposition("p1", "This system is always safe")

        class MockBridge:
            pass

        result = router.route(prop, MockBridge())
        if result["routed"]:
            assert "not available" in result.get("bridge_result", "")


# ── PropositionGenerator Tests ─────────────────────────────────────────────

class TestPropositionGenerator:
    def test_generates_propositions(self):
        gen = PropositionGenerator()
        props = gen.generate(count=5)
        assert len(props) == 5
        assert all(isinstance(p, Proposition) for p in props)

    def test_generates_all_by_default(self):
        gen = PropositionGenerator()
        props = gen.generate()
        assert len(props) > 0

    def test_generated_have_categories(self):
        gen = PropositionGenerator()
        props = gen.generate(count=3)
        for p in props:
            assert p.category in ("safety", "performance", "correctness", "fairness", "meta")

    def test_generate_undecidable(self):
        gen = PropositionGenerator()
        props = gen.generate_undecidable()
        assert len(props) > 0
        for p in props:
            assert p.category == "meta"
            # These should indeed be externalize/undecidable
            boundary = GodelianBoundary()
            report = boundary.analyze(p)
            assert report.verdict in (
                GodelianVerdict.EXTERNALIZE,
                GodelianVerdict.UNDECIDABLE,
            )

    def test_generated_have_unique_ids(self):
        gen = PropositionGenerator()
        props = gen.generate()
        ids = [p.id for p in props]
        assert len(ids) == len(set(ids))


# ── Edge Cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_proposition(self):
        boundary = GodelianBoundary()
        prop = Proposition("empty", "")
        report = boundary.analyze(prop)
        assert report.verdict == GodelianVerdict.SAFE

    def test_very_long_proposition(self):
        boundary = GodelianBoundary()
        long_text = "This system is always safe. " * 1000
        prop = Proposition("long", long_text)
        report = boundary.analyze(prop)
        assert report.self_reference_score >= 0.0

    def test_non_ascii_content(self):
        boundary = GodelianBoundary()
        prop = Proposition("unicode", "这个系统永远是安全的 This system is always safe")
        report = boundary.analyze(prop)
        assert report.verdict in (
            GodelianVerdict.EXTERNALIZE,
            GodelianVerdict.UNDECIDABLE,
        )

    def test_proposition_with_assertions(self):
        boundary = GodelianBoundary()
        prop = Proposition(
            "with_assertions",
            "Calculate values",
            assertions=[
                "This system always calculates correctly",
                "The algorithm never fails",
            ],
        )
        report = boundary.analyze(prop)
        # Assertions make it self-referential
        assert report.self_reference_score > 0.0


# ── Integration Scenario Tests ─────────────────────────────────────────────

class TestIntegrationScenarios:
    def test_pipeline_safe_to_externalize(self):
        """End-to-end: generate → analyze → route. Ensure at least one self-ref prop."""
        gen = PropositionGenerator()
        boundary = GodelianBoundary()
        router = RealityBridgeRouter(boundary)

        class MockBridge:
            pass

        props = gen.generate(count=10)
        # Add a guaranteed self-referential proposition
        props.append(Proposition(
            "guaranteed_self_ref",
            "This system is always safe and never fails",
            category="safety",
        ))

        reports = boundary.analyze_batch(props)

        verdicts = [r.verdict for r in reports]
        # With lowered threshold (0.25), most templates have some self-ref.
        # We only require that at least one is EXTERNALIZE/UNDECIDABLE.
        has_external = any(
            v in (GodelianVerdict.EXTERNALIZE, GodelianVerdict.UNDECIDABLE)
            for v in verdicts
        )
        assert has_external, (
            f"Expected some EXTERNALIZE/UNDECIDABLE verdicts, got: "
            f"{[v.value for v in verdicts]}"
        )

    def test_all_undecidables_are_self_referential(self):
        """所有 UNDECIDABLE 命题都必须有高自指度。"""
        gen = PropositionGenerator()
        boundary = GodelianBoundary(undecidable_threshold=0.5)

        for prop in gen.generate():
            report = boundary.analyze(prop)
            if report.verdict == GodelianVerdict.UNDECIDABLE:
                assert report.self_reference_score >= 0.1, (
                    f"Proposition '{prop.content}' marked UNDECIDABLE "
                    f"but self_ref_score={report.self_reference_score}"
                )

    def test_boundary_guard_loop(self):
        """模拟 MetaCognitiveLoop 中的使用场景。"""
        boundary = GodelianBoundary()
        gen = PropositionGenerator()

        # 模拟循环：每轮生成命题并检测边界
        for _ in range(5):
            props = gen.generate(count=3)
            external = boundary.filter_externalizable(props)

            # 对于 EXTERNALIZE 的命题，记录但不执行（因为需要 RealityBridge）
            for prop, report in external:
                assert report.verdict in (
                    GodelianVerdict.EXTERNALIZE,
                    GodelianVerdict.UNDECIDABLE,
                )
                assert report.recommended_channel != "internal"
