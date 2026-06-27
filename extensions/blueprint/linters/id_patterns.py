#!/usr/bin/env python3
"""
id_patterns.py — Canonical ID patterns (single source of truth).

All ID format patterns are defined here. Linters and schema tools must use
these instead of hardcoding patterns. If a pattern changes, update it here.

Usage:
    from id_patterns import ID_PATTERNS

    # Validate an ID
    pattern = ID_PATTERNS["req"]["pattern"]
    hint = ID_PATTERNS["req"]["hint"]
"""

ID_PATTERNS = {
    # ── GoalSpec ──────────────────────────────────────────────────────────────
    "req": {"pattern": r"^REQ-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "REQ-001-createAccount", "hint": "Format: REQ-NNN-lowerCamelCase"},
    "nfr": {"pattern": r"^NFR-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "NFR-001-responseTime", "hint": "Format: NFR-NNN-lowerCamelCase"},
    "us": {"pattern": r"^US-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "US-001-login", "hint": "Format: US-NNN-lowerCamelCase"},
    "sc": {"pattern": r"^SC-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "SC-001-dataIntegrity", "hint": "Format: SC-NNN-lowerCamelCase"},
    "ng": {"pattern": r"^NG-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "NG-001-webSearch", "hint": "Format: NG-NNN-lowerCamelCase"},
    # ── Glossary ──────────────────────────────────────────────────────────────
    "gl": {"pattern": r"^GL-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "GL-001-Authentication", "hint": "Format: GL-NNN-PascalCase"},
    "dg": {"pattern": r"^DG-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "DG-001-MinimizeCognitiveLoad", "hint": "Format: DG-NNN-PascalCase"},
    "scr": {"pattern": r"^SCR-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "SCR-001-LandingPage", "hint": "Format: SCR-NNN-PascalCase"},

    "dt": {"pattern": r"^DT-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "DT-001-PrimaryColor", "hint": "Format: DT-NNN-PascalCase"},
    "pat": {"pattern": r"^PAT-\d{3}$", "example": "PAT-001", "hint": "Format: PAT-NNN (3-digit zero-padded)"},
    "prs": {"pattern": r"^PRS-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "PRS-001-PowerDeveloper", "hint": "Format: PRS-NNN-PascalCase"},
    "spc": {"pattern": r"^SPC-\d{3}$", "example": "SPC-001", "hint": "Format: SPC-NNN (3-digit zero-padded)"},
    "uj": {"pattern": r"^UJ-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "UJ-001-findProduct", "hint": "Format: UJ-NNN-lowerCamelCase"},
    "uxac": {"pattern": r"^UXAC-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "UXAC-001-touchTarget", "hint": "Format: UXAC-NNN-lowerCamelCase"},
    "vdr": {"pattern": r"^VDR-\d{3}$", "example": "VDR-001", "hint": "Format: VDR-NNN (3-digit zero-padded)"},
    # ── ArchitectureSpec ──────────────────────────────────────────────────────
    "comp": {"pattern": r"^COMP-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "COMP-001-AuthService", "hint": "Format: COMP-NNN-PascalCase"},
    "con": {"pattern": r"^CON-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "CON-001-AuthenticationRequired", "hint": "Format: CON-NNN-PascalCase"},
    "flw": {"pattern": r"^FLW-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "FLW-001-SessionCreation", "hint": "Format: FLW-NNN-PascalCase"},
    # ── DataSpec ──────────────────────────────────────────────────────────────
    "ent": {"pattern": r"^ENT-\d{3}-[A-Z][A-Za-z0-9]*$", "example": "ENT-001-User", "hint": "Format: ENT-NNN-PascalCase"},
    "num": {"pattern": r"^NUM-\d{3}-[A-Z][A-Za-z0-9]*$", "example": "NUM-001-Status", "hint": "Format: NUM-NNN-PascalCase"},
    "prim": {"pattern": r"^PRIM-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "PRIM-001-UserId", "hint": "Format: PRIM-NNN-PascalCase"},
    "rel": {"pattern": r"^REL-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "REL-001-UserOrders", "hint": "Format: REL-NNN-PascalCase"},
    # ── ApiSpec ───────────────────────────────────────────────────────────────
    "fn": {"pattern": r"^FN-\d{3}-[a-z][A-Za-z0-9]*$", "example": "FN-001-authenticate", "hint": "Format: FN-NNN-lowerCamelCase"},
    # ── TestSpec ──────────────────────────────────────────────────────────────
    "tst": {"pattern": r"^TST-\d{3}-[a-z][A-Za-z0-9]*$", "example": "TST-001-exportReportAsPDF", "hint": "Format: TST-NNN-lowerCamelCase"},
    "fc": {"pattern": r"^FC-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "FC-001-authenticate", "hint": "Format: FC-NNN-lowerCamelCase"},
    # ── TaskPlan / Issues ─────────────────────────────────────────────────────
    "ep": {"pattern": r"^EP-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "EP-001-userOnboarding", "hint": "Format: EP-NNN-lowerCamelCase"},
    "is": {"pattern": r"^IS-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "IS-001-implementLogin", "hint": "Format: IS-NNN-lowerCamelCase"},
    "milestone": {"pattern": r"^MIL-\d+-[A-Z][a-zA-Z]*$", "example": "MIL-001-Setup", "hint": "Format: MIL-NNN-NamePascalCase (e.g. MIL-001-Setup)"},
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
    "milestones": "milestone",
    # Glossary
    "terms": "gl",
}
