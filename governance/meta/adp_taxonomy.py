"""
ADP (Agent Decision Protocol) Taxonomy
======================================

Implements the ADP open standard for classifying, authorizing, and auditing
autonomous AI agent decisions. Based on the specification at:
  https://github.com/OpenAgentGovernance/agent-decision-protocol

Classification dimensions:
  - Autonomy Level: A1 (manual) → A5 (fully autonomous)
  - Decision Type: CREATE, READ, UPDATE, DELETE, EXECUTE, DELEGATE
  - Risk Level: NEGLIGIBLE → CRITICAL
  - Reversibility: REVERSIBLE, PARTIALLY_REVERSIBLE, IRREVERSIBLE

Integration: GodelianBoundary maps its verdicts (SAFE/INTERNAL/EXTERNALIZE/
UNDECIDABLE) to ADP classifications, making audit trails enterprise-compliant.
"""
from dataclasses import dataclass, field
from enum import Enum


# ── ADP Enums ─────────────────────────────────────────────────────────────────

class AutonomyLevel(str, Enum):
    """ADP Autonomy Classification (A1-A5)."""
    A1_MANUAL = "A1"              # Human decides; agent is passive
    A2_ASSISTED = "A2"            # Agent suggests; human decides
    A3_SUPERVISED = "A3"          # Agent decides; human can override
    A4_AUTONOMOUS = "A4"          # Agent decides; human notified
    A5_FULLY_AUTONOMOUS = "A5"   # Agent decides; no human in loop


class DecisionType(str, Enum):
    """ADP Decision Type — what action the decision enables."""
    CREATE = "CREATE"     # Create new resources/data
    READ = "READ"         # Read/access data
    UPDATE = "UPDATE"     # Modify existing resources
    DELETE = "DELETE"     # Delete/destroy resources
    EXECUTE = "EXECUTE"   # Execute code/commands/actions
    DELEGATE = "DELEGATE" # Delegate to another agent/system


class RiskLevel(str, Enum):
    """ADP Risk Level — potential impact of the decision."""
    NEGLIGIBLE = "NEGLIGIBLE"  # No meaningful harm
    LOW = "LOW"                 # Minor inconvenience
    MEDIUM = "MEDIUM"           # Recoverable damage
    HIGH = "HIGH"               # Significant harm possible
    CRITICAL = "CRITICAL"       # Irreversible catastrophic harm


class Reversibility(str, Enum):
    """ADP Reversibility — can the decision be undone?"""
    REVERSIBLE = "REVERSIBLE"                 # Fully undoable
    PARTIALLY_REVERSIBLE = "PARTIALLY_REVERSIBLE"  # Some side effects remain
    IRREVERSIBLE = "IRREVERSIBLE"             # Cannot be undone


# ── ADP Classification ────────────────────────────────────────────────────────

@dataclass
class ADPClassification:
    """A complete ADP-compliant decision classification.

    Maps the agent's decision context to the ADP standard taxonomy.
    """
    autonomy_level: AutonomyLevel
    decision_type: DecisionType
    risk_level: RiskLevel
    reversibility: Reversibility
    requires_human: bool = False
    max_retry_count: int = 0        # -1 = unlimited
    ttl_seconds: int = 0            # 0 = no time bound
    policy_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "autonomy_level": self.autonomy_level.value,
            "decision_type": self.decision_type.value,
            "risk_level": self.risk_level.value,
            "reversibility": self.reversibility.value,
            "requires_human": self.requires_human,
            "max_retry_count": self.max_retry_count,
            "ttl_seconds": self.ttl_seconds,
            "policy_tags": self.policy_tags,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ADPClassification":
        return cls(
            autonomy_level=AutonomyLevel(d["autonomy_level"]),
            decision_type=DecisionType(d["decision_type"]),
            risk_level=RiskLevel(d["risk_level"]),
            reversibility=Reversibility(d["reversibility"]),
            requires_human=d.get("requires_human", False),
            max_retry_count=d.get("max_retry_count", 0),
            ttl_seconds=d.get("ttl_seconds", 0),
            policy_tags=d.get("policy_tags", []),
        )


# ── ADP → GodelianBoundary Mapper ────────────────────────────────────────────

def map_to_adp(
    godelian_verdict: str,
    proposition_category: str = "",
    self_ref_score: float = 0.0,
    confidence: float = 0.5,
) -> ADPClassification:
    """Map a GodelianBoundary verdict to an ADP-compliant classification.

    Mapping logic (based on ADP specification):
      - SAFE → A4 or A5 (autonomous), LOW risk, REVERSIBLE
      - INTERNAL → A4 (autonomous), LOW-MEDIUM risk, REVERSIBLE
      - EXTERNALIZE → A3 (supervised), MEDIUM-HIGH risk, PARTIALLY_REVERSIBLE
      - UNDECIDABLE → A2 (assisted), CRITICAL risk, IRREVERSIBLE

    Category modifiers:
      - "safety" → bumps risk by 1 level
      - "meta" → bumps autonomy down by 1 level (requires more oversight)
      - "correctness" → reduces reversibility

    Args:
        godelian_verdict: One of 'safe', 'internal', 'externalize', 'undecidable'
        proposition_category: Category like 'safety', 'fairness', 'correctness'
        self_ref_score: 0-1 self-reference score from GodelianBoundary
        confidence: 0-1 confidence score

    Returns:
        ADPClassification with autonomy, type, risk, reversibility
    """
    # ── Base mapping by verdict ────────────────────────────────────────
    verdict = godelian_verdict.lower()

    _base_map = {
        "safe": {
            "autonomy": AutonomyLevel.A5_FULLY_AUTONOMOUS,
            "type": DecisionType.READ,
            "risk": RiskLevel.NEGLIGIBLE,
            "reversibility": Reversibility.REVERSIBLE,
            "requires_human": False,
            "max_retry": -1,
            "ttl": 3600,
        },
        "internal": {
            "autonomy": AutonomyLevel.A4_AUTONOMOUS,
            "type": DecisionType.UPDATE,
            "risk": RiskLevel.LOW,
            "reversibility": Reversibility.REVERSIBLE,
            "requires_human": False,
            "max_retry": 3,
            "ttl": 1800,
        },
        "externalize": {
            "autonomy": AutonomyLevel.A3_SUPERVISED,
            "type": DecisionType.DELEGATE,
            "risk": RiskLevel.MEDIUM,
            "reversibility": Reversibility.PARTIALLY_REVERSIBLE,
            "requires_human": True,
            "max_retry": 5,
            "ttl": 900,
        },
        "undecidable": {
            "autonomy": AutonomyLevel.A2_ASSISTED,
            "type": DecisionType.EXECUTE,
            "risk": RiskLevel.CRITICAL,
            "reversibility": Reversibility.IRREVERSIBLE,
            "requires_human": True,
            "max_retry": 0,
            "ttl": 300,
        },
    }

    if verdict not in _base_map:
        # Unknown verdict → A1 (most conservative)
        base = {
            "autonomy": AutonomyLevel.A1_MANUAL,
            "type": DecisionType.READ,
            "risk": RiskLevel.HIGH,
            "reversibility": Reversibility.IRREVERSIBLE,
            "requires_human": True,
            "max_retry": 0,
            "ttl": 0,
        }
    else:
        base = _base_map[verdict]

    # ── Category modifiers ────────────────────────────────────────────
    risk_level = base["risk"]
    autonomy = base["autonomy"]
    reversibility = base["reversibility"]
    requires_human = base["requires_human"]
    decision_type = base["type"]

    # Safety category: risk +1 level, more reversible (conservative)
    if "safety" in proposition_category.lower():
        risk_level = _bump_risk(risk_level, 1)
        decision_type = DecisionType.EXECUTE

    # Meta category: reduce autonomy (self-referential decisions need oversight)
    if "meta" in proposition_category.lower():
        autonomy = _reduce_autonomy(autonomy, 1)
        risk_level = _bump_risk(risk_level, 1)
        decision_type = DecisionType.DELEGATE

    # Correctness category: harder to reverse (corruption risk)
    if "correctness" in proposition_category.lower():
        reversibility = _reduce_reversibility(reversibility)
        decision_type = DecisionType.UPDATE

    # Performance category: usually safe to be autonomous
    if "performance" in proposition_category.lower():
        decision_type = DecisionType.UPDATE

    # Fairness category: needs human oversight
    if "fairness" in proposition_category.lower():
        requires_human = True
        decision_type = DecisionType.DELEGATE
        risk_level = _bump_risk(risk_level, 1)

    # ── Score-based refinements ──────────────────────────────────────
    # High self-reference → more risky, less autonomous
    if self_ref_score >= 0.5:
        risk_level = _bump_risk(risk_level, 1)
        if self_ref_score >= 0.7:
            autonomy = _reduce_autonomy(autonomy, 1)
            requires_human = True

    # Low confidence → bump risk
    if confidence < 0.5:
        risk_level = _bump_risk(risk_level, 1)
        requires_human = True

    # ── Build policy tags ────────────────────────────────────────────
    policy_tags = [f"godelian:{verdict}"]
    if self_ref_score >= 0.5:
        policy_tags.append("self_referential")
    if proposition_category:
        policy_tags.append(f"domain:{proposition_category}")
    if requires_human:
        policy_tags.append("human_in_loop")

    return ADPClassification(
        autonomy_level=autonomy,
        decision_type=decision_type,
        risk_level=risk_level,
        reversibility=reversibility,
        requires_human=requires_human,
        max_retry_count=base["max_retry"],
        ttl_seconds=base["ttl"],
        policy_tags=policy_tags,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bump_risk(current: RiskLevel, steps: int) -> RiskLevel:
    """Increase risk level by N steps, clamping at CRITICAL."""
    levels = list(RiskLevel)
    idx = levels.index(current)
    return levels[min(idx + steps, len(levels) - 1)]


def _reduce_autonomy(current: AutonomyLevel, steps: int) -> AutonomyLevel:
    """Decrease autonomy by N steps, clamping at A1."""
    levels = list(AutonomyLevel)
    idx = levels.index(current)
    return levels[max(idx - steps, 0)]


def _reduce_reversibility(current: Reversibility) -> Reversibility:
    """Reduce reversibility by 1 step."""
    levels = list(Reversibility)
    idx = levels.index(current)
    return levels[min(idx + 1, len(levels) - 1)]
