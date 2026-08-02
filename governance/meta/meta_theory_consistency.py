"""
P0: Meta-Theory Consistency Checker
=====================================
Validates that 42 meta-layers have no logical contradictions.

Conflict detection: If Layer A recommends "explore more" and
Layer B recommends "be conservative", that's a logical conflict.

Integration: python meta_theory_consistency.py --ci-check
In CI: exits 0 (consistent) or 1 (conflicts found).

Design based on P3 monotonic_constraint.py architecture.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent.parent.parent  # agent-governance/ -> project root
AUDIT_REPORT_DIR = _PROJECT / ".aionui" / "meta_governance" / "audit" / "reports"

# ── Conflict Pair Definitions ────────────────────────────────────────────────

# Each entry: (layer_a, layer_b, conflict_description, severity)
# These pairs are NATURALLY prone to conflict:
CONFLICT_PAIRS = [
    ("meta_safety", "meta_optimization", "Safety wants restraint, optimization wants exploration", "P0"),
    ("meta_memory", "meta_forgetting", "Memory wants retention, forgetting wants purge", "P1"),
    ("meta_decision", "meta_attention", "Decision wants focus, attention wants breadth", "P2"),
    ("meta_execution", "meta_safety", "Execution wants speed, safety wants checks", "P0"),
    ("meta_evolution", "meta_consolidation", "Evolution wants change, consolidation wants stability", "P1"),
    ("meta_learning", "meta_forgetting", "Learning accumulates, forgetting discards", "P2"),
    ("meta_perception", "meta_attention", "Perception wants more inputs, attention wants filtering", "P3"),
    ("meta_planning", "meta_adaptation", "Planning wants structure, adaptation wants flexibility", "P3"),
    ("meta_repair", "meta_safety", "Repair may introduce regressions, safety demands vetting", "P0"),
    ("meta_optimization", "meta_safety", "Optimization may cut corners, safety demands thoroughness", "P0"),
    ("meta_education", "meta_execution", "Education wants training, execution wants production", "P4"),
    ("meta_evaluation", "meta_evolution", "Evaluation wants stability, evolution wants change", "P2"),
]

# Severity weights for scoring
SEVERITY_WEIGHT = {"P0": 10, "P1": 6, "P2": 3, "P3": 1, "P4": 0.3}


class ConsistencyChecker:
    """Checks logical consistency across 42 meta-layers."""

    def __init__(self, audit_report_path: str = None):
        self.report_path = audit_report_path or self._latest_report()
        self._load()

    def _latest_report(self) -> Path | None:
        reports = sorted(AUDIT_REPORT_DIR.glob("meta_audit_*.json"), reverse=True)
        return reports[0] if reports else None

    def _load(self):
        if not self.report_path or not Path(self.report_path).exists():
            self._layers = {}
            self._overall_score = 0
            return

        with open(self.report_path, encoding="utf-8") as f:
            data = json.load(f)
        self._layers = data.get("layers", {})
        self._overall_score = data.get("overall_score", 0)

    # ── Conflict Detection ──────────────────────────────────────────────────

    def detect_conflicts(self) -> list[dict]:
        """Detect logical conflicts between meta-layer pairs."""
        conflicts = []

        for layer_a, layer_b, desc, severity in CONFLICT_PAIRS:
            a = self._layers.get(layer_a, {})
            b = self._layers.get(layer_b, {})

            if not a or not b:
                continue

            a_recs = [r.lower() for r in a.get("recommendations", [])]
            b_recs = [r.lower() for r in b.get("recommendations", [])]

            # Check recommendation keyword conflicts
            conflict_words = self._find_conflict_keywords(a_recs, b_recs)
            if conflict_words:
                conflicts.append({
                    "layer_a": layer_a,
                    "layer_b": layer_b,
                    "description": desc,
                    "severity": severity,
                    "conflict_keywords": conflict_words,
                    "a_recommendations": a.get("recommendations", [])[:3],
                    "b_recommendations": b.get("recommendations", [])[:3],
                    "a_score": a.get("health_score", 100),
                    "b_score": b.get("health_score", 100),
                })

            # Score disparity check: if one layer is healthy and the other is sick
            score_diff = abs(a.get("health_score", 100) - b.get("health_score", 100))
            if score_diff > 40:
                conflicts.append({
                    "layer_a": layer_a,
                    "layer_b": layer_b,
                    "description": f"Score disparity ({score_diff} pts) — {desc}",
                    "severity": severity,
                    "conflict_keywords": [f"score_gap_{int(score_diff)}"],
                    "a_recommendations": a.get("recommendations", [])[:1],
                    "b_recommendations": b.get("recommendations", [])[:1],
                    "a_score": a.get("health_score", 100),
                    "b_score": b.get("health_score", 100),
                    "type": "score_divergence",
                })

        return conflicts

    def _find_conflict_keywords(self, recs_a: list[str], recs_b: list[str]) -> list[str]:
        """Detect contradictory keyword pairs between two recommendation sets."""
        opposition_pairs = [
            (["explore", "expand", "increase", "grow", "broaden", "extend", "widen", "add", "more"],
             ["restrict", "limit", "reduce", "shrink", "narrow", "remove", "conservative", "constrain", "lock"]),
            (["speed", "fast", "optimize", "accelerate"],
             ["safe", "check", "verify", "guard", "validate", "audit", "review"]),
            (["change", "modify", "evolve", "adapt", "transform"],
             ["stable", "fixed", "preserve", "consistent", "freeze"]),
            (["learn", "train", "acquire", "accumulate"],
             ["forget", "purge", "discard", "prune", "remove"]),
            (["focus", "concentrate", "narrow", "single"],
             ["broaden", "diversify", "spread", "multi", "parallel"]),
        ]

        conflicts = []
        for expand_kw, restrict_kw in opposition_pairs:
            a_has = any(kw in r for r in recs_a for kw in expand_kw)
            b_has = any(kw in r for r in recs_b for kw in restrict_kw)
            if a_has and b_has:
                a_match = next((kw for r in recs_a for kw in expand_kw if kw in r), "?")
                b_match = next((kw for r in recs_b for kw in restrict_kw if kw in r), "?")
                conflicts.append(f"{a_match}_vs_{b_match}")
            # Also check reverse direction
            b_has_expand = any(kw in r for r in recs_b for kw in expand_kw)
            a_has_restrict = any(kw in r for r in recs_a for kw in restrict_kw)
            if b_has_expand and a_has_restrict:
                a_match = next((kw for r in recs_a for kw in restrict_kw if kw in r), "?")
                b_match = next((kw for r in recs_b for kw in expand_kw if kw in r), "?")
                conflicts.append(f"{a_match}_vs_{b_match}")

        return conflicts

    # ── Consistency Score ────────────────────────────────────────────────────

    def compute_score(self) -> dict:
        """Compute overall consistency score (0-100)."""
        conflicts = self.detect_conflicts()

        total_penalty = 0.0
        for c in conflicts:
            weight = SEVERITY_WEIGHT.get(c["severity"], 5)
            total_penalty += weight

            # Extra penalty for score divergence
            if c.get("type") == "score_divergence":
                total_penalty += weight * 0.5

        max_possible = sum(SEVERITY_WEIGHT[s] for _, _, _, s in CONFLICT_PAIRS)
        consistency = max(0, 100 - (total_penalty / max(max_possible, 1)) * 100)

        severity_counts = defaultdict(int)
        for c in conflicts:
            severity_counts[c["severity"]] += 1

        return {
            "consistency_score": round(consistency, 1),
            "conflicts_found": len(conflicts),
            "conflicts_by_severity": dict(severity_counts),
            "conflict_details": conflicts,
            "status": "CONSISTENT" if consistency >= 85 else
                      "MINOR_CONFLICTS" if consistency >= 70 else
                      "SIGNIFICANT_CONFLICTS" if consistency >= 50 else
                      "CRITICAL_CONFLICTS",
            "total_pairs_checked": len(CONFLICT_PAIRS),
        }

    def report(self) -> dict:
        return self.compute_score()

    def ci_check(self) -> int:
        """CI entry point. Returns 0 (pass), 1 (warning), 2 (blocking)."""
        result = self.compute_score()
        conflicts = result["conflict_details"]

        print("P0: Meta-Theory Consistency Check")
        print(f"  Layers loaded:       {len(self._layers)}")
        print(f"  Pairs checked:       {result['total_pairs_checked']}")
        print(f"  Conflicts found:     {result['conflicts_found']}")
        print(f"  Consistency score:   {result['consistency_score']}/100")
        print(f"  Status:              {result['status']}")

        if conflicts:
            print("\n  Conflict details:")
            for c in conflicts:
                kw = ",".join(c.get("conflict_keywords", [])[:3])
                print(f"    [{c['severity']}] {c['layer_a']} vs {c['layer_b']}: "
                      f"{c['description']}")
                if c.get("a_score") and c.get("b_score"):
                    print(f"         scores: {c['a_score']} vs {c['b_score']}")
                if kw:
                    print(f"         keywords: {kw}")

        if result["consistency_score"] < 50:
            print("\n  BLOCK: Critical consistency issues — human review required.")
            return 2
        elif result["consistency_score"] < 85:
            print("\n  WARNING: Minor consistency issues — review recommended.")
            return 1
        else:
            print("\n  PASS: Meta-theory is logically consistent.")
            return 0


# ── CLI ──

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="P0: Meta-Theory Consistency Checker")
    parser.add_argument("--ci-check", action="store_true", help="CI mode: exit 1 on warning, 2 on blocking")
    parser.add_argument("--report", action="store_true", help="Full consistency report (JSON)")
    args = parser.parse_args()

    checker = ConsistencyChecker()

    if args.report:
        print(json.dumps(checker.report(), indent=2, ensure_ascii=False))
    elif args.ci_check:
        sys.exit(checker.ci_check())
    else:
        # Default: print summary + report
        result = checker.report()
        print(f"P0 Meta-Theory Consistency: {result['consistency_score']}/100 ({result['status']})")
        print(f"  {result['conflicts_found']} conflicts in {result['total_pairs_checked']} pairs")
        for c in result["conflict_details"]:
            print(f"  [{c['severity']}] {c['layer_a']} <> {c['layer_b']}: {c['description'][:80]}")
