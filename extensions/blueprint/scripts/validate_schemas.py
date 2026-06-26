#!/usr/bin/env python3
"""
validate_schemas.py — Verify that all schema x_idPattern references
match valid keys in shared.ID_PATTERNS.

Usage:
    python validate_schemas.py
"""

import json
import os
import re
import sys
from pathlib import Path

# Load shared patterns
def load_shared_patterns(linters_dir: Path) -> dict:
    """Parse shared.py to extract ID_PATTERNS keys."""
    shared_path = linters_dir / "shared.py"
    if not shared_path.exists():
        print(f"ERROR: shared.py not found at {shared_path}")
        sys.exit(1)
    
    content = shared_path.read_text()
    keys = []
    for line in content.split('\n'):
        m = re.match(r'\s+"(\w+)":\s*\{', line)
        if m:
            keys.append(m.group(1))
    return set(keys)


def validate_schemas(schemas_dir: Path, shared_keys: set) -> list:
    """Validate all schemas have valid x_idPattern references."""
    errors = []
    schema_files = sorted(schemas_dir.glob("*.schema.json"))
    
    for schema_path in schema_files:
        schema_name = schema_path.stem
        with open(schema_path) as f:
            schema = json.load(f)
        
        props = schema.get("properties", {})
        for field_name, field_def in props.items():
            if field_def.get("type") != "array":
                continue
            
            items = field_def.get("items", {})
            item_props = items.get("properties", {})
            
            if "id" not in item_props:
                continue
            
            x_id_pattern = item_props["id"].get("x_idPattern")
            if not x_id_pattern:
                continue
            
            if x_id_pattern not in shared_keys:
                errors.append(
                    f"{schema_name}: field '{field_name}' has "
                    f"x_idPattern='{x_id_pattern}' which is not in shared.ID_PATTERNS"
                )
    
    return errors


def main():
    linters_dir = Path(__file__).resolve().parent
    schemas_dir = linters_dir.parent.parent / "skills" / "blueprint" / "schemas"
    
    shared_keys = load_shared_patterns(linters_dir)
    errors = validate_schemas(schemas_dir, shared_keys)
    
    if errors:
        print("ERRORS found:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print(f"✓ All schema x_idPattern references are valid ({len(shared_keys)} patterns)")


if __name__ == "__main__":
    main()
