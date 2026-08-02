"""
Code Hole Detector (P0)
=======================

Scans Python source files for "code holes" — empty interfaces, placeholders,
Mock returns, NotImplementedError stubs, and TODO/FIXME markers. Produces
actionable reports used by:

  - Health diagnostic (主治医师): hole ratio as core health metric
  - Self-evolution engine: highest-priority modules for auto-patching
  - Meta CI/CD: meta-audit phase input
  - Meta research: technical debt analysis data source

Detection Categories:
  TYPE           | Example
  ---------------|--------
  EMPTY_BODY     | def foo(): pass / ...
  MOCK_RETURN    | return Mock(...) / return MagicMock()
  NOT_IMPL       | raise NotImplementedError
  PLACEHOLDER    | return None / return [] / return {} / return ""
  TODO_MARKER    | # TODO / # FIXME / # HACK / # XXX
  STUB_CLASS     | class X: pass / ... (entire class body empty)

Architecture:
  CodeHoleDetector.scan() → HoleReport → .aionui/research/analysis/code_hole_report.md
  └── report.priority_modules → self_evolution_closed_loop.py

Usage:
    from tools.code_hole_detector import CodeHoleDetector

    detector = CodeHoleDetector()
    report = detector.scan_directory("governance/")
    print(report.summary())
    detector.save_report(report)
"""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ── Enums ──────────────────────────────────────────────────────────────────────

class HoleCategory(str, Enum):
    """Categories of code holes detected."""
    EMPTY_BODY = "empty_body"            # def foo(): pass / ...
    MOCK_RETURN = "mock_return"          # return Mock(...)
    NOT_IMPL = "not_implemented"         # raise NotImplementedError
    PLACEHOLDER = "placeholder"          # return None / "" / [] / {}
    TODO_MARKER = "todo_marker"          # # TODO / FIXME / HACK / XXX
    STUB_CLASS = "stub_class"            # class X: pass
    BLANK_FUNCTION = "blank_function"    # function with no meaningful code


class Severity(str, Enum):
    """Severity of a code hole."""
    LOW = "low"            # TODO markers, placeholder returns
    MEDIUM = "medium"      # Empty body, stub class
    HIGH = "high"          # NotImplementedError, multiple holes in one file
    CRITICAL = "critical"  # >50% hole ratio in a module


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class Hole:
    """A single code hole found in a source file."""
    file: str
    line: int
    category: HoleCategory
    severity: Severity = Severity.MEDIUM
    name: str = ""           # Function/class name
    snippet: str = ""        # The actual line of code


@dataclass
class FileReport:
    """Hole analysis for a single file."""
    file: str
    total_lines: int = 0
    hole_lines: int = 0
    hole_ratio: float = 0.0
    holes: list[Hole] = field(default_factory=list)
    status: str = "unknown"  # healthy, warning, critical


@dataclass
class HoleReport:
    """Complete code hole scan report."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scan_root: str = ""
    total_files: int = 0
    total_lines: int = 0
    total_holes: int = 0
    overall_hole_ratio: float = 0.0
    files: dict[str, FileReport] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    priority_modules: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Scanned {self.total_files} files ({self.total_lines} lines). "
            f"Found {self.total_holes} holes ({self.overall_hole_ratio:.1%} hole ratio). "
            f"Priority modules: {len(self.priority_modules)}"
        )


# ── AST Visitor ────────────────────────────────────────────────────────────────

class _HoleVisitor(ast.NodeVisitor):
    """AST visitor that detects code holes in Python source."""

    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.holes: list[Hole] = []
        self._func_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._func_stack.append(node.name)
        body = node.body

        # Check for empty body (pass or ...)
        if len(body) == 1 and isinstance(body[0], ast.Pass):
            self.holes.append(Hole(
                file="", line=node.lineno, category=HoleCategory.EMPTY_BODY,
                name=node.name, snippet=f"def {node.name}(...): pass"
            ))
        elif len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and body[0].value.value is Ellipsis:
            self.holes.append(Hole(
                file="", line=node.lineno, category=HoleCategory.EMPTY_BODY,
                name=node.name, snippet=f"def {node.name}(...): ..."
            ))

        # Check for NotImplementedError
        if len(body) == 1 and isinstance(body[0], ast.Raise):
            exc = body[0].exc
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "NotImplementedError":
                self.holes.append(Hole(
                    file="", line=node.lineno, category=HoleCategory.NOT_IMPL,
                    severity=Severity.HIGH, name=node.name,
                    snippet="raise NotImplementedError"
                ))

        # Check for placeholder return
        if len(body) == 1 and isinstance(body[0], ast.Return):
            ret_val = body[0].value
            if ret_val is None or (isinstance(ret_val, ast.Constant) and ret_val.value is None):
                self.holes.append(Hole(
                    file="", line=node.lineno, category=HoleCategory.PLACEHOLDER,
                    name=node.name, snippet="return None"
                ))
            elif isinstance(ret_val, ast.Constant) and ret_val.value in ("", [], {}):
                self.holes.append(Hole(
                    file="", line=node.lineno, category=HoleCategory.PLACEHOLDER,
                    name=node.name, snippet=f"return {repr(ret_val.value)}"
                ))

        # Check for Mock returns in body
        self._check_mock_returns(body)

        # Blank function (docstring only, no real code)
        meaningful = [s for s in body if not (isinstance(s, ast.Expr) and isinstance(s.value, (ast.Constant, ast.Str)))]
        if not meaningful and body:
            already_marked = any(h.line == node.lineno and h.category == HoleCategory.EMPTY_BODY for h in self.holes)
            if not already_marked:
                self.holes.append(Hole(
                    file="", line=node.lineno, category=HoleCategory.BLANK_FUNCTION,
                    name=node.name, snippet=f"def {node.name}(...): <docstring only>"
                ))

        self.generic_visit(node)
        self._func_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Treat async functions same as regular functions
        self.visit_FunctionDef(node)  # type: ignore

    def visit_ClassDef(self, node: ast.ClassDef):
        # Check for stub classes
        body = node.body
        meaningful = [s for s in body if not (isinstance(s, ast.Expr) and isinstance(s.value, (ast.Constant, ast.Str)))]
        if not meaningful:
            self.holes.append(Hole(
                file="", line=node.lineno, category=HoleCategory.STUB_CLASS,
                name=node.name, snippet=f"class {node.name}: <empty>"
            ))
        self.generic_visit(node)

    def _check_mock_returns(self, body: list[ast.stmt]):
        """Check for Mock-related return statements."""
        for stmt in body:
            if isinstance(stmt, ast.Return) and stmt.value:
                code = ast.get_source_segment("".join(self.source_lines), stmt)
                if code and any(kw in code for kw in ("Mock(", "MagicMock(", "patch(", "sentinel")):
                    self.holes.append(Hole(
                        file="", line=stmt.lineno, category=HoleCategory.MOCK_RETURN,
                        name=self._func_stack[-1] if self._func_stack else "",
                        snippet=code.strip()
                    ))


# ── CodeHoleDetector ───────────────────────────────────────────────────────────

class CodeHoleDetector:
    """Detects code holes in Python projects.

    Scans `.py` files using AST analysis to find empty interfaces, placeholders,
    mock returns, NotImplementedError stubs, and TODO markers.
    """

    # Files/directories to always exclude from scanning
    DEFAULT_EXCLUDES: set[str] = {
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
        "dist", "build", "*.egg-info", ".eggs",
    }

    # Patterns that indicate TODO-like markers
    TODO_PATTERNS: list[str] = [
        "# TODO", "# FIXME", "# HACK", "# XXX", "# BUG",
        "# WORKAROUND", "# TEMP", "# OPTIMIZE", "# REFACTOR",
    ]

    # Hole ratio thresholds
    WARNING_THRESHOLD = 0.10   # >10% hole ratio = warning
    CRITICAL_THRESHOLD = 0.25  # >25% hole ratio = critical

    def __init__(
        self,
        warning_threshold: float = 0.10,
        critical_threshold: float = 0.25,
        excludes: set[str] | None = None,
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.excludes = excludes or self.DEFAULT_EXCLUDES

    # ── Public API ─────────────────────────────────────────────────────────

    def scan_file(self, file_path: str | Path) -> FileReport:
        """Scan a single Python file for code holes."""
        path = Path(file_path)

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return FileReport(file=str(path))

        source_lines = source.splitlines(keepends=True)
        total_lines = len(source_lines)

        # Parse AST
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            # File has syntax errors — still check for TODO markers
            tree = None

        # AST-based hole detection
        visitor = _HoleVisitor(source_lines)
        if tree:
            visitor.visit(tree)

        # Line-based TODO detection
        todo_holes = self._scan_todos(source_lines)

        all_holes = visitor.holes + todo_holes
        for h in all_holes:
            h.file = str(path)

        hole_lines = len(set(h.line for h in all_holes))
        hole_ratio = hole_lines / total_lines if total_lines > 0 else 0.0

        if hole_ratio >= self.critical_threshold:
            status = "critical"
        elif hole_ratio >= self.warning_threshold:
            status = "warning"
        else:
            status = "healthy"

        return FileReport(
            file=str(path),
            total_lines=total_lines,
            hole_lines=hole_lines,
            hole_ratio=hole_ratio,
            holes=all_holes,
            status=status,
        )

    def scan_directory(self, dir_path: str | Path) -> HoleReport:
        """Scan a directory recursively for code holes."""
        root = Path(dir_path).resolve()
        if not root.is_dir():
            raise ValueError(f"Not a directory: {root}")

        report = HoleReport(scan_root=str(root))

        py_files = self._collect_python_files(root)
        report.total_files = len(py_files)

        for py_file in py_files:
            file_report = self.scan_file(py_file)
            rel_path = str(py_file.relative_to(root))
            report.files[rel_path] = file_report
            report.total_lines += file_report.total_lines
            report.total_holes += len(file_report.holes)

        # Aggregate statistics
        report.overall_hole_ratio = (
            report.total_holes / report.total_lines
            if report.total_lines > 0 else 0.0
        )

        # Category breakdown
        for fr in report.files.values():
            for hole in fr.holes:
                cat = hole.category.value
                report.by_category[cat] = report.by_category.get(cat, 0) + 1

        # Priority modules (hole ratio > critical threshold)
        report.priority_modules = sorted(
            [f for f, fr in report.files.items() if fr.hole_ratio >= self.critical_threshold],
            key=lambda f: report.files[f].hole_ratio,
            reverse=True
        )

        return report

    def scan_multiple(self, directories: list[str | Path]) -> HoleReport:
        """Scan multiple directories and merge into one report."""
        merged: HoleReport | None = None
        for d in directories:
            r = self.scan_directory(d)
            if merged is None:
                merged = r
                merged.scan_root = ", ".join(str(d) for d in directories)
            else:
                merged.total_files += r.total_files
                merged.total_lines += r.total_lines
                merged.total_holes += r.total_holes
                merged.files.update(r.files)
                for cat, count in r.by_category.items():
                    merged.by_category[cat] = merged.by_category.get(cat, 0) + count
                merged.priority_modules.extend(r.priority_modules)
        if merged is None:
            merged = HoleReport(scan_root=", ".join(str(d) for d in directories))
        else:
            merged.overall_hole_ratio = (
                merged.total_holes / merged.total_lines
                if merged.total_lines > 0 else 0.0
            )
            merged.priority_modules.sort(
                key=lambda f: merged.files[f].hole_ratio if f in merged.files else 0,
                reverse=True
            )
        return merged

    # ── Reports ────────────────────────────────────────────────────────────

    def to_markdown(self, report: HoleReport) -> str:
        """Render a HoleReport as Markdown."""
        lines = [
            f"# 🕳️ Code Hole Detection Report",
            f"**Scan root**: {report.scan_root}",
            f"**Timestamp**: {report.timestamp}",
            f"**Files scanned**: {report.total_files}",
            f"**Total lines**: {report.total_lines}",
            f"**Total holes**: {report.total_holes}",
            f"**Overall hole ratio**: {report.overall_hole_ratio:.1%}",
            "",
            "## 📊 Category Breakdown",
        ]

        for cat in sorted(report.by_category.keys(), key=lambda c: report.by_category[c], reverse=True):
            count = report.by_category[cat]
            lines.append(f"- **{cat}**: {count}")

        # Per-file breakdown (sorted by hole ratio)
        lines.append("")
        lines.append("## 📁 File Breakdown (by hole ratio)")
        lines.append("| File | Lines | Holes | Ratio | Status |")
        lines.append("|------|------:|------:|------:|--------|")

        sorted_files = sorted(
            report.files.items(),
            key=lambda x: x[1].hole_ratio,
            reverse=True
        )
        for rel_path, fr in sorted_files:
            if fr.hole_ratio == 0 and fr.total_lines == 0:
                continue
            emoji = {"healthy": "🟢", "warning": "🟡", "critical": "🔴"}.get(fr.status, "⚪")
            lines.append(
                f"| {rel_path} | {fr.total_lines} | {fr.hole_lines} | "
                f"{fr.hole_ratio:.1%} | {emoji} {fr.status} |"
            )

        # Priority modules
        if report.priority_modules:
            lines.append("")
            lines.append("## 🔴 Priority Modules (hole ratio > {:.0%})".format(self.critical_threshold))
            for mod in report.priority_modules[:10]:
                fr = report.files.get(mod)
                if fr:
                    lines.append(f"- **{mod}** ({fr.hole_ratio:.1%}): {len(fr.holes)} holes")
                    for hole in fr.holes[:3]:
                        lines.append(f"  - L{hole.line}: [{hole.category.value}] {hole.snippet}")

        # Detailed holes
        lines.append("")
        lines.append("## 🔍 All Holes (by file)")
        for rel_path, fr in sorted_files[:20]:
            if not fr.holes:
                continue
            lines.append(f"\n### {rel_path} ({fr.hole_ratio:.1%})")
            for hole in fr.holes:
                cat_emoji = {
                    "empty_body": "🕳️", "mock_return": "🎭", "not_implemented": "🚧",
                    "placeholder": "📦", "todo_marker": "📝", "stub_class": "🏗️",
                    "blank_function": "📄"
                }.get(hole.category.value, "⚪")
                lines.append(
                    f"- {cat_emoji} L{hole.line}: `{hole.snippet[:80]}` "
                    f"[{hole.category.value}]"
                )

        return "\n".join(lines)

    def to_json(self, report: HoleReport) -> dict[str, Any]:
        """Serialize report to JSON-serializable dict."""
        return {
            "timestamp": report.timestamp,
            "scan_root": report.scan_root,
            "total_files": report.total_files,
            "total_lines": report.total_lines,
            "total_holes": report.total_holes,
            "overall_hole_ratio": round(report.overall_hole_ratio, 4),
            "by_category": report.by_category,
            "priority_modules": report.priority_modules,
            "files": {
                path: {
                    "total_lines": fr.total_lines,
                    "hole_lines": fr.hole_lines,
                    "hole_ratio": round(fr.hole_ratio, 4),
                    "status": fr.status,
                    "hole_count": len(fr.holes),
                    "categories": list(set(h.category.value for h in fr.holes)),
                }
                for path, fr in report.files.items()
            },
        }

    def save_report(
        self,
        report: HoleReport,
        output_dir: str = ".aionui/research/analysis",
        filename_md: str = "code_hole_report.md",
        filename_json: str = "code_hole_report.json",
    ) -> tuple[Path, Path]:
        """Save report as Markdown and JSON."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        md_path = out_dir / filename_md
        md_path.write_text(self.to_markdown(report), encoding="utf-8")

        json_path = out_dir / filename_json
        import json
        json_path.write_text(
            json.dumps(self.to_json(report), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        return md_path, json_path

    # ── Helpers ────────────────────────────────────────────────────────────

    def _collect_python_files(self, root: Path) -> list[Path]:
        """Collect all .py files recursively, excluding specified dirs."""
        files = []
        for path in root.rglob("*.py"):
            if any(excl in path.parts for excl in self.excludes):
                continue
            if path.name.startswith("."):
                continue
            files.append(path)
        return sorted(files)

    def _scan_todos(self, source_lines: list[str]) -> list[Hole]:
        """Line-based scan for TODO/FIXME/HACK markers."""
        holes = []
        for i, line in enumerate(source_lines, 1):
            stripped = line.strip()
            # Only check comment lines or lines containing comments
            if not stripped.startswith("#") and "#" not in stripped:
                continue
            for pattern in self.TODO_PATTERNS:
                if pattern in stripped:
                    holes.append(Hole(
                        file="", line=i, category=HoleCategory.TODO_MARKER,
                        severity=Severity.LOW,
                        name="", snippet=stripped[:80]
                    ))
                    break  # One hole per line
        return holes


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Code Hole Detector — Scan Python projects for empty interfaces and placeholders"
    )
    parser.add_argument(
        "--dir", nargs="+", default=["."],
        help="Directories to scan (default: current directory)"
    )
    parser.add_argument(
        "--warning-threshold", type=float, default=0.10,
        help="Hole ratio threshold for warning status (default: 0.10)"
    )
    parser.add_argument(
        "--critical-threshold", type=float, default=0.25,
        help="Hole ratio threshold for critical status (default: 0.25)"
    )
    parser.add_argument(
        "--output-dir", default=".aionui/research/analysis",
        help="Output directory for reports"
    )
    parser.add_argument(
        "--json-only", action="store_true",
        help="Only output JSON (no markdown)"
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Print summary only"
    )
    args = parser.parse_args()

    detector = CodeHoleDetector(
        warning_threshold=args.warning_threshold,
        critical_threshold=args.critical_threshold,
    )

    # Scan directories
    if len(args.dir) == 1:
        report = detector.scan_directory(args.dir[0])
    else:
        report = detector.scan_multiple(args.dir)

    # Output
    if args.summary:
        print(report.summary())
        if report.priority_modules:
            print(f"\nPriority modules ({len(report.priority_modules)}):")
            for mod in report.priority_modules:
                print(f"  - {mod}")
    else:
        print(detector.to_markdown(report))

    # Save reports
    md_path, json_path = detector.save_report(report, output_dir=args.output_dir)
    print(f"\nReports saved to:")
    print(f"  Markdown: {md_path}")
    print(f"  JSON:     {json_path}")

    # Exit with non-zero if critical holes found (for CI gating)
    if report.priority_modules:
        sys.exit(1)


if __name__ == "__main__":
    main()
