#!/usr/bin/env python3
"""
id_patterns.py — Canonical ID patterns (single source of truth).

All ID format patterns are defined here using composable parts.
If a part changes, update it below and all patterns update automatically.

Usage:
    from id_patterns import ID_PATTERNS

    # Validate an ID
    pattern = ID_PATTERNS["req"]["pattern"]
    hint = ID_PATTERNS["req"]["hint"]
"""

# ── Composable pattern parts ─────────────────────────────────────────────────
# Change these to update every ID pattern at once.

SEP = "-"                # separator between parts
ENUM = r"\d{3}"            # 3-digit number
SLUG = r"[A-Z][a-zA-Z0-9]*"  # PascalCase name

# ── ID definitions ───────────────────────────────────────────────────────────
# Each entry: (key, enumeration, slug)
# prefix = key.upper() automatically.

_ID_DEFS = [
    # GoalSpec
    ("req",    ENUM, SLUG),
    ("nfr",    ENUM, SLUG),
    ("us",     ENUM, SLUG),
    ("sc",     ENUM, SLUG),
    ("ng",     ENUM, SLUG),
    # Glossary
    ("gl",     ENUM, SLUG),
    ("dg",     ENUM, SLUG),
    ("scr",    ENUM, SLUG),
    ("dt",     ENUM, SLUG),
    ("pat",    ENUM, SLUG),
    ("prs",    ENUM, SLUG),
    ("spc",    ENUM, SLUG),
    ("uj",     ENUM, SLUG),
    ("uxac",   ENUM, SLUG),
    ("vdr",    ENUM, SLUG),
    # ArchitectureSpec
    ("comp",   ENUM, SLUG),
    ("con",    ENUM, SLUG),
    ("flw",    ENUM, SLUG),
    # DataSpec
    ("ent",    ENUM, SLUG),
    ("num",    ENUM, SLUG),
    ("prim",   ENUM, SLUG),
    ("rel",    ENUM, SLUG),
    # ApiSpec
    ("fn",     ENUM, SLUG),
    # TestSpec
    ("tst",    ENUM, SLUG),
    ("fc",     ENUM, SLUG),
    # TaskPlan / Issues
    ("ep",     ENUM, SLUG),
    ("is",     ENUM, SLUG),
    ("si",     ENUM, SLUG),
    # Milestones
    ("mil",    ENUM, SLUG),
]

# ── Build ID_PATTERNS from definitions ───────────────────────────────────────
ID_PATTERNS = {}
for key, enumeration, slug in _ID_DEFS:
    prefix = key.upper()
    pattern = rf"^{prefix}-{enumeration}-{slug}$"
    ID_PATTERNS[key] = {
        "pattern": pattern,
        "example": f"{prefix}-001-Example",
        "hint": f"Format: {prefix}-NNN-PascalCase",
    }

# Section path → ID pattern type mapping (single source of truth for ID validation)
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
    "functions": "fn",
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
