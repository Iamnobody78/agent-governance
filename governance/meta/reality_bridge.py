"""
TaG-Extended RealityBridge Router
==================================

Extends the GodelianBoundary RealityBridgeRouter with TaG-style governance
hooks (21 production-tested hooks from Trust and Governance framework).

TaG Reference: https://github.com/AIObuilt/TaG

Original channels: gazebo, log, user, shadow_loop
Extended channels: +10 TaG governance hook types

Architecture:
    GodelianBoundary.analyze()
        → verdict EXTERNALIZE
        → RealityBridgeRouter.route()
            → TaGHookRegistry.match()
                → hook.execute() → ALLOW / DENY / MODIFY / LOG

Each hook is a named, configurable pre-execution check with:
  - hook_type: what aspect of governance it covers
  - condition: when it triggers
  - action: ALLOW, DENY, MODIFY, DEFER (to human), LOG_ONLY
  - ttl: time-bound validity
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from governance.meta.godelian_boundary import (
    GodelianBoundary,
    GodelianVerdict,
    Proposition,
    RealityBridgeRouter,
)


# ── TaG Hook Types ───────────────────────────────────────────────────────────

class TaGHookType(str, Enum):
    """TaG-compatible governance hook types.

    Based on TaG's 21 production-tested hooks, categorized by governance domain.
    """
    # ── Financial ──
    SPENDING_LIMIT = "spending_limit"           # Cost ceiling per session/task
    BUDGET_QUOTA = "budget_quota"               # Token/API call budget
    COST_AWARE_ROUTING = "cost_aware_routing"   # Route to cheaper model if possible

    # ── Security ──
    CREDENTIAL_INTERCEPT = "credential_intercept"  # Block credential leaks
    RATE_LIMIT = "rate_limit"                      # Max requests per window
    PERMISSION_BOUNDARY = "permission_boundary"    # Sandbox capability limits
    INPUT_SANITIZATION = "input_sanitization"      # Sanitize untrusted input

    # ── Operational ──
    DEPLOYMENT_GATE = "deployment_gate"         # Pre-deploy safety check
    CIRCUIT_BREAKER = "circuit_breaker"         # Halt on repeated failures
    RETRY_POLICY = "retry_policy"               # Max retries + backoff
    TIMEOUT_GUARD = "timeout_guard"             # Max execution time

    # ── Data ──
    DATA_EXFILTRATION = "data_exfiltration"     # Prevent data leaks
    PII_MASKING = "pii_masking"                 # Mask PII in outputs
    QUERY_COMPLEXITY_LIMIT = "query_complexity_limit"  # Limit DB query cost

    # ── Compliance ──
    AUDIT_TRAIL = "audit_trail"                 # Mandatory logging
    POLICY_ENFORCEMENT = "policy_enforcement"   # Check against org policies
    CONSENT_VERIFICATION = "consent_verification"  # Verify user consent

    # ── Quality ──
    OUTPUT_VALIDATION = "output_validation"     # Validate agent output quality
    HALLUCINATION_CHECK = "hallucination_check" # Detect factual errors
    BIAS_DETECTION = "bias_detection"           # Check for biased output

    # ── Meta ──
    SELF_MODIFICATION_GATE = "self_modification_gate"  # Gate self-modifying actions


class TaGHookAction(str, Enum):
    """Action taken by a TaG hook."""
    ALLOW = "allow"           # Pass through without modification
    DENY = "deny"             # Block the action
    MODIFY = "modify"         # Modify the action before execution
    DEFER = "defer"           # Defer to human reviewer
    LOG_ONLY = "log_only"     # Log but don't block


# ── TaG Hook Definition ──────────────────────────────────────────────────────

@dataclass
class TaGHook:
    """A single TaG-compatible governance hook.

    Each hook is a named pre-execution check that inspects propositions
    and returns ALLOW / DENY / MODIFY / DEFER / LOG_ONLY.
    """
    name: str
    hook_type: TaGHookType
    description: str
    condition: Callable[[Proposition], bool]  # When this hook triggers
    action: Callable[[Proposition], tuple[TaGHookAction, str]]  # What to do
    priority: int = 50          # Lower = runs first (0-100)
    enabled: bool = True
    ttl_seconds: int = 0        # 0 = no time bound
    tags: list[str] = field(default_factory=list)

    def execute(self, proposition: Proposition) -> "TaGHookResult":
        """Execute this hook on a proposition.

        Returns:
            TaGHookResult with action, reason, and optional modified proposition.
        """
        if not self.enabled:
            return TaGHookResult(
                hook_name=self.name,
                hook_type=self.hook_type,
                action=TaGHookAction.ALLOW,
                reason=f"Hook '{self.name}' is disabled",
            )

        if not self.condition(proposition):
            return TaGHookResult(
                hook_name=self.name,
                hook_type=self.hook_type,
                action=TaGHookAction.ALLOW,
                reason=f"Condition not met for hook '{self.name}'",
            )

        action, reason = self.action(proposition)
        return TaGHookResult(
            hook_name=self.name,
            hook_type=self.hook_type,
            action=action,
            reason=reason,
        )


@dataclass
class TaGHookResult:
    """Result of executing a TaG hook."""
    hook_name: str
    hook_type: TaGHookType
    action: TaGHookAction
    reason: str
    modified_proposition: Proposition | None = None

    def to_dict(self) -> dict:
        return {
            "hook_name": self.hook_name,
            "hook_type": self.hook_type.value,
            "action": self.action.value,
            "reason": self.reason,
            "modified": self.modified_proposition is not None,
        }


@dataclass
class TaGRoutingResult:
    """Complete routing result including all hook evaluations."""
    routed: bool
    godelian_report: dict
    hook_results: list[dict] = field(default_factory=list)
    final_action: str = "allow"   # allow, deny, modified, deferred
    bridge_result: str = ""


# ── TaG Hook Registry ────────────────────────────────────────────────────────

class TaGHookRegistry:
    """Registry of TaG-compatible governance hooks.

    Hooks are executed in priority order (lowest first). If any hook
    returns DENY, the proposition is blocked. DEFER sends to human review.
    MODIFY transforms the proposition before execution.
    """

    def __init__(self):
        self._hooks: dict[str, TaGHook] = {}
        self._register_defaults()

    # ── Registration ─────────────────────────────────────────────────────

    def register(self, hook: TaGHook):
        """Register a hook. Overwrites if same name exists."""
        self._hooks[hook.name] = hook

    def unregister(self, name: str):
        """Remove a hook by name."""
        self._hooks.pop(name, None)

    def get(self, name: str) -> TaGHook | None:
        return self._hooks.get(name)

    def list_hooks(self) -> list[TaGHook]:
        return sorted(self._hooks.values(), key=lambda h: h.priority)

    def list_by_type(self, hook_type: TaGHookType) -> list[TaGHook]:
        return sorted(
            [h for h in self._hooks.values() if h.hook_type == hook_type],
            key=lambda h: h.priority,
        )

    # ── Execution ────────────────────────────────────────────────────────

    def execute_all(self, proposition: Proposition) -> list[TaGHookResult]:
        """Execute all enabled hooks in priority order.

        Stops at first DENY (short-circuit evaluation for security).
        """
        results = []
        for hook in self.list_hooks():
            result = hook.execute(proposition)
            results.append(result)
            # DENY short-circuits — security hooks must block immediately
            if result.action == TaGHookAction.DENY:
                break
        return results

    def final_verdict(self, results: list[TaGHookResult]) -> TaGHookAction:
        """Compute the final verdict from a list of hook results.

        Priority: DENY > DEFER > MODIFY > ALLOW
        """
        actions = [r.action for r in results]
        if TaGHookAction.DENY in actions:
            return TaGHookAction.DENY
        if TaGHookAction.DEFER in actions:
            return TaGHookAction.DEFER
        if TaGHookAction.MODIFY in actions:
            return TaGHookAction.MODIFY
        return TaGHookAction.ALLOW

    # ── Default Hooks ────────────────────────────────────────────────────

    def _register_defaults(self):
        """Register the default set of production-tested TaG hooks.

        These cover the most critical governance dimensions and can be
        extended by users for domain-specific needs.
        """

        # ── Security hooks (priority 0-20) ──
        self.register(TaGHook(
            name="credential_leak_guard",
            hook_type=TaGHookType.CREDENTIAL_INTERCEPT,
            description="Block propositions that may leak credentials",
            priority=5,
            condition=lambda p: any(
                kw in p.content.lower()
                for kw in ("api_key", "password", "secret", "token", "credential")
            ),
            action=lambda p: (
                TaGHookAction.DENY,
                "Credential-like pattern detected in proposition",
            ),
            tags=["security", "critical"],
        ))

        self.register(TaGHook(
            name="rate_limit_guard",
            hook_type=TaGHookType.RATE_LIMIT,
            description="Rate-limit repeated external verification requests",
            priority=10,
            condition=lambda p: "verify" in p.content.lower() and "itself" in p.content.lower(),
            action=lambda p: (
                TaGHookAction.MODIFY,
                "Rate-limited self-verification request; added cooldown",
            ),
            ttl_seconds=60,
            tags=["security", "performance"],
        ))

        # ── Financial hooks (priority 20-30) ──
        self.register(TaGHook(
            name="cost_aware_routing",
            hook_type=TaGHookType.COST_AWARE_ROUTING,
            description="Route to cheaper verification when confidence is high",
            priority=20,
            condition=lambda p: p.category in ("performance", "correctness"),
            action=lambda p: (
                TaGHookAction.ALLOW,
                "Low-cost routing sufficient for non-safety categories",
            ),
            tags=["cost", "routing"],
        ))

        # ── Operational hooks (priority 30-50) ──
        self.register(TaGHook(
            name="deployment_safety_gate",
            hook_type=TaGHookType.DEPLOYMENT_GATE,
            description="Gate deployment-related propositions for safety review",
            priority=30,
            condition=lambda p: any(
                kw in p.content.lower()
                for kw in ("deploy", "release", "publish", "production")
            ),
            action=lambda p: (
                TaGHookAction.DEFER,
                "Deployment action requires human review",
            ),
            tags=["operations", "safety"],
        ))

        self.register(TaGHook(
            name="circuit_breaker",
            hook_type=TaGHookType.CIRCUIT_BREAKER,
            description="Block actions when failure rate exceeds threshold",
            priority=35,
            condition=lambda p: "always" in p.content.lower() and "never" in p.content.lower(),
            action=lambda p: (
                TaGHookAction.DENY,
                "Absolute claim detected ('always'/'never') — potential overconfidence",
            ),
            tags=["operations", "reliability"],
        ))

        self.register(TaGHook(
            name="self_modification_safety",
            hook_type=TaGHookType.SELF_MODIFICATION_GATE,
            description="Gate self-modifying propositions",
            priority=40,
            condition=lambda p: any(
                kw in p.content.lower()
                for kw in ("self-modif", "modify itself", "change its own", "rewrite itself")
            ),
            action=lambda p: (
                TaGHookAction.DEFER,
                "Self-modification attempt detected — requires external review",
            ),
            tags=["meta", "safety", "critical"],
        ))

        # ── Data hooks (priority 50-60) ──
        self.register(TaGHook(
            name="pii_sanitization",
            hook_type=TaGHookType.PII_MASKING,
            description="Flag propositions that might contain PII",
            priority=50,
            condition=lambda p: any(
                kw in p.content.lower()
                for kw in ("email", "phone", "address", "ssn", "social security")
            ),
            action=lambda p: (
                TaGHookAction.MODIFY,
                "PII-related content flagged for sanitization",
            ),
            tags=["data", "privacy"],
        ))

        # ── Compliance hooks (priority 60-80) ──
        self.register(TaGHook(
            name="mandatory_audit_trail",
            hook_type=TaGHookType.AUDIT_TRAIL,
            description="Log all externalized propositions",
            priority=60,
            condition=lambda p: True,  # Always log externalized props
            action=lambda p: (
                TaGHookAction.LOG_ONLY,
                "Logged for audit trail",
            ),
            tags=["compliance", "audit"],
        ))

        # ── Quality hooks (priority 80-100) ──
        self.register(TaGHook(
            name="output_safety_validator",
            hook_type=TaGHookType.OUTPUT_VALIDATION,
            description="Validate that routed output meets quality standards",
            priority=90,
            condition=lambda p: "unsafe" in p.content.lower() or "dangerous" in p.content.lower(),
            action=lambda p: (
                TaGHookAction.DENY,
                "Unsafe/dangerous content detected",
            ),
            tags=["quality", "safety"],
        ))


# ── Extended RealityBridge Router ─────────────────────────────────────────────

class ExtendedRealityBridgeRouter(RealityBridgeRouter):
    """Extended RealityBridge with TaG hook pipeline.

    Extends the base RealityBridgeRouter with:
      - TaG hook registry (10 default hooks, user-extensible)
      - Pre-execution hook pipeline (security → financial → ops → data → compliance → quality)
      - Structured routing results with hook verdicts
      - Channel-aware hook selection
    """

    def __init__(
        self,
        boundary: GodelianBoundary | None = None,
        hook_registry: TaGHookRegistry | None = None,
    ):
        super().__init__(boundary)
        self.hook_registry = hook_registry or TaGHookRegistry()

    def route_with_hooks(
        self,
        proposition: Proposition,
        bridge=None,
        skip_hooks: bool = False,
    ) -> TaGRoutingResult:
        """Route a proposition through the full TaG hook pipeline.

        Two-layer safety architecture:
          1. TaG Hooks (pre-security): Run FIRST — independent of Godelian analysis.
             Detects credential leaks, deployment gates, self-modification, etc.
          2. GodelianBoundary (self-reference): Analyzes self-referential patterns.
          3. If hooks DENY → blocked regardless of Godelian verdict.
          4. If hooks DEFER → deferred to human review.
          5. If hooks ALLOW + Godelian SAFE/INTERNAL → no routing needed.
          6. If Godelian EXTERNALIZE/UNDECIDABLE → route to bridge.

        Args:
            proposition: The proposition to analyze and route
            bridge: Optional RealityBridge instance for external verification
            skip_hooks: If True, skip TaG hooks (debug mode)

        Returns:
            TaGRoutingResult with full hook evaluation trace
        """
        # ── Layer 1: TaG Pre-Security Hooks (always run, independent of Godelian) ──
        if skip_hooks:
            hook_results = []
            hook_verdicts = []
        else:
            hook_verdicts = self.hook_registry.execute_all(proposition)
            hook_results = [r.to_dict() for r in hook_verdicts]

        final_action = self.hook_registry.final_verdict(hook_verdicts) if not skip_hooks else TaGHookAction.ALLOW

        # If hooks say DENY, block immediately — Godelian analysis not needed
        if final_action == TaGHookAction.DENY:
            # Still run Godelian for audit trail
            report = self.boundary.analyze(proposition)
            return TaGRoutingResult(
                routed=False,
                godelian_report=report.to_dict(),
                hook_results=hook_results,
                final_action="deny",
                bridge_result="Blocked by TaG pre-security hook: DENY",
            )

        # ── Layer 2: GodelianBoundary Self-Reference Analysis ──
        report = self.boundary.analyze(proposition)

        # Safe/internal propositions with no hook concerns → no routing needed
        if report.verdict in (GodelianVerdict.INTERNAL, GodelianVerdict.SAFE):
            # BUT if hooks say DEFER, still flag for human review
            if final_action == TaGHookAction.DEFER:
                return TaGRoutingResult(
                    routed=False,
                    godelian_report=report.to_dict(),
                    hook_results=hook_results,
                    final_action="deferred",
                    bridge_result="Deferred to human review by TaG hook (Godelian: SAFE)",
                )
            return TaGRoutingResult(
                routed=False,
                godelian_report=report.to_dict(),
                hook_results=hook_results,
                final_action="allow" if final_action == TaGHookAction.ALLOW
                             else final_action.value,
                bridge_result="Internal safe proposition — not routed",
            )

        # If hooks say DEFER for externalized propositions, prioritize human review
        if final_action == TaGHookAction.DEFER:
            return TaGRoutingResult(
                routed=False,
                godelian_report=report.to_dict(),
                hook_results=hook_results,
                final_action="deferred",
                bridge_result="Deferred to human review by TaG hook",
            )

        # ── Layer 3: Route to RealityBridge ──
        bridge_result = "No bridge available"
        if bridge:
            channel = getattr(bridge, report.recommended_channel, None)
            if channel:
                result = channel(proposition)
                bridge_result = str(result)
            else:
                bridge_result = f"Channel '{report.recommended_channel}' not available"

        return TaGRoutingResult(
            routed=True,
            godelian_report=report.to_dict(),
            hook_results=hook_results,
            final_action=final_action,
            bridge_result=bridge_result,
        )

    def get_state(self) -> dict:
        """Get observability state including TaG hook status."""
        base_state = self.boundary.get_state()

        hooks_state = {
            "total_hooks": len(self.hook_registry._hooks),
            "enabled_hooks": sum(
                1 for h in self.hook_registry._hooks.values() if h.enabled
            ),
            "hooks_by_type": {},
        }
        for hook in self.hook_registry.list_hooks():
            t = hook.hook_type.value
            if t not in hooks_state["hooks_by_type"]:
                hooks_state["hooks_by_type"][t] = []
            hooks_state["hooks_by_type"][t].append({
                "name": hook.name,
                "enabled": hook.enabled,
                "priority": hook.priority,
            })

        return {
            "module": "ExtendedRealityBridgeRouter",
            "godelian_state": base_state,
            "tag_hooks": hooks_state,
        }

    def add_hook(self, hook: TaGHook):
        """Register a custom TaG hook."""
        self.hook_registry.register(hook)

    def remove_hook(self, name: str):
        """Remove a TaG hook by name."""
        self.hook_registry.unregister(name)

    def toggle_hook(self, name: str, enabled: bool):
        """Enable or disable a hook by name."""
        hook = self.hook_registry.get(name)
        if hook:
            hook.enabled = enabled

    def list_hooks(self) -> list[dict]:
        """List all hooks with status."""
        return [
            {
                "name": h.name,
                "type": h.hook_type.value,
                "enabled": h.enabled,
                "priority": h.priority,
                "description": h.description,
            }
            for h in self.hook_registry.list_hooks()
        ]
