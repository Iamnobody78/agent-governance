#!/usr/bin/env python3
"""Thermal Health Check — entropy budget monitor for CI.

Reads .aionui/entropy.log (if exists) and compares current code entropy
against baseline. If cognitive temperature delta exceeds threshold,
generates ghost patch as warning (non-blocking).
"""
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))

ENTROPY_LOG = _PROJECT / ".aionui" / "entropy.log"
GHOST_DIR = _PROJECT / "liquid" / "ghosts"
ENTROPY_THRESHOLD = 0.15  # 15% delta triggers warning


def compute_file_entropy(directory: Path) -> float:
    """Compute Shannon entropy of Python file sizes as proxy for code complexity."""
    import math
    sizes = []
    for f in directory.rglob("*.py"):
        if "__pycache__" not in str(f) and ".git" not in str(f):
            sizes.append(f.stat().st_size)

    if not sizes:
        return 0.0

    total = sum(sizes)
    entropy = 0.0
    for s in sizes:
        p = s / total
        if p > 0:
            entropy -= p * math.log2(p)
    return round(entropy, 4)


def load_baseline() -> dict:
    """Load baseline entropy from log file."""
    if not ENTROPY_LOG.exists():
        return {"baseline_entropy": 0.0, "timestamp": str(datetime.now(timezone.utc))}

    try:
        with open(ENTROPY_LOG, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return {"baseline_entropy": 0.0, "timestamp": str(datetime.now(timezone.utc))}


def save_baseline(entropy: float):
    """Save current entropy as new baseline."""
    ENTROPY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ENTROPY_LOG, "w", encoding="utf-8") as f:
        json.dump({
            "baseline_entropy": entropy,
            "timestamp": str(datetime.now(timezone.utc)),
        }, f, indent=2)


def generate_ghost_patch(delta: float, current_entropy: float):
    """Generate a ghost patch file for post-hoc analysis."""
    GHOST_DIR.mkdir(parents=True, exist_ok=True)
    patch_file = GHOST_DIR / f"ghost_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.patch"
    patch_file.write_text(
        f"# Ghost Patch — entropy delta {delta:.2%}\n"
        f"# Generated: {datetime.now(timezone.utc).isoformat()}\n"
        f"# Baseline: {load_baseline().get('baseline_entropy', 'N/A')}\n"
        f"# Current:  {current_entropy}\n"
        f"# Action:   Review code complexity increase, consider refactoring\n"
    )
    return patch_file


def main():
    current = compute_file_entropy(_PROJECT)
    baseline_data = load_baseline()
    baseline = baseline_data.get("baseline_entropy", 0.0)

    print(f"Thermal Health Check")
    print(f"  Baseline entropy: {baseline}")
    print(f"  Current entropy:  {current}")

    if baseline == 0.0:
        print(f"  Cold start — setting baseline to {current}")
        save_baseline(current)
        return 0

    delta = abs(current - baseline) / max(baseline, 0.001)
    print(f"  Delta:            {delta:.2%}")

    if delta > ENTROPY_THRESHOLD:
        ghost = generate_ghost_patch(delta, current)
        print(f"  WARNING: Entropy delta {delta:.2%} > {ENTROPY_THRESHOLD:.0%} threshold")
        print(f"  Ghost patch created: {ghost}")
        print(f"  (Non-blocking — review recommended but not required)")
        return 0  # Non-blocking

    print(f"  PASS: Entropy within budget ({delta:.2%} < {ENTROPY_THRESHOLD:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
