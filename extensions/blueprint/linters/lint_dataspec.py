#!/usr/bin/env python3
"""
lint_dataspec.py — Validate a DataSpec JSON against its schema and semantic rules.

What this catches that JSON Schema alone cannot:
  - Duplicate entity names
  - Entity names not following PascalCase
  - Field names not following camelCase
  - Method names not following camelCase
  - Entity 'extends' referencing non-existent parent
  - Relationship 'from'/'to' referencing non-existent entities
  - Enum names not following SCREAMING_SNAKE_CASE
  - Enum values not following SCREAMING_SNAKE_CASE
  - Self-referencing relationships (from == to)
  - Field types referencing undefined primitives/entities/enums
  - Methods referencing apiRef that doesn't match FN-<camelCase> pattern
  - Relationship cardinality labels not matching expected patterns

Usage:
    python lint_dataspec.py <dataspec.json> [--schema dataspec.schema.json] [--strict] [--json]
"""

import json
import re
from pathlib import Path
from typing import Optional, Set
from shared import BaseLinter, LayerResult, validate_spec_ids, validate_project_and_version


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check_duplicate_fields(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check for duplicate field names within entities."""
    for entity in spec.get("entities", []):
        field_names = [f["name"] for f in entity.get("fields", [])]
        duplicates = [name for name in field_names if field_names.count(name) > 1]
        if duplicates:
            result.add("error", "duplicate_field",
                f"Entity '{entity['name']}' has duplicate fields: {duplicates}",
                hint="Remove duplicate field definitions.")


def _check_enum_entity_conflict(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that no entity name collides with an enum name."""
    entity_names = {e["name"] for e in spec.get("entities", [])}
    enum_names = {e["name"] for e in spec.get("enums", [])}
    collision = entity_names & enum_names
    for name in sorted(collision):
        result.add("error", "enum_entity_conflict",
            f"Name '{name}' is defined as both an enum and an entity.",
            hint=f"Remove the entity '{name}' and use the enum instead, or rename the entity.")


def _check_relationship_label_keywords(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Warn if relationship labels contain keywords suggesting a different type."""
    for rel in spec.get("relationships", []):
        label = (rel.get("label", "") or "").lower()
        rel_type = rel.get("type", "")
        from_entity = rel.get("from", "")
        to_entity = rel.get("to", "")

        if not label:
            continue

        strong_keywords = {
            "association": ["is associated with", "maintains a reference to", "holds a reference to", "references"],
            "aggregation": ["maintains a list of", "maintains a set of", "maintains a collection of", "is an element of"],
            "composition": ["is responsible for creation and destruction", "is the aggregate root of", "is the container of", "is a part of", "creates and owns"],
            "dependency": ["receives as parameter", "receives as argument", "uses as local variable", "references as parameter", "references as argument", "references as a local variable", "instantiates locally", "throws", "catches"],
        }

        medium_keywords = {
            "association": ["delegates to", "notifies", "subscribes to", "publishes to", "queries", "retrieves from"],
            "aggregation": ["has", "contains", "consists of", "belongs to", "includes", "comprises", "groups", "collects"],
            "composition": ["owns", "is composed of", "manages", "controls", "is responsible for", "instantiates", "destroys", "is the parent of", "creates"],
            "dependency": ["calls", "invokes", "uses", "imports", "depends on", "uses temporarily", "uses as a local variable"],
        }

        strong_matched = {}
        medium_matched = {}

        for rt, keywords in strong_keywords.items():
            matched = [kw for kw in keywords if kw in label]
            if matched:
                strong_matched[rt] = matched

        for rt, keywords in medium_keywords.items():
            matched = [kw for kw in keywords if kw in label]
            if matched:
                medium_matched[rt] = matched

        if not strong_matched and not medium_matched:
            result.add("warning", "rel_label_no_keyword_match",
                f"Relationship '{from_entity}' → '{to_entity}': label '{rel.get('label', '')}' "
                f"does not match any known keyword patterns.",
                hint="Consider using a more standard label that clearly indicates the relationship type. "
                     f"Current type: '{rel_type}'.")
            continue

        strong_non_declared = {t: kws for t, kws in strong_matched.items() if t != rel_type}
        if strong_non_declared:
            suggested = ", ".join(sorted(strong_non_declared.keys()))
            matched_kw = []
            for t, kws in strong_non_declared.items():
                matched_kw.extend([f"'{kw}'" for kw in kws])
            result.add("warning", "rel_label_keyword_mismatch",
                f"Relationship '{from_entity}' → '{to_entity}': label '{rel.get('label', '')}' "
                f"contains strong keywords for {suggested} (matched: {', '.join(matched_kw)}).",
                hint=f"Consider changing the relationship type to '{suggested}' "
                     f"or revising the label to better match '{rel_type}'.")
            continue

        non_declared = {t for t in medium_matched if t != rel_type}
        if len(non_declared) == 1:
            other_type = non_declared.pop()
            matched_kw = [f"'{kw}'" for kw in medium_matched[other_type]]
            result.add("warning", "rel_label_keyword_mismatch",
                f"Relationship '{from_entity}' → '{to_entity}': label '{rel.get('label', '')}' "
                f"contains keywords ({', '.join(matched_kw)}) that suggest '{other_type}' "
                f"rather than '{rel_type}'.",
                hint="Review whether the relationship type or label should be adjusted.")


def _check_abstract_entity_relationships(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Warn when abstract entities have composition/aggregation relationships as targets."""
    entity_map = {e["name"]: e for e in spec.get("entities", [])}
    for rel in spec.get("relationships", []):
        to_entity = rel.get("to", "")
        rel_type = rel.get("type", "")
        if to_entity in entity_map:
            entity = entity_map[to_entity]
            if entity.get("abstract", False) and rel_type in ("composition", "aggregation"):
                result.add("error", "abstract_entity_composition",
                    f"Abstract entity '{to_entity}' cannot be the target of {rel_type} relationship from '{rel.get('from', '')}'.",
                    hint="Abstract entities are base classes and should not be 'owned'. Use 'association' instead.")


def _check_duplicate_relationships(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Warn when the same entity pair has multiple relationships of the same type."""
    seen = {}
    for rel in spec.get("relationships", []):
        key = (rel["from"], rel["to"], rel.get("type", "association"))
        if key in seen:
            result.add("warning", "duplicate_relationship",
                f"Duplicate relationship: {rel['from']} → {rel['to']} "
                f"(type: {rel.get('type', 'association')}). "
                f"First declared at line {seen[key]}.",
                hint="Consider merging into a single relationship or using different types.")
        else:
            seen[key] = rel.get("line", 0)


def _check_missing_descriptions(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Warn about entities and fields without descriptions."""
    for entity in spec.get("entities", []):
        if not entity.get("description"):
            result.add("info", "missing_entity_description",
                f"Entity '{entity['name']}' has no description.",
                hint="Add a description to explain what this entity represents in the domain.")
        for field in entity.get("fields", []):
            if not field.get("description"):
                result.add("info", "missing_field_description",
                    f"Entity '{entity['name']}': field '{field['name']}' has no description.",
                    hint="Add a description to explain the purpose of this field.")


def _check_pk_naming(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Warn if any entity's primary key field doesn't contain 'id' in its name."""
    for entity in spec.get("entities", []):
        fields = entity.get("fields", [])
        if not fields:
            continue
        pk_field = None
        for f in fields:
            if f.get("primaryKey", False):
                pk_field = f
                break
        if not pk_field:
            for f in fields:
                if f["name"].lower() == "id":
                    pk_field = f
                    break
        if not pk_field:
            for f in fields:
                name = f["name"]
                if name.endswith("Id") or name.endswith("id"):
                    pk_field = f
                    break
        if not pk_field:
            pk_field = fields[0]
        if pk_field and "id" not in pk_field["name"].lower():
            result.add("warning", "pk_naming",
                f"Entity '{entity['name']}': primary key field '{pk_field['name']}' "
                f"doesn't contain 'id' in its name.",
                hint=f"Consider renaming to '{pk_field['name']}Id' or 'entityId' "
                     "for consistency with diagram generators and DBML output.")


def _check_primitives(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate that primitives list is non-empty and contains valid names."""
    raw_primitives = spec.get("primitives", [])
    # Handle both string list and dict list for primitives
    primitives = {p if isinstance(p, str) else p.get("id", "") for p in raw_primitives}
    expected_primitives = {'string', 'number', 'boolean', 'null', 'void'}
    missing = expected_primitives - primitives
    if missing:
        result.add("error", "primitives_missing",
            f"DataSpec missing expected primitives: {sorted(missing)}",
            hint="Add missing primitives to the primitives list.")
    if "any" in primitives:
        result.add("warning", "primitives_any",
            "'any' is in the primitives list — this disables type checking.",
            hint="Consider removing 'any' to enforce stricter type discipline.")


def _check_entity_visibility(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Validate entity visibility values."""
    for entity in spec.get("entities", []):
        vis = entity.get("visibility", "public")
        if vis not in ("public", "internal"):
            result.add("error", "entity_visibility_invalid",
                f"Entity '{entity['name']}': visibility '{vis}' is not valid.",
                hint="Entity visibility must be 'public' or 'internal'.")


# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES = [
    # Entity names must be PascalCase
    {
        "type": "contains_patterns",
        "target": "entities.name",
        "patterns": [r"^[A-Z][A-Za-z0-9]*$"],
        "negate": True,
        "target_label": "Entity",
        "category": "entity_name_format",
        "hint": "Entity names must start with an uppercase letter followed by alphanumeric characters.",
    },
    # Field names must be camelCase
    {
        "type": "contains_patterns",
        "target": "entities.fields.name",
        "patterns": [r"^[a-z][A-Za-z0-9]*$"],
        "negate": True,
        "target_label": "Field",
        "category": "field_name_format",
        "hint": "Field names must start with a lowercase letter.",
    },
    # Method names must be camelCase
    {
        "type": "contains_patterns",
        "target": "entities.methods.name",
        "patterns": [r"^[a-z][A-Za-z0-9]*$"],
        "negate": True,
        "target_label": "Method",
        "category": "method_name_format",
        "hint": "Method names must start with a lowercase letter.",
    },
    # Enum names must be PascalCase
    {
        "type": "contains_patterns",
        "target": "enums.name",
        "patterns": [r"^[A-Z][A-Za-z0-9]*$"],
        "negate": True,
        "target_label": "Enum",
        "category": "enum_name_format",
        "hint": "Enum names must start with an uppercase letter followed by alphanumeric characters.",
    },
    # Enum values must be SCREAMING_SNAKE_CASE
    {
        "type": "contains_patterns",
        "target": "enums.values.name",
        "patterns": [r"^[A-Z][A-Z0-9_]*$"],
        "negate": True,
        "target_label": "Enum value",
        "category": "enum_value_format",
        "hint": "Enum values must be uppercase with underscores.",
    },
    # Entity extends must reference existing entity
    {
        "type": "exists",
        "target": "entities.extends",
        "inside": "entities.name",
        "target_label": "Entity",
        "ref_label": "Entity",
        "category": "extends_missing",
        "hint": "Add the parent entity or remove the 'extends' field.",
    },
    # Relationship from must reference existing entity
    {
        "type": "exists",
        "target": "relationships.from",
        "inside": "entities.name",
        "target_label": "Relationship",
        "ref_label": "Entity",
        "category": "rel_from_missing",
        "hint": "Add the source entity.",
    },
    # Relationship to must reference existing entity
    {
        "type": "exists",
        "target": "relationships.to",
        "inside": "entities.name",
        "target_label": "Relationship",
        "ref_label": "Entity",
        "category": "rel_to_missing",
        "hint": "Add the target entity.",
    },
    # Relationship type must be valid
    {
        "type": "non_empty",
        "target": "relationships.type",
        "target_label": "Relationship",
        "category": "rel_type_invalid",
        "hint": "Valid types: association, composition, aggregation, dependency, realization.",
    },
]


# ── Misc Checks ───────────────────────────────────────────────────────────────

MISC_CHECKS = [
    ("primitives", _check_primitives),
    ("pk_naming", _check_pk_naming),
    ("duplicate_fields", _check_duplicate_fields),
    ("enum_entity_conflict", _check_enum_entity_conflict),
    ("entity_visibility", _check_entity_visibility),
    ("abstract_relationships", _check_abstract_entity_relationships),
    ("duplicate_relationships", _check_duplicate_relationships),
    ("missing_descriptions", _check_missing_descriptions),
    ("relationship_label", _check_relationship_label_keywords),
]


# ── Cross-spec dependency ─────────────────────────────────────────────────────

CROSS_SPEC_DEPS = []


# ── Linter Class ──────────────────────────────────────────────────────────────

class DataSpecLinter(BaseLinter):
    """Linter for DataSpec artifacts."""
    
    SPEC_NAME = "dataspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    MISC_CHECKS = MISC_CHECKS
    CROSS_SPEC_DEPS = CROSS_SPEC_DEPS
    
    def __init__(self, spec, schema_path, strict):
        super().__init__(spec, schema_path, strict)
        # Pre-compute entity and enum names for cross-reference rules
        self._entity_names = {e["name"] for e in self.spec.get("entities", [])}
        self._enum_names = {e["name"] for e in self.spec.get("enums", [])}
    
    def _run_misc_checks(self) -> None:
        """Run misc checks with entity/enum names available."""
        for name, func in self.MISC_CHECKS:
            func(self.spec, self.result, self.extra_specs)
    
    def _validate_cross_spec_consistency(self) -> None:
        """Check project match, version pinning, field types, and relationship types."""
        super()._validate_cross_spec_consistency()
        # Also validate field types reference valid types
        _check_field_types(self.spec, self._entity_names, self._enum_names, self.result)
        # Validate relationship types
        _check_relationship_types(self.spec, self._entity_names, self._enum_names, self.result)


# ── Cross-spec type validation helpers ────────────────────────────────────────

def _check_field_types(spec: dict, entity_names: Set[str], enum_names: Set[str], result: LayerResult) -> None:
    """Validate that field types reference valid primitives/entities/enums."""
    raw_primitives = spec.get("primitives", ["string", "number", "boolean", "null"])
    primitives = {p if isinstance(p, str) else p.get("id", "") for p in raw_primitives}
    valid_types = entity_names | enum_names | primitives
    
    for entity in spec.get("entities", []):
        for field_def in entity.get("fields", []):
            ftype = field_def.get("type", "")
            base_type = ftype.replace("[]", "") if ftype.endswith("[]") else ftype
            if base_type and base_type not in valid_types:
                result.add("error", "type_undefined",
                    f"Entity '{entity['name']}': field '{field_def['name']}' has type '{ftype}', which is not defined.",
                    hint=f"Define '{base_type}' as a primitive, entity, or enum. Available: {sorted(primitives | entity_names | enum_names)}")


def _check_relationship_types(spec: dict, entity_names: Set[str], enum_names: Set[str], result: LayerResult) -> None:
    """Validate relationship endpoints and types."""
    valid_types = {"association", "composition", "aggregation", "dependency", "realization"}
    
    for rel in spec.get("relationships", []):
        from_entity = rel.get("from", "")
        to_entity = rel.get("to", "")
        rel_type = rel.get("type", "")
        
        # Check from/to are valid entities (not enums)
        if to_entity in enum_names:
            result.add("error", "rel_to_enum",
                f"Relationship targets enum '{to_entity}' which cannot be a relationship target.",
                hint="Enums are type references, not entities. Remove this relationship — the type is already referenced via a field definition.")
        
        # Check relationship type is valid
        if rel_type and rel_type not in valid_types:
            result.add("error", "rel_type_invalid",
                f"Relationship between '{from_entity}' and '{to_entity}': type '{rel_type}' is not valid.",
                hint=f"Valid types: {', '.join(sorted(valid_types))}")
        
        # Warn about self-referencing relationships
        if from_entity == to_entity and from_entity in entity_names:
            result.add("warning", "rel_self_reference",
                f"Self-referencing relationship: '{from_entity}' → '{to_entity}'.",
                hint="Self-referencing relationships are valid (e.g., tree structures) but often indicate a design choice that should be reviewed.")


# ── Backward-compatible entry point ───────────────────────────────────────────

def run_lint(spec, schema_path, strict, api_spec=None, glossary=None):
    """Backward-compatible entry point for lint_all.py."""
    linter = DataSpecLinter(spec, schema_path, strict)
    return linter.run(api=api_spec, glossary=glossary)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    DataSpecLinter.main([])
