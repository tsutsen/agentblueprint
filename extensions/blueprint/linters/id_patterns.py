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

SEP = "-"                        # separator between parts
ENUM = r"\d{3}"                  # 3-digit number (used by most IDs)
ENUM_MIL = r"\d+"                # 1+ digit (used by milestones)
SLUG = r"[A-Z][a-zA-Z0-9]*"     # PascalCase name (used by most IDs)
SLUG_MIL = r"[A-Z][a-zA-Z]*"    # Name without digits (used by milestones)

# ── ID definitions ───────────────────────────────────────────────────────────
# Each entry: (key, prefix, enumeration, slug)
# Standard IDs use SEP+ENUM+SLUG; milestones use SEP+ENUM_MIL+SLUG_MIL.

_ID_DEFS = [
    # GoalSpec
    ("req",     "REQ", ENUM, SLUG),
    ("nfr",     "NFR", ENUM, SLUG),
    ("us",      "US",  ENUM, SLUG),
    ("sc",      "SC",  ENUM, SLUG),
    ("ng",      "NG",  ENUM, SLUG),
    # Glossary
    ("gl",      "GL",  ENUM, SLUG),
    ("dg",      "DG",  ENUM, SLUG),
    ("scr",     "SCR", ENUM, SLUG),
    ("dt",      "DT",  ENUM, SLUG),
    ("pat",     "PAT", ENUM, SLUG),
    ("prs",     "PRS", ENUM, SLUG),
    ("spc",     "SPC", ENUM, SLUG),
    ("uj",      "UJ",  ENUM, SLUG),
    ("uxac",    "UXAC", ENUM, SLUG),
    ("vdr",     "VDR", ENUM, SLUG),
    # ArchitectureSpec
    ("comp",    "COMP", ENUM, SLUG),
    ("con",     "CON",  ENUM, SLUG),
    ("flw",     "FLW",  ENUM, SLUG),
    # DataSpec
    ("ent",     "ENT",  ENUM, SLUG),
    ("num",     "NUM",  ENUM, SLUG),
    ("prim",    "PRIM", ENUM, SLUG),
    ("rel",     "REL",  ENUM, SLUG),
    # ApiSpec
    ("fn",      "FN",   ENUM, SLUG),
    # TestSpec
    ("tst",     "TST",  ENUM, SLUG),
    ("fc",      "FC",   ENUM, SLUG),
    # TaskPlan / Issues
    ("ep",      "EP",   ENUM, SLUG),
    ("is",      "IS",   ENUM, SLUG),
    ("si",      "SI",   ENUM, SLUG),
    # Milestone (special: 1+ digits, name without digits)
    ("milestone", "MIL", ENUM_MIL, SLUG_MIL),
]

# ── Build ID_PATTERNS from definitions ───────────────────────────────────────
ID_PATTERNS = {}
for key, prefix, enumeration, slug in _ID_DEFS:
    pattern = rf"^{prefix}-{enumeration}-{slug}$"
    ID_PATTERNS[key] = {
        "pattern": pattern,
        "example": f"{prefix}-001-Example",
        "hint": f"Format: {prefix}-NNN-PascalCase",
    }

# Special hint for milestone
ID_PATTERNS["milestone"]["hint"] = "Format: MIL-NNN-NamePascalCase (e.g. MIL-001-Setup)"


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
    "milestones": "milestone",
    "issues": "is",
    "subIssues": "si",
    # Glossary
    "terms": "gl",
}
