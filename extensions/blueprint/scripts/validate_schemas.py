#!/usr/bin/env python3
"""
validate_schemas.py — Comprehensive schema pattern validation.

Verifies that all ID patterns and Ref fields in schema files are
consistent with shared.ID_PATTERNS (single source of truth).

Checks:
  1. Every x_idPattern key exists in shared.ID_PATTERNS
  2. Every inline pattern matches the canonical pattern for its x_idPattern
  3. Every definitions.*Id pattern matches shared.ID_PATTERNS
  4. Every *Ref array field uses $ref to a canonical definition

Usage:
    python validate_schemas.py
"""

import json
import re
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
LINTERS_DIR = SCRIPT_DIR.parent / "linters"
SCHEMAS_DIR = LINTERS_DIR.parent.parent.parent / "skills" / "blueprint" / "schemas"
SHARED_PATH = LINTERS_DIR / "shared.py"

# ── Canonical name mapping ───────────────────────────────────────────────────

CANONICAL_DEF_NAME = {
    "req": "reqId", "nfr": "nfrId", "us": "usId", "sc": "scId", "ng": "ngId",
    "gl": "glId", "dg": "dgId", "scr": "scrId", "dt": "dtId", "pat": "patId",
    "prs": "prsId", "spc": "spcId", "uj": "ujId", "uxac": "uxacId", "vdr": "vdrId",
    "comp": "compId", "con": "conId", "flw": "flwId", "ent": "entId",
    "num": "numId", "prim": "primId", "rel": "relId", "fn": "fnId",
    "tst": "tstId", "fc": "fcId", "ep": "epId", "is": "isId",
    "milestone": "milestoneId",
}

# Non-canonical definition name aliases → pattern key
DEF_NAME_ALIASES = {
    "flowId": "flw", "componentId": "comp", "entityId": "ent",
    "enumId": "num", "arId": None,
}

# Ref field name → pattern key
REF_TO_PATTERN = {
    "reqRefs": "req", "nfrRefs": "nfr", "usRefs": "us", "scRefs": "sc",
    "componentRefs": "comp", "componentRef": "comp",
    "glossaryRefs": "gl", "fnRef": "fn", "apiRef": "fn",
    "screenRefs": "scr", "screenRef": "scr", "ujRefs": "uj",
    "personaRef": "prs", "patternRefs": "pat", "patternRef": "pat",
    "constraintRefs": "con", "entityRefs": "ent",
    "inScopeGlossaryRefs": "gl", "outOfScopeGlossaryRefs": "gl",
    "titleGlossaryRefs": "gl",
}

# Fields that are intentionally NOT ID refs
SKIP_REF_FIELDS = {
    "dataSpecRef", "apiSpecRef", "designSystemRef", "typeRef",
    "archRefs", "designRefs", "wireframe",
}


# ── Load shared patterns ─────────────────────────────────────────────────────

def load_id_patterns() -> dict:
    """Parse shared.py to extract ID_PATTERNS as {key: pattern}."""
    if not SHARED_PATH.exists():
        print(f"ERROR: shared.py not found at {SHARED_PATH}")
        sys.exit(1)

    content = SHARED_PATH.read_text()
    patterns = {}
    for m in re.finditer(r'"(\w+)":\s*\{\s*"pattern":\s*r"((?:[^"\\]|\\.)*)"', content):
        patterns[m.group(1)] = m.group(2)
    return patterns


def get_pattern_key(def_name: str) -> str | None:
    """Resolve a definition name to its shared.ID_PATTERNS key."""
    if def_name in DEF_NAME_ALIASES:
        return DEF_NAME_ALIASES[def_name]
    for pk, cn in CANONICAL_DEF_NAME.items():
        if cn == def_name:
            return pk
    if def_name.endswith("Id"):
        key = def_name[:-2]
        if key in load_id_patterns():
            return key
    return None


# ── Validation ────────────────────────────────────────────────────────────────

def validate_schema(schema_path: Path, id_patterns: dict) -> list:
    """Validate one schema file. Returns list of error strings."""
    errors = []
    schema = json.loads(schema_path.read_text())
    sname = schema_path.stem

    def walk(obj, path="$", depth=0):
        if depth > 25:
            return
        if not isinstance(obj, dict):
            if isinstance(obj, list):
                for item in obj:
                    walk(item, path, depth + 1)
            return

        # 1. Check x_idPattern + inline pattern match
        x_id = obj.get("x_idPattern")
        pattern = obj.get("pattern")
        if x_id and pattern:
            if x_id not in id_patterns:
                errors.append(
                    f"{sname}: {path} — x_idPattern='{x_id}' "
                    f"not in shared.ID_PATTERNS"
                )
            elif pattern != id_patterns[x_id]:
                errors.append(
                    f"{sname}: {path} — x_idPattern='{x_id}' "
                    f"pattern mismatch\n"
                    f"    schema: {pattern}\n"
                    f"    shared: {id_patterns[x_id]}"
                )

        # 2. Check definitions.*Id patterns
        for def_name, def_val in obj.get("definitions", {}).items():
            if not isinstance(def_val, dict) or "pattern" not in def_val:
                continue
            pk = get_pattern_key(def_name)
            if pk and pk in id_patterns:
                if def_val["pattern"] != id_patterns[pk]:
                    errors.append(
                        f"{sname}: definitions.{def_name} — pattern mismatch\n"
                        f"    schema: {def_val['pattern']}\n"
                        f"    shared: {id_patterns[pk]}"
                    )

        # 3. Check *Ref array fields use $ref
        for key, val in obj.get("properties", {}).items():
            if key in SKIP_REF_FIELDS:
                continue
            if not ("Ref" in key or key == "refs"):
                continue
            if not isinstance(val, dict) or val.get("type") != "array":
                continue
            items = val.get("items", {})
            if "$ref" not in items and REF_TO_PATTERN.get(key):
                canon = CANONICAL_DEF_NAME.get(REF_TO_PATTERN[key], "")
                errors.append(
                    f"{sname}: properties.{key} — no $ref "
                    f"(expected #{canon})"
                )

        # Recurse
        for key, val in obj.items():
            if isinstance(val, dict):
                walk(val, f"{path}.{key}", depth + 1)
            elif isinstance(val, list):
                for item in val:
                    walk(item, path, depth + 1)

    walk(schema)
    return errors


def main():
    id_patterns = load_id_patterns()
    all_errors = []

    for schema_path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        all_errors.extend(validate_schema(schema_path, id_patterns))

    if all_errors:
        print(f"✗ {len(all_errors)} error(s) found:")
        for e in all_errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(
            f"✓ All schema patterns are valid "
            f"({len(id_patterns)} shared patterns)"
        )


if __name__ == "__main__":
    main()
