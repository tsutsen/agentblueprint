#!/usr/bin/env python3
"""
shared.py — Canonical types and output formatting for all linters.

All linters should import from this module instead of defining their own
Issue and LayerResult types. This ensures consistent output across all
linters, which is critical for agents that parse lint results.

Usage in a linter:
    from shared import Issue, LayerResult, print_human, print_json_output, ID_PATTERNS
"""

import json
import re
from dataclasses import dataclass, field


# ── Canonical ID patterns (single source of truth) ────────────────────────────
# All ID format patterns are defined here. Linters must use these instead of
# hardcoding patterns. If a pattern changes, update it in one place.

ID_PATTERNS = {
    # GoalSpec
    "req": {"pattern": r"^REQ-\d{3}$", "example": "REQ-001", "hint": "Format: REQ-NNN (3-digit zero-padded)"},
    "nfr": {"pattern": r"^NFR-\d{3}$", "example": "NFR-001", "hint": "Format: NFR-NNN (3-digit zero-padded)"},
    "us": {"pattern": r"^US-\d{3}$", "example": "US-001", "hint": "Format: US-NNN (3-digit zero-padded)"},
    "sc": {"pattern": r"^SC-\d{3}$", "example": "SC-001", "hint": "Format: SC-NNN (3-digit zero-padded)"},
    "ng": {"pattern": r"^NG-\d{3}$", "example": "NG-001", "hint": "Format: NG-NNN (3-digit zero-padded)"},
    # Glossary
    "gl": {"pattern": r"^GL-\d{3}$", "example": "GL-001", "hint": "Format: GL-NNN (3-digit zero-padded)"},
    # DesignSpec
    "dg": {"pattern": r"^DG-\d{3}$", "example": "DG-001", "hint": "Format: DG-NNN (3-digit zero-padded)"},
    "scr": {"pattern": r"^SCR-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "SCR-001-landingPage", "hint": "Format: SCR-NNN-lowerCamelCase"},
    "dcon": {"pattern": r"^DCON-\d{3}$", "example": "DCON-001", "hint": "Format: DCON-NNN (3-digit zero-padded)"},
    # ArchitectureSpec
    "comp": {"pattern": r"^[a-zA-Z][a-zA-Z0-9]*$", "example": "AuthService", "hint": "Format: PascalCase component name"},
    "con": {"pattern": r"^CON-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "CON-001-AuthenticationRequired", "hint": "Format: CON-NNN-PascalCase"},
    "flw": {"pattern": r"^FLW-\d{3}-[a-z][a-z0-9]*(-[a-z0-9]+)*$", "example": "FLW-001-session-creation", "hint": "Format: FLW-NNN-kebab-case"},
    "dfw": {"pattern": r"^[a-z][a-z0-9-]*$", "example": "query-routing-flow", "hint": "Format: kebab-case lowercase"},
    # DataSpec
    "ent": {"pattern": r"^ENT-\d{3}-[A-Z][A-Za-z0-9]*$", "example": "ENT-001-User", "hint": "Format: ENT-NNN-PascalCase"},
    "num": {"pattern": r"^NUM-\d{3}-[A-Z][A-Za-z0-9]*$", "example": "NUM-001-UserName", "hint": "Format: NUM-NNN-PascalCase"},
    # ApiSpec
    "fn": {"pattern": r"^FN-\d{3}-[a-z][A-Za-z0-9]*$", "example": "FN-001-authenticate", "hint": "Format: FN-NNN-lowerCamelCase"},
    # TestSpec
    "tst": {"pattern": r"^TST-\d{3}-[a-z][A-Za-z0-9]*$", "example": "TST-001-exportReportAsPDF", "hint": "Format: TST-NNN-testName (lowerCamelCase name suffix)"},
}


def validate_id_format(id_value: str, id_type: str) -> tuple[bool, str]:
    """Validate an ID against its canonical pattern.
    
    Returns (is_valid, error_message).
    """
    if id_type not in ID_PATTERNS:
        return True, ""  # Unknown type, skip validation
    pattern = ID_PATTERNS[id_type]["pattern"]
    if re.match(pattern, id_value):
        return True, ""
    return False, f"ID '{id_value}' does not follow {ID_PATTERNS[id_type]['hint'].lower()}"


# Backwards compatibility alias
ID_FORMATS = ID_PATTERNS


# ── Canonical types ───────────────────────────────────────────────────────────

@dataclass
class Issue:
    """A single lint finding."""
    severity: str          # "error" | "warning" | "info"
    category: str          # e.g. "schema", "duplicate_id", "cross-ref"
    message: str           # Human-readable description of the issue
    hint: str = ""         # Optional suggestion for how to fix


@dataclass
class LayerResult:
    """Result from a single lint layer (one spec or cross-spec check)."""
    name: str = ""
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    @property
    def all_issues(self):
        return self.errors + self.warnings

    def add(self, severity: str, category: str, message: str, hint: str = ""):
        issue = Issue(severity, category, message, hint)
        if severity == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)


# ── Output formatting ────────────────────────────────────────────────────────

def print_human(result: LayerResult, path: str = ""):
    """Print human-readable lint report."""
    print(f"\n{'─'*60}")
    if path:
        print(f"  {result.name} Lint Report — {path}")
    else:
        print(f"  {result.name} Lint Report")
    print(f"{'─'*60}")

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
        "errors": [{"category": e.category, "message": e.message, "hint": e.hint} for e in result.errors],
        "warnings": [{"category": w.category, "message": w.message, "hint": w.hint} for w in result.warnings]
    }
    print(json.dumps(out, indent=2))
