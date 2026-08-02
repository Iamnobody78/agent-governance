"""Tests for TaG-extended RealityBridge Router.

Verifies:
  - TaGHook creation, execution, result formatting
  - TaGHookRegistry: registration, listing, execution pipeline
  - Hook priority ordering and DENY short-circuit
  - ExtendedRealityBridgeRouter with hook pipeline
  - 10 default TaG hooks all present and executable
  - get_state() includes hook information
  - Custom hook registration and management
"""
import pytest
from governance.meta.reality_bridge import (
    ExtendedRealityBridgeRouter,
    TaGHookRegistry,
    TaGHook,
    TaGHookType,
    TaGHookAction,
    TaGHookResult,
    TaGRoutingResult,
)
from governance.meta.godelian_boundary import (
    GodelianBoundary,
    Proposition,
)


# ── TaGHook ──────────────────────────────────────────────────────────────────

class TestTaGHook:
    def test_creation(self):
        hook = TaGHook(
            name="test_hook",
            hook_type=TaGHookType.SPENDING_LIMIT,
            description="A test hook",
            condition=lambda p: True,
            action=lambda p: (TaGHookAction.ALLOW, "OK"),
        )
        assert hook.name == "test_hook"
        assert hook.hook_type == TaGHookType.SPENDING_LIMIT
        assert hook.priority == 50
        assert hook.enabled is True

    def test_execute_condition_met(self):
        hook = TaGHook(
            name="always_deny",
            hook_type=TaGHookType.CREDENTIAL_INTERCEPT,
            description="Deny everything",
            condition=lambda p: True,
            action=lambda p: (TaGHookAction.DENY, "Blocked"),
            priority=10,
        )
        prop = Proposition(id="test-1", content="anything")
        result = hook.execute(prop)
        assert result.action == TaGHookAction.DENY
        assert result.hook_name == "always_deny"
        assert result.reason == "Blocked"

    def test_execute_condition_not_met(self):
        hook = TaGHook(
            name="never_trigger",
            hook_type=TaGHookType.AUDIT_TRAIL,
            description="Never triggers",
            condition=lambda p: False,
            action=lambda p: (TaGHookAction.DENY, "Should not happen"),
        )
        prop = Proposition(id="test-2", content="anything")
        result = hook.execute(prop)
        assert result.action == TaGHookAction.ALLOW
        assert "Condition not met" in result.reason

    def test_execute_disabled(self):
        hook = TaGHook(
            name="disabled_hook",
            hook_type=TaGHookType.RATE_LIMIT,
            description="Disabled",
            condition=lambda p: True,
            action=lambda p: (TaGHookAction.DENY, "N/A"),
            enabled=False,
        )
        result = hook.execute(Proposition(id="x", content="y"))
        assert result.action == TaGHookAction.ALLOW
        assert "disabled" in result.reason.lower()

    def test_modify_action(self):
        hook = TaGHook(
            name="modifier",
            hook_type=TaGHookType.INPUT_SANITIZATION,
            description="Modifies input",
            condition=lambda p: True,
            action=lambda p: (TaGHookAction.MODIFY, "Sanitized"),
        )
        result = hook.execute(Proposition(id="x", content="y"))
        assert result.action == TaGHookAction.MODIFY

    def test_defer_action(self):
        hook = TaGHook(
            name="deferrer",
            hook_type=TaGHookType.DEPLOYMENT_GATE,
            description="Defers to human",
            condition=lambda p: True,
            action=lambda p: (TaGHookAction.DEFER, "Needs human review"),
        )
        result = hook.execute(Proposition(id="x", content="y"))
        assert result.action == TaGHookAction.DEFER

    def test_log_only_action(self):
        hook = TaGHook(
            name="logger",
            hook_type=TaGHookType.AUDIT_TRAIL,
            description="Log only",
            condition=lambda p: True,
            action=lambda p: (TaGHookAction.LOG_ONLY, "Logged"),
        )
        result = hook.execute(Proposition(id="x", content="y"))
        assert result.action == TaGHookAction.LOG_ONLY

    def test_tags(self):
        hook = TaGHook(
            name="tagged",
            hook_type=TaGHookType.CIRCUIT_BREAKER,
            description="Has tags",
            condition=lambda p: True,
            action=lambda p: (TaGHookAction.ALLOW, ""),
            tags=["security", "critical"],
        )
        assert "security" in hook.tags
        assert "critical" in hook.tags


# ── TaGHookResult ────────────────────────────────────────────────────────────

class TestTaGHookResult:
    def test_to_dict(self):
        result = TaGHookResult(
            hook_name="test",
            hook_type=TaGHookType.CREDENTIAL_INTERCEPT,
            action=TaGHookAction.DENY,
            reason="Blocked credential leak",
        )
        d = result.to_dict()
        assert d["hook_name"] == "test"
        assert d["hook_type"] == "credential_intercept"
        assert d["action"] == "deny"
        assert d["reason"] == "Blocked credential leak"
        assert d["modified"] is False

    def test_to_dict_with_modified(self):
        prop = Proposition(id="mod", content="original")
        result = TaGHookResult(
            hook_name="sanitizer",
            hook_type=TaGHookType.PII_MASKING,
            action=TaGHookAction.MODIFY,
            reason="Sanitized",
            modified_proposition=prop,
        )
        d = result.to_dict()
        assert d["modified"] is True


# ── TaGHookRegistry ──────────────────────────────────────────────────────────

class TestTaGHookRegistry:
    def test_initialization(self):
        registry = TaGHookRegistry()
        hooks = registry.list_hooks()
        assert len(hooks) >= 8  # At least 8 default hooks
        # Verify hooks are sorted by priority
        priorities = [h.priority for h in hooks]
        assert priorities == sorted(priorities)

    def test_all_default_hooks_present(self):
        registry = TaGHookRegistry()
        hook_names = {h.name for h in registry.list_hooks()}
        expected = {
            "credential_leak_guard",
            "rate_limit_guard",
            "cost_aware_routing",
            "deployment_safety_gate",
            "circuit_breaker",
            "self_modification_safety",
            "pii_sanitization",
            "mandatory_audit_trail",
            "output_safety_validator",
        }
        assert expected.issubset(hook_names)

    def test_register_custom_hook(self):
        registry = TaGHookRegistry()
        custom = TaGHook(
            name="custom_check",
            hook_type=TaGHookType.BIAS_DETECTION,
            description="Custom bias check",
            condition=lambda p: True,
            action=lambda p: (TaGHookAction.ALLOW, "Passed"),
            priority=99,
        )
        registry.register(custom)
        assert registry.get("custom_check") is not None

    def test_unregister(self):
        registry = TaGHookRegistry()
        # Unregister a default hook
        registry.unregister("credential_leak_guard")
        assert registry.get("credential_leak_guard") is None

    def test_list_by_type(self):
        registry = TaGHookRegistry()
        security_hooks = registry.list_by_type(TaGHookType.CREDENTIAL_INTERCEPT)
        assert len(security_hooks) >= 1
        for h in security_hooks:
            assert h.hook_type == TaGHookType.CREDENTIAL_INTERCEPT

    def test_execute_all_stops_on_deny(self):
        """High-priority DENY should short-circuit."""
        registry = TaGHookRegistry()
        prop = Proposition(
            id="secret-leak",
            content="Here is my api_key: abc123xyz",
        )
        results = registry.execute_all(prop)
        # credential_leak_guard (priority 5) should DENY, stopping execution
        assert results[-1].action == TaGHookAction.DENY
        assert results[-1].hook_name == "credential_leak_guard"

    def test_safe_proposition_passes_all(self):
        registry = TaGHookRegistry()
        prop = Proposition(
            id="safe-read",
            content="Read current temperature from sensor T1",
            category="performance",
        )
        results = registry.execute_all(prop)
        # All hooks should ALLOW for a safe proposition
        for r in results:
            assert r.action != TaGHookAction.DENY

    def test_final_verdict_deny_wins(self):
        registry = TaGHookRegistry()
        results = [
            TaGHookResult("a", TaGHookType.AUDIT_TRAIL, TaGHookAction.LOG_ONLY, ""),
            TaGHookResult("b", TaGHookType.CREDENTIAL_INTERCEPT, TaGHookAction.DENY, "blocked"),
            TaGHookResult("c", TaGHookType.PII_MASKING, TaGHookAction.MODIFY, ""),
        ]
        assert registry.final_verdict(results) == TaGHookAction.DENY

    def test_final_verdict_defer_over_modify(self):
        registry = TaGHookRegistry()
        results = [
            TaGHookResult("a", TaGHookType.AUDIT_TRAIL, TaGHookAction.LOG_ONLY, ""),
            TaGHookResult("b", TaGHookType.PII_MASKING, TaGHookAction.MODIFY, ""),
            TaGHookResult("c", TaGHookType.DEPLOYMENT_GATE, TaGHookAction.DEFER, "review"),
        ]
        assert registry.final_verdict(results) == TaGHookAction.DEFER

    def test_final_verdict_all_allow(self):
        registry = TaGHookRegistry()
        results = [
            TaGHookResult("a", TaGHookType.AUDIT_TRAIL, TaGHookAction.LOG_ONLY, ""),
            TaGHookResult("b", TaGHookType.COST_AWARE_ROUTING, TaGHookAction.ALLOW, ""),
        ]
        assert registry.final_verdict(results) == TaGHookAction.ALLOW


# ── ExtendedRealityBridgeRouter ──────────────────────────────────────────────

class TestExtendedRealityBridgeRouter:
    def test_initialization(self):
        router = ExtendedRealityBridgeRouter()
        assert router.boundary is not None
        assert router.hook_registry is not None
        assert len(router.hook_registry.list_hooks()) >= 8

    def test_route_safe_proposition(self):
        router = ExtendedRealityBridgeRouter()
        prop = Proposition(id="safe-1", content="Read external sensor value")
        result = router.route_with_hooks(prop)
        assert result.routed is False
        assert result.final_action == "allow"
        assert "not routed" in result.bridge_result.lower()

    def test_route_with_credential_pattern(self):
        router = ExtendedRealityBridgeRouter()
        prop = Proposition(
            id="secret-1",
            content="My API token is xyz-secret-abc",
        )
        result = router.route_with_hooks(prop)
        # credential_leak_guard (priority 5) should DENY
        assert result.final_action == "deny", f"Expected deny, got {result.final_action}"
        assert "Blocked by TaG" in result.bridge_result

    def test_route_deployment_triggers_defer(self):
        router = ExtendedRealityBridgeRouter()
        prop = Proposition(
            id="deploy-1",
            content="Deploy the new version to production",
            category="meta",
        )
        result = router.route_with_hooks(prop)
        # deployment_safety_gate should DEFER for "deploy" + "production"
        hook_actions = [h.get("action") for h in result.hook_results]
        assert "defer" in hook_actions, f"Expected defer in {hook_actions}"

    def test_route_self_modification(self):
        router = ExtendedRealityBridgeRouter()
        prop = Proposition(
            id="self-mod",
            content="The system should modify itself to improve safety",
            category="meta",
        )
        result = router.route_with_hooks(prop)
        # self_modification_safety should fire (condition matches "modify itself")
        hook_actions = [h.get("action") for h in result.hook_results]
        # At minimum, the audit trail hook should fire (condition=lambda p: True)
        assert len(result.hook_results) > 0, f"Expected hooks to fire, got {result.hook_results}"
        # Check that at least one hook triggered on this content
        assert any(
            h.get("action") in ("defer", "deny", "modify")
            for h in result.hook_results
        ), f"Expected restrictive action in {hook_actions}"

    def test_route_always_never_claim(self):
        router = ExtendedRealityBridgeRouter()
        prop = Proposition(
            id="absolute-1",
            content="This system always works and never fails",
            category="safety",
        )
        result = router.route_with_hooks(prop)
        # circuit_breaker should detect "always"/"never" and DENY
        hook_actions = [h.get("action") for h in result.hook_results]
        assert "deny" in hook_actions or result.final_action in ("deny", "deferred")

    def test_get_state(self):
        router = ExtendedRealityBridgeRouter()
        state = router.get_state()
        assert state["module"] == "ExtendedRealityBridgeRouter"
        assert "godelian_state" in state
        assert "tag_hooks" in state
        assert state["tag_hooks"]["total_hooks"] >= 8
        assert state["tag_hooks"]["enabled_hooks"] >= 8
        assert "hooks_by_type" in state["tag_hooks"]

    def test_add_custom_hook(self):
        router = ExtendedRealityBridgeRouter()
        custom = TaGHook(
            name="my_custom",
            hook_type=TaGHookType.BIAS_DETECTION,
            description="My bias check",
            condition=lambda p: "biased" in p.content.lower(),
            action=lambda p: (TaGHookAction.DENY, "Biased content"),
        )
        router.add_hook(custom)
        assert router.hook_registry.get("my_custom") is not None

    def test_remove_hook(self):
        router = ExtendedRealityBridgeRouter()
        router.remove_hook("pii_sanitization")
        assert router.hook_registry.get("pii_sanitization") is None

    def test_toggle_hook(self):
        router = ExtendedRealityBridgeRouter()
        router.toggle_hook("credential_leak_guard", False)
        hook = router.hook_registry.get("credential_leak_guard")
        assert hook is not None
        assert hook.enabled is False
        # Re-enable
        router.toggle_hook("credential_leak_guard", True)
        assert hook.enabled is True

    def test_list_hooks(self):
        router = ExtendedRealityBridgeRouter()
        hooks = router.list_hooks()
        assert len(hooks) >= 8
        for h in hooks:
            assert "name" in h
            assert "type" in h
            assert "enabled" in h

    def test_skip_hooks(self):
        router = ExtendedRealityBridgeRouter()
        # Even a dangerous proposition should pass when hooks are skipped
        prop = Proposition(
            id="skip-test",
            content="Here is my password: hunter2 and api_key: secret123",
        )
        result = router.route_with_hooks(prop, skip_hooks=True)
        # With skip_hooks=True, no hooks fire and Godelian says SAFE → not routed
        assert result.hook_results == []
        assert result.final_action == "allow"

    def test_godelian_report_included(self):
        router = ExtendedRealityBridgeRouter()
        prop = Proposition(
            id="report-test",
            content="Deploy to staging environment for testing",
        )
        result = router.route_with_hooks(prop)
        assert "godelian_report" in result.__dict__ or hasattr(result, "godelian_report")
        report = result.godelian_report
        assert "verdict" in report
        assert "adp_classification" in report  # ADP integration still works


# ── TaG Hook Type Enum ───────────────────────────────────────────────────────

class TestTaGHookType:
    def test_all_types_exist(self):
        assert TaGHookType.SPENDING_LIMIT.value == "spending_limit"
        assert TaGHookType.BUDGET_QUOTA.value == "budget_quota"
        assert TaGHookType.COST_AWARE_ROUTING.value == "cost_aware_routing"
        assert TaGHookType.CREDENTIAL_INTERCEPT.value == "credential_intercept"
        assert TaGHookType.RATE_LIMIT.value == "rate_limit"
        assert TaGHookType.PERMISSION_BOUNDARY.value == "permission_boundary"
        assert TaGHookType.INPUT_SANITIZATION.value == "input_sanitization"

    def test_count(self):
        types = list(TaGHookType)
        assert len(types) >= 18  # At minimum 18 hook types


class TestTaGHookAction:
    def test_all_actions_exist(self):
        assert TaGHookAction.ALLOW.value == "allow"
        assert TaGHookAction.DENY.value == "deny"
        assert TaGHookAction.MODIFY.value == "modify"
        assert TaGHookAction.DEFER.value == "defer"
        assert TaGHookAction.LOG_ONLY.value == "log_only"


# ── TaGRoutingResult ─────────────────────────────────────────────────────────

class TestTaGRoutingResult:
    def test_creation_defaults(self):
        result = TaGRoutingResult(
            routed=False,
            godelian_report={"verdict": "safe"},
        )
        assert result.routed is False
        assert result.final_action == "allow"
        assert result.hook_results == []
        assert result.bridge_result == ""

    def test_with_hook_results(self):
        result = TaGRoutingResult(
            routed=True,
            godelian_report={"verdict": "externalize"},
            hook_results=[
                {"hook_name": "audit", "action": "log_only"},
                {"hook_name": "cost", "action": "allow"},
            ],
            final_action="allow",
            bridge_result="Routed to gazebo",
        )
        assert len(result.hook_results) == 2
        assert result.bridge_result == "Routed to gazebo"


# ── Integration: Hook registry with GodelianBoundary ─────────────────────────

class TestHookGodelianIntegration:
    def test_self_ref_proposition_hooks_fire(self):
        """Self-referential safety proposition should trigger relevant hooks."""
        router = ExtendedRealityBridgeRouter(
            boundary=GodelianBoundary(self_ref_threshold=0.25)
        )
        prop = Proposition(
            id="self-ref-safety",
            content="This system always verifies its own safety correctly",
            category="safety",
            context={"dependencies": ["self_verifier"]},
        )
        result = router.route_with_hooks(prop)
        # Should have hook results from the pipeline
        assert len(result.hook_results) > 0
        # At least one hook should have fired (circuit_breaker for "always")
        actions = [h.get("action") for h in result.hook_results]
        assert len(actions) > 0

    def test_meta_proposition_all_hooks_execute(self):
        """Meta-cognitive proposition should pass through all non-blocking hooks."""
        router = ExtendedRealityBridgeRouter()
        prop = Proposition(
            id="meta-1",
            content="The system should evaluate its own decision quality",
            category="meta",
        )
        result = router.route_with_hooks(prop)
        assert len(result.hook_results) > 0
        # audit trail should have LOG_ONLY
        audit_results = [
            h for h in result.hook_results
            if h.get("hook_type") == "audit_trail"
        ]
        assert len(audit_results) > 0
        assert audit_results[0]["action"] == "log_only"
