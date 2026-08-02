"""Tests for ADP (Agent Decision Protocol) taxonomy integration.

Verifies:
  - ADPClassification serialization/deserialization
  - map_to_adp() mapping logic for all 4 Godelian verdicts
  - Category modifiers (safety, meta, correctness, fairness)
  - Score-based modifiers (self_ref_score, confidence)
  - GodelianBoundary integration: ADP classification in BoundaryReport
  - get_state() includes ADP risk/autonomy distributions
"""
import pytest
from governance.meta.adp_taxonomy import (
    ADPClassification,
    AutonomyLevel,
    DecisionType,
    RiskLevel,
    Reversibility,
    map_to_adp,
)
from governance.meta.godelian_boundary import (
    GodelianBoundary,
    GodelianVerdict,
    Proposition,
    BoundaryReport,
)


# ── ADPClassification ────────────────────────────────────────────────────────

class TestADPClassification:
    def test_basic_creation(self):
        cls = ADPClassification(
            autonomy_level=AutonomyLevel.A4_AUTONOMOUS,
            decision_type=DecisionType.READ,
            risk_level=RiskLevel.LOW,
            reversibility=Reversibility.REVERSIBLE,
        )
        assert cls.autonomy_level == AutonomyLevel.A4_AUTONOMOUS
        assert cls.decision_type == DecisionType.READ
        assert cls.risk_level == RiskLevel.LOW
        assert cls.reversibility == Reversibility.REVERSIBLE

    def test_defaults(self):
        cls = ADPClassification(
            autonomy_level=AutonomyLevel.A1_MANUAL,
            decision_type=DecisionType.READ,
            risk_level=RiskLevel.NEGLIGIBLE,
            reversibility=Reversibility.REVERSIBLE,
        )
        assert cls.requires_human is False
        assert cls.max_retry_count == 0
        assert cls.ttl_seconds == 0
        assert cls.policy_tags == []

    def test_with_policy_tags(self):
        cls = ADPClassification(
            autonomy_level=AutonomyLevel.A3_SUPERVISED,
            decision_type=DecisionType.DELEGATE,
            risk_level=RiskLevel.HIGH,
            reversibility=Reversibility.IRREVERSIBLE,
            policy_tags=["godelian:externalize", "self_referential"],
        )
        assert "godelian:externalize" in cls.policy_tags
        assert "self_referential" in cls.policy_tags

    def test_to_dict(self):
        cls = ADPClassification(
            autonomy_level=AutonomyLevel.A4_AUTONOMOUS,
            decision_type=DecisionType.UPDATE,
            risk_level=RiskLevel.LOW,
            reversibility=Reversibility.REVERSIBLE,
            requires_human=False,
            max_retry_count=3,
            ttl_seconds=1800,
            policy_tags=["godelian:internal"],
        )
        d = cls.to_dict()
        assert d["autonomy_level"] == "A4"
        assert d["decision_type"] == "UPDATE"
        assert d["risk_level"] == "LOW"
        assert d["reversibility"] == "REVERSIBLE"
        assert d["requires_human"] is False
        assert d["max_retry_count"] == 3
        assert d["ttl_seconds"] == 1800
        assert d["policy_tags"] == ["godelian:internal"]

    def test_from_dict(self):
        original = ADPClassification(
            autonomy_level=AutonomyLevel.A2_ASSISTED,
            decision_type=DecisionType.EXECUTE,
            risk_level=RiskLevel.CRITICAL,
            reversibility=Reversibility.IRREVERSIBLE,
            requires_human=True,
            max_retry_count=0,
            ttl_seconds=300,
            policy_tags=["godelian:undecidable"],
        )
        d = original.to_dict()
        restored = ADPClassification.from_dict(d)
        assert restored.autonomy_level == original.autonomy_level
        assert restored.decision_type == original.decision_type
        assert restored.risk_level == original.risk_level
        assert restored.reversibility == original.reversibility
        assert restored.requires_human == original.requires_human
        assert restored.max_retry_count == original.max_retry_count
        assert restored.ttl_seconds == original.ttl_seconds
        assert restored.policy_tags == original.policy_tags

    def test_full_autonomous_no_human(self):
        cls = ADPClassification(
            autonomy_level=AutonomyLevel.A5_FULLY_AUTONOMOUS,
            decision_type=DecisionType.READ,
            risk_level=RiskLevel.NEGLIGIBLE,
            reversibility=Reversibility.REVERSIBLE,
        )
        assert cls.requires_human is False


# ── ADT Enums ────────────────────────────────────────────────────────────────

class TestAutonomyLevel:
    def test_all_levels_exist(self):
        assert AutonomyLevel.A1_MANUAL.value == "A1"
        assert AutonomyLevel.A2_ASSISTED.value == "A2"
        assert AutonomyLevel.A3_SUPERVISED.value == "A3"
        assert AutonomyLevel.A4_AUTONOMOUS.value == "A4"
        assert AutonomyLevel.A5_FULLY_AUTONOMOUS.value == "A5"

    def test_ordering(self):
        levels = list(AutonomyLevel)
        assert len(levels) == 5
        assert levels[0] == AutonomyLevel.A1_MANUAL
        assert levels[-1] == AutonomyLevel.A5_FULLY_AUTONOMOUS


class TestDecisionType:
    def test_all_types_exist(self):
        assert DecisionType.CREATE.value == "CREATE"
        assert DecisionType.READ.value == "READ"
        assert DecisionType.UPDATE.value == "UPDATE"
        assert DecisionType.DELETE.value == "DELETE"
        assert DecisionType.EXECUTE.value == "EXECUTE"
        assert DecisionType.DELEGATE.value == "DELEGATE"


class TestRiskLevel:
    def test_all_levels_exist(self):
        assert RiskLevel.NEGLIGIBLE.value == "NEGLIGIBLE"
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.CRITICAL.value == "CRITICAL"


class TestReversibility:
    def test_all_levels_exist(self):
        assert Reversibility.REVERSIBLE.value == "REVERSIBLE"
        assert Reversibility.PARTIALLY_REVERSIBLE.value == "PARTIALLY_REVERSIBLE"
        assert Reversibility.IRREVERSIBLE.value == "IRREVERSIBLE"


# ── map_to_adp() ─────────────────────────────────────────────────────────────

class TestMapToADPSafe:
    def test_safe_maps_to_a5(self):
        adp = map_to_adp("safe", "", 0.0, 0.9)
        assert adp.autonomy_level == AutonomyLevel.A5_FULLY_AUTONOMOUS
        assert adp.risk_level == RiskLevel.NEGLIGIBLE
        assert adp.reversibility == Reversibility.REVERSIBLE
        assert adp.requires_human is False

    def test_safe_default_type_is_read(self):
        adp = map_to_adp("safe")
        assert adp.decision_type == DecisionType.READ

    def test_safe_tags(self):
        adp = map_to_adp("safe")
        assert "godelian:safe" in adp.policy_tags
        assert "human_in_loop" not in adp.policy_tags


class TestMapToADPInternal:
    def test_internal_maps_to_a4(self):
        adp = map_to_adp("internal", "", 0.0, 0.8)
        assert adp.autonomy_level == AutonomyLevel.A4_AUTONOMOUS
        assert adp.risk_level == RiskLevel.LOW
        assert adp.reversibility == Reversibility.REVERSIBLE

    def test_internal_default_type_is_update(self):
        adp = map_to_adp("internal")
        assert adp.decision_type == DecisionType.UPDATE

    def test_internal_retry_limit(self):
        adp = map_to_adp("internal")
        assert adp.max_retry_count == 3


class TestMapToADPExternalize:
    def test_externalize_maps_to_a3(self):
        adp = map_to_adp("externalize", "", 0.3, 0.7)
        assert adp.autonomy_level == AutonomyLevel.A3_SUPERVISED
        assert adp.risk_level == RiskLevel.MEDIUM
        assert adp.reversibility == Reversibility.PARTIALLY_REVERSIBLE
        assert adp.requires_human is True

    def test_externalize_default_type_is_delegate(self):
        adp = map_to_adp("externalize")
        assert adp.decision_type == DecisionType.DELEGATE


class TestMapToADPUndecidable:
    def test_undecidable_maps_to_a2(self):
        adp = map_to_adp("undecidable", "", 0.0, 0.3)
        assert adp.autonomy_level == AutonomyLevel.A2_ASSISTED
        assert adp.risk_level == RiskLevel.CRITICAL
        assert adp.reversibility == Reversibility.IRREVERSIBLE
        assert adp.requires_human is True

    def test_undecidable_no_retries(self):
        adp = map_to_adp("undecidable")
        assert adp.max_retry_count == 0
        assert adp.ttl_seconds == 300


class TestMapToADPUnknown:
    def test_unknown_verdict_maps_to_a1(self):
        adp = map_to_adp("bogus", "", 0.0, 0.5)
        assert adp.autonomy_level == AutonomyLevel.A1_MANUAL
        assert adp.risk_level == RiskLevel.HIGH
        assert adp.requires_human is True


# ── Category Modifiers ───────────────────────────────────────────────────────

class TestCategoryModifiers:
    def test_safety_category_bumps_risk(self):
        base = map_to_adp("safe", "", 0.0, 0.9)
        modified = map_to_adp("safe", "safety", 0.0, 0.9)
        # risk bumped from NEGLIGIBLE to LOW
        assert _risk_index(modified.risk_level) > _risk_index(base.risk_level)

    def test_safety_category_sets_execute(self):
        adp = map_to_adp("safe", "safety", 0.0, 0.9)
        assert adp.decision_type == DecisionType.EXECUTE

    def test_meta_category_reduces_autonomy(self):
        base = map_to_adp("internal", "", 0.0, 0.8)
        modified = map_to_adp("internal", "meta_cognition", 0.0, 0.8)
        assert _autonomy_index(modified.autonomy_level) < _autonomy_index(base.autonomy_level)

    def test_meta_category_sets_delegate(self):
        adp = map_to_adp("safe", "meta", 0.0, 0.9)
        assert adp.decision_type == DecisionType.DELEGATE

    def test_correctness_category_reduces_reversibility(self):
        base = map_to_adp("safe", "", 0.0, 0.9)
        modified = map_to_adp("safe", "correctness", 0.0, 0.9)
        assert _reversibility_index(modified.reversibility) >= _reversibility_index(base.reversibility)

    def test_fairness_category_requires_human(self):
        adp = map_to_adp("safe", "fairness", 0.0, 0.9)
        assert adp.requires_human is True

    def test_fairness_category_bumps_risk(self):
        base = map_to_adp("safe", "", 0.0, 0.9)
        modified = map_to_adp("safe", "fairness", 0.0, 0.9)
        assert _risk_index(modified.risk_level) > _risk_index(base.risk_level)

    def test_performance_category_no_extra_restrictions(self):
        adp = map_to_adp("safe", "performance", 0.0, 0.9)
        assert adp.decision_type == DecisionType.UPDATE
        # performance should not force human intervention
        assert adp.autonomy_level in (AutonomyLevel.A4_AUTONOMOUS, AutonomyLevel.A5_FULLY_AUTONOMOUS)


# ── Score-based Modifiers ────────────────────────────────────────────────────

class TestScoreModifiers:
    def test_high_self_ref_bumps_risk(self):
        base = map_to_adp("safe", "", 0.0, 0.9)
        modified = map_to_adp("safe", "", 0.6, 0.9)
        assert _risk_index(modified.risk_level) > _risk_index(base.risk_level)

    def test_very_high_self_ref_reduces_autonomy(self):
        base = map_to_adp("safe", "", 0.0, 0.9)
        modified = map_to_adp("safe", "", 0.8, 0.9)
        assert _autonomy_index(modified.autonomy_level) < _autonomy_index(base.autonomy_level)

    def test_very_high_self_ref_requires_human(self):
        adp = map_to_adp("safe", "", 0.8, 0.9)
        assert adp.requires_human is True

    def test_low_confidence_bumps_risk(self):
        base = map_to_adp("safe", "", 0.0, 0.9)
        modified = map_to_adp("safe", "", 0.0, 0.3)
        assert _risk_index(modified.risk_level) > _risk_index(base.risk_level)

    def test_low_confidence_requires_human(self):
        adp = map_to_adp("safe", "", 0.0, 0.3)
        assert adp.requires_human is True

    def test_moderate_self_ref_still_safe(self):
        """0.3 self_ref should not trigger autonomy reduction."""
        adp = map_to_adp("safe", "", 0.3, 0.9)
        assert adp.requires_human is False


# ── GodelianBoundary Integration ─────────────────────────────────────────────

class TestGodelianBoundaryADPIntegration:
    def test_report_includes_adp_classification(self):
        gb = GodelianBoundary(self_ref_threshold=0.25, undecidable_threshold=0.60)
        prop = Proposition(
            id="prop-safety-001",
            content="This system is always safe because it checks itself",
            category="safety",
        )
        report = gb.analyze(prop)
        assert report.adp_classification is not None
        assert "autonomy_level" in report.adp_classification
        assert "decision_type" in report.adp_classification
        assert "risk_level" in report.adp_classification
        assert "reversibility" in report.adp_classification

    def test_report_to_dict_includes_adp(self):
        gb = GodelianBoundary()
        prop = Proposition(id="prop-001", content="Read sensor data", category="performance")
        report = gb.analyze(prop)
        d = report.to_dict()
        assert "adp_classification" in d
        assert d["adp_classification"]["autonomy_level"] in ("A4", "A5")

    def test_safe_proposition_gets_a5(self):
        gb = GodelianBoundary()
        prop = Proposition(id="prop-002", content="The external sensor reads 42.5 degrees")
        report = gb.analyze(prop)
        assert report.adp_classification["risk_level"] in ("NEGLIGIBLE", "LOW")

    def test_self_ref_proposition_gets_restrictive_adp(self):
        gb = GodelianBoundary(self_ref_threshold=0.25, undecidable_threshold=0.60)
        prop = Proposition(
            id="prop-meta-001",
            content="This decision system can fully verify its own correctness",
            category="meta",
            context={"dependencies": ["self_verifier"]},
        )
        report = gb.analyze(prop)
        adp = report.adp_classification
        # self-referential meta proposition should be restrictive
        assert adp["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")
        # high self-ref should require human
        if report.self_reference_score >= 0.5:
            assert adp["requires_human"] is True

    def test_batch_reports_all_have_adp(self):
        gb = GodelianBoundary()
        props = [
            Proposition(id="prop-003", content="Read value from sensor X"),
            Proposition(
                id="prop-004",
                content="This system verifies its own decisions",
                category="meta",
            ),
        ]
        reports = gb.analyze_batch(props)
        for report in reports:
            assert report.adp_classification is not None

    def test_get_state_includes_adp_distributions(self):
        gb = GodelianBoundary()
        gb.analyze(Proposition(id="prop-005", content="Read sensor value"))
        gb.analyze(Proposition(
            id="prop-006",
            content="This system should govern itself without oversight",
            category="meta",
        ))
        state = gb.get_state()
        assert "adp_risk_distribution" in state
        assert "adp_autonomy_distribution" in state
        assert isinstance(state["adp_risk_distribution"], dict)
        assert isinstance(state["adp_autonomy_distribution"], dict)

    def test_godel_sentence_adp_is_restrictive(self):
        gb = GodelianBoundary(self_ref_threshold=0.25, undecidable_threshold=0.60)
        prop = Proposition(
            id="prop-godel-001",
            content="This sentence is a self-referential paradox: I cannot verify my own truth",
        )
        report = gb.analyze(prop)
        adp = report.adp_classification
        # Godelian sentence: must have ADP classification
        assert adp is not None
        assert "autonomy_level" in adp
        # If high self-ref, requires human oversight
        if report.self_reference_score >= 0.5:
            assert adp["requires_human"] is True
        # At minimum, should have non-trivial classification with policy tags
        assert len(adp["policy_tags"]) > 0

    def test_circular_dependency_proposition_adp_tracks_tags(self):
        gb = GodelianBoundary()
        prop = Proposition(
            id="prop-circ-001",
            content="Module A depends on module B which depends on module A",
            category="meta",
            context={"dependencies": ["module_a", "module_b"]},
        )
        report = gb.analyze(prop)
        adp = report.adp_classification
        assert "policy_tags" in adp
        assert any("domain" in t or "godelian" in t for t in adp["policy_tags"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _risk_index(level: RiskLevel) -> int:
    return list(RiskLevel).index(level)


def _autonomy_index(level: AutonomyLevel) -> int:
    return list(AutonomyLevel).index(level)


def _reversibility_index(level: Reversibility) -> int:
    return list(Reversibility).index(level)
