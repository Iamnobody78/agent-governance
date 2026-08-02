r"""
P3: Monotonic Constraint Engine
================================
Ensures Agent behavior space converges monotonically — the agent's
effective action space never expands into dangerous territory.

Theory: An Agent's behavior space B is the set of all possible
(action, state) pairs. The monotonic constraint requires:
  |B(t+1) \ B_safe| <= |B(t) \ B_safe|  for all t

Where B_safe = actions known to be safe (no crash, no edge-fall,
no policy violation).

CI Integration: Run `python governance/meta/monotonic_constraint.py --ci-check`
to verify monotonic convergence. Non-zero slope = CI warning.
"""
import json
import sys
import time
from pathlib import Path


class MonotonicConstraint:
    """Tracks agent behavior space across iterations and enforces convergence.

    Behavior space is defined as the set of (action_hash, state_hash) pairs
    the agent has used in successful (non-crash) episodes.

    Monotonic constraint: unsafe_actions(t+1) <= unsafe_actions(t)
    """

    def __init__(self, state_dir: str | None = None):
        if state_dir is None:
            state_dir = Path(__file__).resolve().parent.parent.parent / ".agent_state"
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "monotonic_constraint.json"
        self._load()

    def _load(self):
        if self.state_file.exists():
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
                self._safe_set = {tuple(a) for a in data.get("safe_actions", [])}
                self._unsafe_set = {tuple(a) for a in data.get("unsafe_actions", [])}
                self._iteration = data.get("iteration", 0)
                self._convergence_slope = data.get("convergence_slope", 0.0)
        else:
            self._safe_set: set[tuple] = set()
            self._unsafe_set: set[tuple] = set()
            self._iteration = 0
            self._convergence_slope = 0.0

    def _save(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump({
                "iteration": self._iteration,
                "safe_actions": [list(a) for a in self._safe_set],
                "unsafe_actions": [list(a) for a in self._unsafe_set],
                "convergence_slope": self._convergence_slope,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }, f, indent=2)

    # ── Public API ──

    def record_action(self, action: int, state_hash: int, safe: bool):
        """Record whether an (action, state) pair was safe."""
        entry = (action, state_hash)
        if safe:
            self._safe_set.add(entry)
            self._unsafe_set.discard(entry)
        else:
            self._unsafe_set.add(entry)
            self._safe_set.discard(entry)

    def end_iteration(self) -> dict:
        """Close current iteration and compute convergence metrics."""
        self._iteration += 1
        prev_unsafe = self._unsafe_count
        self._save()
        self._convergence_slope = (len(self._unsafe_set) - prev_unsafe)

        return self.report()

    @property
    def _unsafe_count(self) -> int:
        return len(self._unsafe_set)

    def report(self) -> dict:
        """Return current monotonic constraint health."""
        total = len(self._safe_set) + len(self._unsafe_set)
        if total == 0:
            return {"status": "cold_start", "iteration": 0,
                    "safe_actions": 0, "unsafe_actions": 0,
                    "safe_ratio": 1.0, "convergence_slope": 0.0,
                    "convergence": True, "p3_health": 1.0}

        safe_ratio = len(self._safe_set) / total
        convergence = self._convergence_slope <= 0

        return {
            "status": "converging" if convergence else "DIVERGING",
            "iteration": self._iteration,
            "safe_actions": len(self._safe_set),
            "unsafe_actions": len(self._unsafe_set),
            "safe_ratio": round(safe_ratio, 4),
            "convergence_slope": self._convergence_slope,
            "convergence": convergence,
            "p3_health": round(max(0, 1.0 - (1.0 - safe_ratio) * 2), 2),
        }

    def ci_check(self) -> int:
        """CI entry point: returns 0 (pass) or 1 (warning)."""
        r = self.report()
        print("P3 Monotonic Constraint Check")
        print(f"  Iteration:    {r['iteration']}")
        print(f"  Safe actions: {r['safe_actions']}")
        print(f"  Unsafe:       {r['unsafe_actions']}")
        print(f"  Safe ratio:   {r['safe_ratio']:.2%}")
        print(f"  Slope:        {int(r['convergence_slope']):+d}")
        print(f"  P3 Health:    {r['p3_health']:.2f}/1.0")

        if not r["convergence"] and r["iteration"] > 0:
            print(f"  WARNING: Monotonic constraint violated — unsafe actions expanded by {r['convergence_slope']:+d}")
            print("  This PR introduces new unsafe behaviors. Review manually or run --reset-safe.")
            return 1  # Warning, not blocking

        print("  PASS: Behavior space is monotonically converging.")
        return 0


# ── CLI ──

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="P3 Monotonic Constraint Engine")
    parser.add_argument("--ci-check", action="store_true", help="CI-mode: exit 1 if diverging")
    parser.add_argument("--report", action="store_true", help="Print current status")
    parser.add_argument("--reset", action="store_true", help="Reset constraint state")
    parser.add_argument("--record", nargs=3, metavar=("ACTION", "STATE_HASH", "SAFE"),
                        help="Record action: ACTION STATE_HASH SAFE(0|1)")
    args = parser.parse_args()

    mc = MonotonicConstraint()

    if args.reset:
        mc._safe_set.clear()
        mc._unsafe_set.clear()
        mc._iteration = 0
        mc._save()
        print("Monotonic constraint state reset.")

    if args.record:
        action = int(args.record[0])
        state_hash = int(args.record[1])
        safe = bool(int(args.record[2]))
        mc.record_action(action, state_hash, safe)
        print(f"Recorded: action={action}, hash={state_hash}, safe={safe}")

    if args.report or (not args.ci_check and not args.record):
        import json as j
        print(j.dumps(mc.report(), indent=2))

    if args.ci_check:
        sys.exit(mc.ci_check())
