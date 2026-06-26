#!/usr/bin/env python3
"""
fix_schema_patterns.py — Align all schema ID patterns with shared.ID_PATTERNS.

Reads shared.ID_PATTERNS as the single source of truth and:
1. Fixes every definitions.*Id pattern to match shared.ID_PATTERNS
2. Converts inline `pattern` on `id` fields to $ref when a matching definition exists
3. Converts bare string arrays on *Ref fields to $ref when a matching definition exists
4. Removes unused definitions that duplicate canonical ones

Usage:
    python fix_schema_patterns.py           # dry-run (show changes)
    python fix_schema_patterns.py --apply   # write changes
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

# ── Load shared.ID_PATTERNS ──────────────────────────────────────────────────

def load_id_patterns() -> dict:
    """Parse shared.py to extract ID_PATTERNS with pattern → key mapping."""
    content = SHARED_PATH.read_text()
    patterns = {}
    for m in re.finditer(r'"(\w+)":\s*\{\s*"pattern":\s*r"((?:[^"\\]|\\.)*)"', content):
        key = m.group(1)
        pattern = m.group(2)
        patterns[key] = pattern
    return patterns

# ── Mapping: x_idPattern key → definition name in each schema ────────────────
# Most schemas use the convention: pattern key "req" → definition "reqId"
# Some use alternative names; map them explicitly.

# Canonical mapping: pattern_key → preferred definition name
CANONICAL_DEF_NAME = {
    "req": "reqId",
    "nfr": "nfrId",
    "us": "usId",
    "sc": "scId",
    "ng": "ngId",
    "gl": "glId",
    "dg": "dgId",
    "scr": "scrId",
    "dt": "dtId",
    "pat": "patId",
    "prs": "prsId",
    "spc": "spcId",
    "uj": "ujId",
    "uxac": "uxacId",
    "vdr": "vdrId",
    "comp": "compId",
    "con": "conId",
    "flw": "flwId",
    "ent": "entId",
    "num": "numId",
    "prim": "primId",
    "rel": "relId",
    "fn": "fnId",
    "tst": "tstId",
    "fc": "fcId",
    "ep": "epId",
    "is": "isId",
    "milestone": "milestoneId",
}

# Non-canonical definition name aliases → pattern key
# Some schemas use "flowId" instead of "flwId", "componentId" instead of "compId", etc.
DEF_NAME_ALIASES = {
    "flowId": "flw",
    "componentId": "comp",
    "entityId": "ent",
    "enumId": "num",
    "arId": None,   # freeform arch ref, not a canonical ID
}

# Ref field name → pattern key (what ID type this ref should reference)
REF_TO_PATTERN = {
    "reqRefs": "req",
    "nfrRefs": "nfr",
    "usRefs": "us",
    "scRefs": "sc",
    "ngRefs": "ng",
    "componentRefs": "comp",
    "componentRef": "comp",
    "dataRef": "ent",
    "glRefs": "gl",
    "glossaryRefs": "gl",
    "fnRef": "fn",
    "apiRef": "fn",
    "screenRefs": "scr",
    "screenRef": "scr",
    "ujRefs": "uj",
    "personaRef": "prs",
    "patternRefs": "pat",
    "patternRef": "pat",
    "constraintRefs": "con",
    "entityRefs": "ent",
    "inScopeGlossaryRefs": "gl",
    "outOfScopeGlossaryRefs": "gl",
    "titleGlossaryRefs": "gl",
}

# Fields that are intentionally NOT ID refs (file paths, freeform, etc.)
SKIP_REF_FIELDS = {
    "dataSpecRef",      # file path
    "apiSpecRef",       # file path
    "designSystemRef",  # freeform / URL
    "typeRef",          # parameter type descriptor
    "archRefs",         # freeform architecture references
    "designRefs",       # freeform design references
    "wireframe",        # freeform text
    "designRefs",       # freeform
    "archRefs",         # freeform
}

# ── Schema fixer ──────────────────────────────────────────────────────────────

class SchemaFixer:
    def __init__(self, schema_path: Path, id_patterns: dict, apply: bool = False):
        self.schema_path = schema_path
        self.schema_name = schema_path.stem
        self.id_patterns = id_patterns
        self.apply = apply
        self.changes = []
        self.schema = json.loads(schema_path.read_text())

    def run(self):
        """Execute all fixes and report."""
        self._fix_definitions()
        self._fix_id_fields()
        self._fix_ref_fields()
        self._cleanup_unused_defs()
        self._write_if_applied()
        return self.changes

    def _log(self, msg: str):
        self.changes.append(f"  {self.schema_name}: {msg}")

    # ── 1. Fix definitions ───────────────────────────────────────────────────

    def _fix_definitions(self):
        """Update every definitions.*Id pattern to match shared.ID_PATTERNS."""
        defs = self.schema.get("definitions", {})

        # Build reverse mapping: existing def name → pattern key
        # by checking x_idPattern on all id fields that $ref this definition
        def_to_pattern = {}
        self._find_def_usage(self.schema, def_to_pattern)

        for def_name, def_val in list(defs.items()):
            if not isinstance(def_val, dict):
                continue

            # Find which pattern key this definition maps to
            pattern_key = def_to_pattern.get(def_name)
            if not pattern_key:
                # Try to infer from name (e.g., "reqId" → "req")
                pattern_key = self._infer_pattern_key(def_name)

            if not pattern_key or pattern_key not in self.id_patterns:
                continue

            expected_pattern = self.id_patterns[pattern_key]
            current_pattern = def_val.get("pattern", "")

            if current_pattern != expected_pattern:
                self._log(
                    f"definitions.{def_name}: pattern "
                    f"'{current_pattern}' → '{expected_pattern}'"
                )
                if self.apply:
                    def_val["pattern"] = expected_pattern

    def _find_def_usage(self, obj, mapping: dict):
        """Walk schema to find which definitions are $ref'd by id fields with x_idPattern."""
        if isinstance(obj, dict):
            # Check if this is an id field with x_idPattern that $refs a definition
            if obj.get("x_idPattern") and "$ref" in obj:
                ref = obj["$ref"]
                def_name = ref.split("/")[-1] if "/" in ref else ref
                mapping[def_name] = obj["x_idPattern"]

            for key, val in obj.items():
                # Special handling: if key is "id" and val is a dict with x_idPattern
                if key == "id" and isinstance(val, dict) and val.get("x_idPattern"):
                    if "$ref" in val:
                        ref = val["$ref"]
                        def_name = ref.split("/")[-1] if "/" in ref else ref
                        mapping[def_name] = val["x_idPattern"]
                    elif "pattern" in val:
                        # Inline pattern — find or create the right definition
                        pattern_key = val["x_idPattern"]
                        canon_name = CANONICAL_DEF_NAME.get(pattern_key)
                        if canon_name:
                            mapping[canon_name] = pattern_key

                if isinstance(val, (dict, list)):
                    self._find_def_usage(val, mapping)

        elif isinstance(obj, list):
            for item in obj:
                self._find_def_usage(item, mapping)

    def _infer_pattern_key(self, def_name: str) -> str | None:
        """Infer the pattern key from a definition name."""
        # Check explicit aliases first (non-canonical names)
        if def_name in DEF_NAME_ALIASES:
            return DEF_NAME_ALIASES[def_name]

        # Reverse lookup: "reqId" → "req"
        for pattern_key, canon_name in CANONICAL_DEF_NAME.items():
            if canon_name == def_name:
                return pattern_key

        # Try stripping "Id" suffix
        if def_name.endswith("Id"):
            key = def_name[:-2]
            if key in self.id_patterns:
                return key

        return None

    # ── 2. Fix id fields ─────────────────────────────────────────────────────

    def _fix_id_fields(self):
        """Fix inline pattern on id fields: convert to $ref or update pattern."""
        self._walk_and_fix_id(self.schema, "$")

    def _walk_and_fix_id(self, obj, path: str):
        """Recursively find and fix id fields with inline patterns."""
        if isinstance(obj, dict):
            # Check properties at this level
            for key, val in obj.get("properties", {}).items():
                if key == "id" and isinstance(val, dict):
                    self._fix_inline_id(val, path, canon_key="id")

            # Recurse into all nested structures
            for key, val in obj.items():
                if key in ("properties",):  # already handled above
                    # Recurse into each property value
                    for pk, pv in val.items():
                        if isinstance(pv, (dict, list)):
                            self._walk_and_fix_id(pv, f"{path}.properties.{pk}")
                elif key == "items":
                    if isinstance(val, dict):
                        # Check if items itself is an id field
                        if val.get("x_idPattern") and "pattern" in val and "$ref" not in val:
                            self._fix_inline_id(val, path, canon_key="items")
                        # Recurse into items
                        self._walk_and_fix_id(val, f"{path}.items")
                elif isinstance(val, dict):
                    self._walk_and_fix_id(val, f"{path}.{key}")
                elif isinstance(val, list):
                    for i, item in enumerate(val):
                        self._walk_and_fix_id(item, f"{path}[{i}]")

    def _fix_inline_id(self, val: dict, path: str, canon_key: str):
        """Fix an id field with inline pattern: use $ref or fix pattern."""
        x_id = val.get("x_idPattern")
        if not x_id or "$ref" in val or "pattern" not in val:
            return

        expected_pattern = self.id_patterns.get(x_id)
        current_pattern = val.get("pattern", "")

        if expected_pattern and current_pattern != expected_pattern:
            canon_name = CANONICAL_DEF_NAME.get(x_id)
            defs = self.schema.get("definitions", {})
            target_def = canon_name if canon_name and canon_name in defs else None

            # If canonical def doesn't exist, create it
            if not target_def and self.apply and canon_name:
                self._create_definition(canon_name, x_id)
                target_def = canon_name

            if target_def:
                self._log(
                    f"{path}.{canon_key}: inline pattern → "
                    f"$ref '#/definitions/{target_def}'"
                )
                if self.apply:
                    desc = val.get("description", "")
                    val.clear()
                    val["$ref"] = f"#/definitions/{target_def}"
                    if desc:
                        val["description"] = desc
                    val["x_idPattern"] = x_id
            else:
                # Fallback: just fix the inline pattern
                self._log(
                    f"{path}.{canon_key}: inline pattern "
                    f"'{current_pattern}' → '{expected_pattern}'"
                )
                if self.apply:
                    val["pattern"] = expected_pattern

    # ── 3. Fix Ref fields ────────────────────────────────────────────────────

    def _fix_ref_fields(self):
        """Convert bare string arrays on *Ref fields to use $ref."""
        self._walk_and_fix_refs(self.schema, "$")

    def _walk_and_fix_refs(self, obj, path: str):
        """Recursively find and fix Ref fields without $ref."""
        if isinstance(obj, dict):
            # Check properties at this level
            for key, val in obj.get("properties", {}).items():
                if key in SKIP_REF_FIELDS:
                    continue
                if ("Ref" in key or key == "refs") and isinstance(val, dict):
                    if val.get("type") == "array":
                        items = val.get("items", {})
                        if "$ref" not in items:
                            pattern_key = REF_TO_PATTERN.get(key)
                            if pattern_key:
                                canon_name = CANONICAL_DEF_NAME.get(pattern_key)
                                defs = self.schema.get("definitions", {})
                                target_def = canon_name if canon_name in defs else None

                                # If definition doesn't exist, create it
                                if not target_def and self.apply and canon_name:
                                    self._create_definition(canon_name, pattern_key)
                                    target_def = canon_name

                                if target_def:
                                    self._log(
                                        f"{path}.{key}: bare string[] → "
                                        f"items.$ref '#/definitions/{target_def}'"
                                    )
                                    if self.apply:
                                        items["$ref"] = f"#/definitions/{target_def}"

            # Recurse into nested structures
            for key, val in obj.items():
                if key == "properties":
                    for pk, pv in val.items():
                        if isinstance(pv, (dict, list)):
                            self._walk_and_fix_refs(pv, f"{path}.properties.{pk}")
                elif key == "items" and isinstance(val, dict):
                    self._walk_and_fix_refs(val, f"{path}.items")
                elif isinstance(val, dict):
                    self._walk_and_fix_refs(val, f"{path}.{key}")

    def _create_definition(self, def_name: str, pattern_key: str):
        """Create a definition entry for a pattern key."""
        if pattern_key not in self.id_patterns:
            return
        defs = self.schema.setdefault("definitions", {})
        if def_name in defs:
            return
        pattern = self.id_patterns[pattern_key]
        prefix = pattern.split("-")[0]  # e.g., "REQ"
        defs[def_name] = {
            "type": "string",
            "description": f"{prefix} identifier.",
            "pattern": pattern,
        }
        self._log(f"CREATED definitions.{def_name}: pattern '{pattern}'")

    # ── 4. Cleanup unused definitions ────────────────────────────────────────

    def _cleanup_unused_defs(self):
        """Report definitions that exist but aren't $ref'd anywhere."""
        defs = set(self.schema.get("definitions", {}).keys())
        text = json.dumps(self.schema)
        referenced = set()
        for m in re.finditer(r'"\$ref":\s*"#/definitions/([^"]+)"', text):
            referenced.add(m.group(1))

        # Also check for definitions used as non-$ref patterns (keep those)
        non_id_defs = {"tbd", "planguageLevel", "typeRef", "parameterObject",
                       "errorCondition", "epicStatus", "testCategory",
                       "concreteValue", "glossaryRefItem", "acceptanceCriterion",
                       "scopeItem", "iaNode", "namedRequirement"}
        unused = defs - referenced - non_id_defs

        if unused:
            self._log(f"UNUSED definitions (review manually): {sorted(unused)}")

    # ── Write ────────────────────────────────────────────────────────────────

    def _write_if_applied(self):
        if self.apply:
            # Ensure definitions exist for patterns we reference
            self._ensure_definitions()
            output = json.dumps(self.schema, indent=2) + "\n"
            self.schema_path.write_text(output)

    def _ensure_definitions(self):
        """Ensure all canonical definitions referenced by $ref exist."""
        defs = self.schema.setdefault("definitions", {})
        text = json.dumps(self.schema)

        for m in re.finditer(r'"\$ref":\s*"#/definitions/([^"]+)"', text):
            def_name = m.group(1)
            if def_name not in defs:
                # Infer pattern key from def name
                pattern_key = self._infer_pattern_key(def_name)
                if pattern_key and pattern_key in self.id_patterns:
                    pattern = self.id_patterns[pattern_key]
                    prefix = pattern.split("-")[0]  # e.g., "REQ"
                    defs[def_name] = {
                        "type": "string",
                        "description": f"{prefix} identifier.",
                        "pattern": pattern,
                    }
                    self._log(f"CREATED definitions.{def_name}: pattern '{pattern}'")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    apply = "--apply" in sys.argv
    if apply:
        print("🔧 Applying schema pattern fixes...")
    else:
        print("🔍 Dry-run: showing schema pattern fixes needed...")
    print()

    id_patterns = load_id_patterns()

    all_changes = []
    for schema_path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        fixer = SchemaFixer(schema_path, id_patterns, apply=apply)
        changes = fixer.run()
        all_changes.extend(changes)

    print(f"\n{'=' * 70}")
    if all_changes:
        print("Changes needed:")
        for c in all_changes:
            print(c)
    else:
        print("✓ All schema patterns are aligned with shared.ID_PATTERNS!")

    if not apply:
        print(f"\nRun with --apply to write changes.")
    else:
        print(f"\n✓ Written {len(all_changes)} changes.")


if __name__ == "__main__":
    main()
