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
    "req": {"pattern": r"^REQ-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "REQ-001-CreateAccount", "hint": "Format: REQ-NNN-PascalCase"},
    "nfr": {"pattern": r"^NFR-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "NFR-001-ResponseTime", "hint": "Format: NFR-NNN-PascalCase"},
    "us": {"pattern": r"^US-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "US-001-Login", "hint": "Format: US-NNN-PascalCase"},
    "sc": {"pattern": r"^SC-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "SC-001-DataIntegrity", "hint": "Format: SC-NNN-PascalCase"},
    "ng": {"pattern": r"^NG-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "NG-001-WebSearch", "hint": "Format: NG-NNN-PascalCase"},
    # ── Glossary ──────────────────────────────────────────────────────────────
    "gl": {"pattern": r"^GL-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "GL-001-Authentication", "hint": "Format: GL-NNN-PascalCase"},
    "dg": {"pattern": r"^DG-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "DG-001-MinimizeCognitiveLoad", "hint": "Format: DG-NNN-PascalCase"},
    "scr": {"pattern": r"^SCR-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "SCR-001-LandingPage", "hint": "Format: SCR-NNN-PascalCase"},

    "dt": {"pattern": r"^DT-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "DT-001-PrimaryColor", "hint": "Format: DT-NNN-PascalCase"},
    "pat": {"pattern": r"^PAT-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "PAT-001-KeyboardNavigation", "hint": "Format: PAT-NNN-PascalCase"},
    "prs": {"pattern": r"^PRS-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "PRS-001-PowerDeveloper", "hint": "Format: PRS-NNN-PascalCase"},
    "spc": {"pattern": r"^SPC-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "SPC-001-LoginScreen", "hint": "Format: SPC-NNN-PascalCase"},
    "uj": {"pattern": r"^UJ-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "UJ-001-FindProduct", "hint": "Format: UJ-NNN-PascalCase"},
    "uxac": {"pattern": r"^UXAC-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "UXAC-001-TouchTarget", "hint": "Format: UXAC-NNN-PascalCase"},
    "vdr": {"pattern": r"^VDR-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "VDR-001-ContrastRatio", "hint": "Format: VDR-NNN-PascalCase"},
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
    "fn": {"pattern": r"^FN-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "FN-001-Authenticate", "hint": "Format: FN-NNN-PascalCase"},
    # ── TestSpec ──────────────────────────────────────────────────────────────
    "tst": {"pattern": r"^TST-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "TST-001-ExportReportAsPDF", "hint": "Format: TST-NNN-PascalCase"},
    "fc": {"pattern": r"^FC-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "FC-001-Authenticate", "hint": "Format: FC-NNN-PascalCase"},
    # ── TaskPlan / Issues ─────────────────────────────────────────────────────
    "ep": {"pattern": r"^EP-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "EP-001-UserOnboarding", "hint": "Format: EP-NNN-PascalCase"},
    "is": {"pattern": r"^IS-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "IS-001-ImplementLogin", "hint": "Format: IS-NNN-PascalCase"},
    "si": {"pattern": r"^SI-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "SI-001-CreateLoginSchema", "hint": "Format: SI-NNN-PascalCase"},
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
    "issues": "is",
    "subIssues": "si",
    # Glossary
    "terms": "gl",
}
