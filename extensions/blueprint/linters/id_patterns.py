#!/usr/bin/env python3
"""
id_patterns.py — Canonical ID patterns (derived from proto-schema refs.yaml).

Imports pattern definitions from the proto-schema single source of truth
and builds the ID_PATTERNS dict used by linters.

Also provides SECTION_ID_PATTERNS mapping JSON paths to ID types,
which is structural metadata not encoded in refs.yaml.
"""

from pathlib import Path
import yaml

# ── Load patterns from proto-schema refs.yaml (single source of truth) ──────

_REFS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "skills" / "blueprint" / "schemas" / "proto" / "blocks" / "refs.yaml"

def _load_refs():
    """Load ID patterns from refs.yaml."""
    if _REFS_PATH.exists():
        with open(_REFS_PATH) as f:
            refs = yaml.safe_load(f) or {}
    else:
        refs = {}

    # Build ID_PATTERNS from refs.yaml
    patterns = {}
    for key, info in refs.items():
        patterns[key] = {
            "pattern": info["pattern"],
            "example": f"{key.upper()}-001-Example",
            "hint": f"Format: {key.upper()}-NNN-PascalCase",
        }
    return patterns


ID_PATTERNS = _load_refs()

# ── Section path → ID pattern type mapping ──────────────────────────────────
# Structural metadata: maps JSON artifact paths to the ID type they contain.
# Not derivable from refs.yaml — lives here as linter configuration.

SECTION_ID_PATTERNS = {
    # GoalSpec
    "functionalRequirements": "req",
    "nonFunctionalRequirements": "nfr",
    "userStories": "us",
    "successCriteria": "sc",
    "nonGoals": "ng",
    # DesignSpec
    "designGoals": "dg",
    "personas": "prs",
    "userJourneys": "uj",
    "screenInventory": "scr",
    "screenSpecs": "spc",
    "interactionPatterns": "pat",
    "uxAcceptanceCriteria": "uxac",
    "visualDesignRequirements": "vdr",
    # ArchSpec
    "components": "comp",
    "dataFlow": "flw",
    "constraints": "con",
    # DataSpec
    "primitives": "prim",
    "enums": "num",
    "entities": "ent",
    "relationships": "rel",
    # ApiSpec
    "functions": "endp",
    # TestSpec
    "tests": "tst",
    "functionCoverage": "fc",
    # TaskPlan
    "epics": "ep",
    "milestones": "mil",
    "issues": "is",
    "subIssues": "si",
    # Glossary
    "terms": "gl",
}
