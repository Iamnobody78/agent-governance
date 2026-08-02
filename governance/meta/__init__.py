"""Meta-governance module: P0 meta-theory consistency, P3 monotonic constraint, meta-audit."""
from governance.meta.monotonic_constraint import MonotonicConstraint
from governance.meta.meta_theory_consistency import ConsistencyChecker

__all__ = ["MonotonicConstraint", "ConsistencyChecker"]
