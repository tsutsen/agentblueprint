#!/usr/bin/env python3
"""
output.py — Human-readable and JSON output formatting for lint results.

All linters import print_human / print_json_output from shared.py
which re-exports them.
"""

import json

from linter_types import LayerResult


def print_human(result: LayerResult, path: str = ""):
    """Print human-readable lint report."""
    print(f"\n{'─' * 60}")
    if path:
        print(f"  {result.name} Lint Report — {path}")
    else:
        print(f"  {result.name} Lint Report")
    print(f"{'─' * 60}")

    if not result.all_issues:
        print("  ✓ All checks passed.\n")
        return

    if result.errors:
        print(f"\n  ERRORS ({len(result.errors)}):")
        for e in result.errors:
            print(f"    ✗ [{e.category}] {e.message}")
            if e.hint:
                print(f"      → {e.hint}")

    if result.warnings:
        print(f"\n  WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"    ⚠ [{w.category}] {w.message}")
            if w.hint:
                print(f"      → {w.hint}")

    print(f"\n  {len(result.errors)} error(s), {len(result.warnings)} warning(s).\n")


def print_json_output(result: LayerResult):
    """Print JSON lint report."""
    out = {
        "clean": result.clean,
        "errors": [
            {"category": e.category, "message": e.message, "hint": e.hint}
            for e in result.errors
        ],
        "warnings": [
            {"category": w.category, "message": w.message, "hint": w.hint}
            for w in result.warnings
        ],
    }
    print(json.dumps(out, indent=2))
