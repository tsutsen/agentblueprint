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
import sys
import argparse
import re
from pathlib import Path
from typing import Optional, Set
from shared import Issue, LayerResult, print_human, print_json_output, validate_id_format
from schema_validator import SchemaValidator


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_ids(items: list, key: str) -> list[str]:
    return [item[key] for item in items if key in item]

def check_duplicates(ids: list[str], label: str, result: LayerResult):
    seen = set()
    for id_ in ids:
        if id_ in seen:
            result.add("error", "duplicate_id",
                f"Duplicate {label} name '{id_}'.",
                hint=f"Each {label} must have a unique name.")
        seen.add(id_)


# ── Semantic checks ───────────────────────────────────────────────────────────

def check_entities(spec: dict, enums: list, result: LayerResult) -> Set[str]:
    """Validate entity names, fields, methods, and extends references."""
    entities = spec.get("entities", [])
    entity_names: Set[str] = set()
    entity_map: dict = {}

    # Validate ENT-NNN-PascalCase format
    check_id_format(entities, "id", "ent", "entity_id_format", result)

    for entity in entities:
        eid = entity.get("id", "")
        if not eid:
            result.add("error", "entity_missing_id",
                f"Entity '{entity.get('name', '<unknown>')}'' is missing an 'id' field.",
                hint="Add an ID in the format 'ENT-NNN-entityName', e.g. 'ENT-001-ResearchSession'.")

        name = entity["name"]
        entity_names.add(name)
        entity_map[name] = entity

        # Entity name must be PascalCase
        if not re.match(r"^[A-Z][A-Za-z0-9]*$", name):
            result.add("error", "entity_name_format",
                f"Entity '{name}' does not follow PascalCase.",
                hint="Entity names must start with an uppercase letter followed by alphanumeric characters.")

    # Check extends references
    for entity in entities:
        extends = entity.get("extends")
        if extends and extends not in entity_names:
            result.add("error", "extends_missing",
                f"Entity '{entity['name']}' extends '{extends}', which does not exist.",
                hint=f"Add '{extends}' as an entity or remove the 'extends' field.")

    # Validate fields
    for entity in entities:
        for field_def in entity.get("fields", []):
            fname = field_def["name"]

            # Field name must be camelCase
            if not re.match(r"^[a-z][A-Za-z0-9]*$", fname):
                result.add("error", "field_name_format",
                    f"Entity '{entity['name']}': field '{fname}' does not follow camelCase.",
                    hint="Field names must start with a lowercase letter.")

            # Field type must resolve
            ftype = field_def.get("type", "")
            base_type = ftype.replace("[]", "") if ftype.endswith("[]") else ftype
            primitives = set(spec.get("primitives", ["string", "number", "boolean", "null"]))
            enum_names = {e["name"] for e in enums}

            if base_type not in entity_names and base_type not in primitives and base_type not in enum_names:
                result.add("error", "type_undefined",
                    f"Entity '{entity['name']}': field '{fname}' has type '{ftype}', which is not defined.",
                    hint=f"Define '{base_type}' as a primitive, entity, or enum. Available: {sorted(primitives | entity_names | enum_names)}")

    # Validate methods
    for entity in entities:
        for method in entity.get("methods", []):
            mname = method.get("name", "")
            if mname and not re.match(r"^[a-z][A-Za-z0-9]*$", mname):
                result.add("error", "method_name_format",
                    f"Entity '{entity['name']}': method '{mname}' does not follow camelCase.",
                    hint="Method names must start with a lowercase letter.")

            api_ref = method.get("apiRef", "")
            if api_ref and not validate_id_format(api_ref, "fn")[0]:
                result.add("error", "method_api_ref_format",
                    f"Entity '{entity['name']}': method '{mname}' has apiRef '{api_ref}' which doesn't match FN-NNN-lowerCamelCase.",
                    hint="apiRef must reference a function ID in the API spec, e.g. 'FN-001-authenticate'.")

    # Validate visibility
    for entity in entities:
        vis = entity.get("visibility", "public")
        if vis not in ("public", "internal"):
            result.add("error", "entity_visibility_invalid",
                f"Entity '{entity['name']}': visibility '{vis}' is not valid.",
                hint="Entity visibility must be 'public' or 'internal'.")

    return entity_names


def check_enums(spec: dict, result: LayerResult) -> Set[str]:
    """Validate enum names and values."""
    enums = spec.get("enums", [])
    enum_names: Set[str] = set()

    # Validate NUM-NNN-PascalCase format
    check_id_format(enums, "id", "num", "enum_id_format", result)

    for enum in enums:
        eid = enum.get("id", "")
        if not eid:
            result.add("error", "enum_missing_id",
                f"Enum '{enum.get('name', '<unknown>')}'' is missing an 'id' field.",
                hint="Add an ID in the format 'NUM-NNN-enumName', e.g. 'NUM-001-EvidenceType'.")

        ename = enum["name"]
        enum_names.add(ename)

        # Enum name must be PascalCase (per DataSpec schema)
        if not re.match(r"^[A-Z][A-Za-z0-9]*$", ename):
            result.add("error", "enum_name_format",
                f"Enum '{ename}' does not follow PascalCase.",
                hint="Enum names must start with an uppercase letter followed by alphanumeric characters, e.g. 'OrderStatus'.")

        for val in enum.get("values", []):
            vname = val["name"]
            if not re.match(r"^[A-Z][A-Z0-9_]*$", vname):
                result.add("error", "enum_value_format",
                    f"Enum '{ename}': value '{vname}' does not follow SCREAMING_SNAKE_CASE.",
                    hint="Enum values must be uppercase with underscores, e.g. 'PENDING'.")

    return enum_names


def check_abstract_entity_relationships(spec: dict, result: LayerResult):
    """Warn when abstract entities have composition/aggregation relationships as targets.

    Abstract entities are base classes and should not be 'owned' by other entities.
    """
    entity_map = {e["name"]: e for e in spec.get("entities", [])}
    relationships = spec.get("relationships", [])

    for rel in relationships:
        to_entity = rel.get("to", "")
        rel_type = rel.get("type", "")

        # Check if target is abstract and relationship is composition/aggregation
        if to_entity in entity_map:
            entity = entity_map[to_entity]
            if entity.get("abstract", False) and rel_type in ("composition", "aggregation"):
                result.add("error", "abstract_entity_composition",
                    f"Abstract entity '{to_entity}' cannot be the target of {rel_type} relationship from '{rel.get('from', '')}'.",
                    hint="Abstract entities are base classes and should not be 'owned'. Use 'association' instead.")


def check_relationships(spec: dict, entity_names: Set[str], result: LayerResult):
    """Validate relationship endpoints and types."""
    relationships = spec.get("relationships", [])
    enum_names = {e["name"] for e in spec.get("enums", [])}

    for rel in relationships:
        from_entity = rel.get("from", "")
        to_entity = rel.get("to", "")

        # from/to must reference valid entities
        if from_entity not in entity_names:
            result.add("error", "rel_from_missing",
                f"Relationship from '{from_entity}' does not exist.",
                hint=f"Add '{from_entity}' as an entity.")

        if to_entity not in entity_names:
            if to_entity in enum_names:
                result.add("error", "rel_to_enum",
                    f"Relationship targets enum '{to_entity}' which cannot be a relationship target.",
                    hint="Enums are type references, not entities. Remove this relationship — the type is already referenced via a field definition.")
            else:
                result.add("error", "rel_to_missing",
                    f"Relationship to '{to_entity}' does not exist.",
                    hint=f"Add '{to_entity}' as an entity.")

        # Relationship type must be valid
        rel_type = rel.get("type", "")
        valid_types = {"association", "composition", "aggregation", "dependency", "realization"}
        if rel_type not in valid_types:
            result.add("error", "rel_type_invalid",
                f"Relationship between '{from_entity}' and '{to_entity}': type '{rel_type}' is not valid.",
                hint=f"Valid types: {', '.join(sorted(valid_types))}")

        # Warn about self-referencing relationships
        if from_entity == to_entity and from_entity in entity_names:
            result.add("warning", "rel_self_reference",
                f"Self-referencing relationship: '{from_entity}' → '{to_entity}'.",
                hint="Self-referencing relationships are valid (e.g., tree structures) but often indicate a design choice that should be reviewed.")

        # Check label keywords against declared type
        check_relationship_label_keywords(rel, result)


def check_relationship_label_keywords(rel: dict, result: LayerResult):
    """Warn if the relationship label contains keywords suggesting a different type.

    The label (natural-language description) should match the declared type.
    This catches mismatches like:
      - type=aggregation but label contains 'owns' or 'is the lifecycle owner of'
      - type=dependency but label contains 'maintains a reference to' or 'holds a reference to'

    Keywords are weighted:
      - strong: unique to one type → direct suggestion to change type
      - medium: shared by two types → softer hint about reviewing
    """
    label = (rel.get("label", "") or "").lower()
    rel_type = rel.get("type", "")
    from_entity = rel.get("from", "")
    to_entity = rel.get("to", "")

    if not label:
        return

    # Strong keywords: unique to one relationship type
    strong_keywords = {
        "association": [
            "is associated with", "maintains a reference to",
            "holds a reference to", "references",
        ],
        "aggregation": [
            "maintains a list of", "maintains a set of", "maintains a collection of",
            "is an element of",
        ],
        "composition": [
            "is responsible for creation and destruction", "is the aggregate root of",
            "is the container of", "is a part of", "creates and owns",
        ],
        "dependency": [
            "receives as parameter", "receives as argument",
            "uses as local variable", "references as parameter",
            "references as argument", "references as a local variable",
            "instantiates locally", "throws", "catches",
        ],
    }

    # Medium keywords: shared by two types (weaker signal)
    medium_keywords = {
        "association": ["delegates to", "notifies", "subscribes to", "publishes to", "queries", "retrieves from"],
        "aggregation": ["has", "contains", "consists of", "belongs to", "includes", "comprises", "groups", "collects"],
        "composition": ["owns", "is composed of", "manages", "controls", "is responsible for", "instantiates", "destroys", "is the parent of", "creates"],
        "dependency": ["calls", "invokes", "uses", "imports", "depends on", "uses temporarily", "uses as a local variable"],
    }

    # Separate strong and medium matches per type
    strong_matched: dict[str, list[str]] = {}
    medium_matched: dict[str, list[str]] = {}

    for rel_type_str, keywords in strong_keywords.items():
        matched = [kw for kw in keywords if kw in label]
        if matched:
            strong_matched[rel_type_str] = matched

    for rel_type_str, keywords in medium_keywords.items():
        matched = [kw for kw in keywords if kw in label]
        if matched:
            medium_matched[rel_type_str] = matched

    if not strong_matched and not medium_matched:
        # Label doesn't match any known keyword patterns — warn that
        # the label may be unclear or non-standard
        result.add("warning", "rel_label_no_keyword_match",
            f"Relationship '{from_entity}' → '{to_entity}': label '{rel.get('label', '')}' "
            f"does not match any known keyword patterns.",
            hint="Consider using a more standard label that clearly indicates the relationship type. "
                 f"Current type: '{rel_type}'.")
        return

    # Check if strong keywords from a different type are present
    strong_non_declared = {
        t: kws for t, kws in strong_matched.items()
        if t != rel_type
    }

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
        return

    # No strong mismatch — check for medium mismatches from a single other type
    non_declared = {t for t in medium_matched if t != rel_type}
    if len(non_declared) == 1:
        other_type = non_declared.pop()
        matched_kw = [f"'{kw}'" for kw in medium_matched[other_type]]
        result.add("warning", "rel_label_keyword_mismatch",
            f"Relationship '{from_entity}' → '{to_entity}': label '{rel.get('label', '')}' "
            f"contains keywords ({', '.join(matched_kw)}) that suggest '{other_type}' "
            f"rather than '{rel_type}'.",
            hint="Review whether the relationship type or label should be adjusted.")


def check_enum_entity_conflict(spec: dict, result: LayerResult):
    """Check that no entity name collides with an enum name."""
    entity_names = {e["name"] for e in spec.get("entities", [])}
    enum_names = {e["name"] for e in spec.get("enums", [])}
    collision = entity_names & enum_names
    for name in sorted(collision):
        result.add("error", "enum_entity_conflict",
            f"Name '{name}' is defined as both an enum and an entity.",
            hint=f"Remove the entity '{name}' and use the enum instead, or rename the entity.")


def check_field_type_kinds(spec: dict, entity_names: Set[str], enum_names: Set[str], result: LayerResult):
    """Warn when a field type could be ambiguous (exists as entity but should be enum or vice versa)."""
    for entity in spec.get("entities", []):
        for field_def in entity.get("fields", []):
            ftype = field_def.get("type", "")
            base = ftype.replace("[]", "")
            if not base:
                continue
            is_entity = base in entity_names
            is_enum = base in enum_names
            if is_entity and is_enum:
                result.add("warning", "type_ambiguous_kind",
                    f"Entity '{entity['name']}': field '{field_def['name']}' has type '{ftype}' "
                    f"which exists as both an entity and an enum.",
                    hint=f"Clarify whether '{base}' should be used as a type reference (enum) or a relationship target (entity).")


def check_duplicate_fields(spec: dict, result: LayerResult):
    """Check for duplicate field names within entities."""
    for entity in spec.get("entities", []):
        field_names = [f["name"] for f in entity.get("fields", [])]
        duplicates = [name for name in field_names if field_names.count(name) > 1]
        if duplicates:
            result.add("error", "duplicate_field",
                f"Entity '{entity['name']}' has duplicate fields: {duplicates}",
                hint="Remove duplicate field definitions.")


def check_entity_should_be_field(spec: dict, api_spec: Optional[dict], result: LayerResult):
    """Heuristic: entity with ≤3 fields, all primitives, ≤1 relationship, ≤1 referrer → should be a field."""
    entities = spec.get("entities", [])
    relationships = spec.get("relationships", [])
    primitives = {"string", "number", "boolean", "null"}

    # Build referrer map: entity_name → set of entities that reference it as a field type
    referrers: dict[str, set[str]] = {e["name"]: set() for e in entities}
    for entity in entities:
        for field_def in entity.get("fields", []):
            base = field_def.get("type", "").replace("[]", "")
            if base in referrers:
                referrers[base].add(entity["name"])

    # Count relationships per entity
    rel_counts: dict[str, int] = {e["name"]: 0 for e in entities}
    for rel in relationships:
        from_e = rel.get("from", "")
        to_e = rel.get("to", "")
        if from_e in rel_counts:
            rel_counts[from_e] += 1
        if to_e in rel_counts:
            rel_counts[to_e] += 1

    # Count API functions referencing each entity
    api_counts: dict[str, int] = {e["name"]: 0 for e in entities}
    if api_spec:
        for fn in api_spec.get("functions", []):
            for p in fn.get("inputs", []):
                ptype = p.get("type", "").replace("[]", "")
                if ptype in api_counts:
                    api_counts[ptype] += 1
            out = fn.get("output", {})
            if isinstance(out, dict):
                out_type = out.get("type", "").replace("[]", "")
                if out_type in api_counts:
                    api_counts[out_type] += 1

    for entity in entities:
        name = entity["name"]
        fields = entity.get("fields", [])

        if len(fields) <= 3 and all(
            f.get("type", "").replace("[]", "") in primitives or f.get("type", "").endswith("[]")
            for f in fields
        ) and rel_counts.get(name, 0) <= 1 and len(referrers.get(name, set())) <= 1:
            parent = next(iter(referrers.get(name, set()))) if referrers.get(name) else "unknown"
            result.add("info", "entity_should_be_field",
                f"Entity '{name}' has only {len(fields)} field(s) and {rel_counts.get(name, 0)} relationship(s).",
                hint=f"Consider whether this entity should be a field of '{parent}' instead.")


def check_field_should_be_entity(spec: dict, api_spec: Optional[dict], result: LayerResult):
    """Heuristic: field of complex type with >5 fields, has identity, ≥2 referrers, ≥1 relationship, ≥2 API functions → should be an entity."""
    entities = spec.get("entities", [])
    relationships = spec.get("relationships", [])
    entity_map = {e["name"]: e for e in entities}

    # Build referrer map: entity_name → set of entities that reference it as a field type
    referrers: dict[str, set[str]] = {e["name"]: set() for e in entities}
    for entity in entities:
        for field_def in entity.get("fields", []):
            base = field_def.get("type", "").replace("[]", "")
            if base in referrers:
                referrers[base].add(entity["name"])

    # Count relationships per entity
    rel_counts: dict[str, int] = {e["name"]: 0 for e in entities}
    for rel in relationships:
        from_e = rel.get("from", "")
        to_e = rel.get("to", "")
        if from_e in rel_counts:
            rel_counts[from_e] += 1
        if to_e in rel_counts:
            rel_counts[to_e] += 1

    # Count API functions referencing each entity
    api_counts: dict[str, int] = {e["name"]: 0 for e in entities}
    if api_spec:
        for fn in api_spec.get("functions", []):
            for p in fn.get("inputs", []):
                ptype = p.get("type", "").replace("[]", "")
                if ptype in api_counts:
                    api_counts[ptype] += 1
            out = fn.get("output", {})
            if isinstance(out, dict):
                out_type = out.get("type", "").replace("[]", "")
                if out_type in api_counts:
                    api_counts[out_type] += 1

    for entity in entities:
        for field_def in entity.get("fields", []):
            ftype = field_def.get("type", "").replace("[]", "")
            if ftype in ("string", "number", "boolean", "null"):
                continue
            target = entity_map.get(ftype)
            if not target:
                continue

            score = 0
            if len(target.get("fields", [])) > 5:
                score += 1
            if any("id" in f.get("name", "").lower() for f in target.get("fields", [])):
                score += 1
            if len(referrers.get(ftype, set())) >= 2:
                score += 1
            if rel_counts.get(ftype, 0) >= 1:
                score += 1
            if api_counts.get(ftype, 0) >= 2:
                score += 1

            if score >= 4:
                result.add("warning", "field_should_be_entity",
                    f"Field '{entity['name']}.{field_def['name']}' of type '{ftype}' "
                    f"looks like it should be a separate entity.",
                    hint=f"{len(target.get('fields', []))} fields, {len(referrers.get(ftype, set()))} referrer(s), "
                         f"{rel_counts.get(ftype, 0)} relationship(s), {api_counts.get(ftype, 0)} API function(s).")


def check_methods_coverage(spec: dict, api_spec: Optional[dict], result: LayerResult):
    """Warn if entity has ≥2 ApiSpec functions but 0 methods defined."""
    if not api_spec:
        return

    # Count API functions per entity
    api_counts: dict[str, int] = {}
    for fn in api_spec.get("functions", []):
        entity = fn.get("entity", "")
        if entity:
            api_counts[entity] = api_counts.get(entity, 0) + 1

    for entity in spec.get("entities", []):
        name = entity["name"]
        api_count = api_counts.get(name, 0)
        methods = entity.get("methods", [])
        if api_count >= 3 and len(methods) == 0:
            result.add("warning", "methods_missing",
                f"Entity '{name}' has {api_count} ApiSpec function(s) but 0 methods defined.",
                hint=f"Define entity methods to document how the API functions interact with this entity.")


def _name_similarity(a: str, b: str) -> float:
    """Compute name similarity ratio between 0 and 1 using difflib."""
    if not a or not b:
        return 0.0
    return __import__('difflib').SequenceMatcher(None, a.lower(), b.lower()).ratio()


def check_entity_similarity(spec: dict, result: LayerResult):
    """Warn if two entities have similar names and high field overlap."""
    entities = spec.get("entities", [])
    for i, a in enumerate(entities):
        for b in entities[i + 1:]:
            a_name = a["name"]
            b_name = b["name"]

            # Skip if both are valid PascalCase
            if not (re.match(r"^[A-Z][A-Za-z0-9]*$", a_name) and
                    re.match(r"^[A-Z][A-Za-z0-9]*$", b_name)):
                continue

            # 1. Name similarity (Levenshtein ratio ≥ 0.6)
            name_sim = _name_similarity(a_name, b_name)
            if name_sim < 0.6:
                continue

            # 2. Field overlap (Jaccard similarity ≥ 0.6)
            fields_a = {f["name"] for f in a.get("fields", [])}
            fields_b = {f["name"] for f in b.get("fields", [])}
            if not fields_a and not fields_b:
                continue
            overlap = fields_a & fields_b
            union = fields_a | fields_b
            jaccard = len(overlap) / len(union) if union else 0

            if jaccard >= 0.6:
                result.add("warning", "entity_similarity",
                    f"Entities '{a_name}' and '{b_name}' appear to be similar.",
                    hint=f"Name similarity: {name_sim:.0%}, Field overlap: {jaccard:.0%} "
                         f"({len(overlap)}/{len(union)} fields). Shared: {sorted(overlap)}. "
                         f"Consider merging or renaming.")


def check_similar_entities_connected(spec: dict, result: LayerResult):
    """Warn if similar-named entities exist but have no relationship between them."""
    entities = spec.get("entities", [])
    relationships = spec.get("relationships", [])

    # Build set of connected entity pairs
    connected = set()
    for rel in relationships:
        pair = tuple(sorted([rel.get("from", ""), rel.get("to", "")]))
        connected.add(pair)

    for i, a in enumerate(entities):
        for b in entities[i + 1:]:
            a_name = a["name"]
            b_name = b["name"]

            # Skip if both are valid PascalCase
            if not (re.match(r"^[A-Z][A-Za-z0-9]*$", a_name) and
                    re.match(r"^[A-Z][A-Za-z0-9]*$", b_name)):
                continue

            # Name similarity threshold
            name_sim = _name_similarity(a_name, b_name)
            if name_sim < 0.55:
                continue

            # Check if they are already connected
            pair = tuple(sorted([a_name, b_name]))
            if pair in connected:
                continue

            # Warn — similar names but no relationship
            result.add("warning", "similar_entities_disconnected",
                f"Similar entities '{a_name}' and '{b_name}' have no relationship.",
                hint=f"Name similarity: {name_sim:.0%}. "
                     f"Consider adding a relationship or clarifying their distinct roles.")


def check_bidirectional_relationships(spec: dict, result: LayerResult):
    """Warn when two entities have relationships in both directions.

    DBML only supports unidirectional relationships. If A → B and B → A
    both exist, the user should consolidate into a single relationship.
    """
    relationships = spec.get("relationships", [])

    # Build set of directed pairs
    directed_pairs = set()
    for rel in relationships:
        from_e = rel.get("from", "")
        to_e = rel.get("to", "")
        if from_e and to_e:
            directed_pairs.add((from_e, to_e))

    # Check for bidirectional pairs
    seen = set()
    for from_e, to_e in directed_pairs:
        if (to_e, from_e) in directed_pairs:
            pair = tuple(sorted([from_e, to_e]))
            if pair in seen:
                continue
            seen.add(pair)
            # Warn — bidirectional relationships are valid in domain modeling
            # but not supported by DBML export
            result.add("warning", "bidirectional_relationship",
                f"Bidirectional relationship between '{from_e}' and '{to_e}'.",
                hint="DBML only supports unidirectional relationships. "
                     f"Consolidate '{from_e}' → '{to_e}' and '{to_e}' → '{from_e}' "
                     f"into a single relationship in the direction that makes sense "
                     f"for your domain model.")


def check_entity_list_fields(spec: dict, result: LayerResult):
    """Warn when an entity has a field that is a list of another entity.

    Entity[] fields suggest embedding a collection of related entities
    rather than declaring a proper relationship. Relationships should be
    used instead.
    """
    entities = spec.get("entities", [])
    entity_names = {e["name"] for e in entities}

    for entity in entities:
        for field_def in entity.get("fields", []):
            ftype = field_def.get("type", "")
            if not ftype.endswith("[]"):
                continue
            base = ftype[:-2]  # Remove '[]'
            if base in entity_names:
                result.add("warning", "entity_list_field",
                    f"Entity '{entity['name']}' has field '{field_def['name']}' "
                    f"of type '{ftype}' (list of entity '{base}').",
                    hint=f"Consider replacing this field with a relationship "
                         f"from '{entity['name']}' to '{base}'. "
                         f"Entity lists in fields suggest embedding rather than "
                         f"relating — use relationships for entity-to-entity "
                         f"associations.")


def check_primitives(spec: dict, result: LayerResult):
    """Validate that primitives list is non-empty and contains valid names."""
    primitives = spec.get("primitives", [])
    expected_primitives = {'string', 'number', 'boolean', 'null', 'void'}
    missing = expected_primitives - set(primitives)
    if missing:
        result.add("error", "primitives_missing",
            f"DataSpec missing expected primitives: {sorted(missing)}",
            hint="Add missing primitives to the primitives list.")

    # Warn about 'any' in primitives — it's too permissive
    if "any" in primitives:
        result.add("warning", "primitives_any",
            "'any' is in the primitives list — this disables type checking.",
            hint="Consider removing 'any' to enforce stricter type discipline.")


def check_pk_naming(spec: dict, result: LayerResult):
    """Warn if any entity's primary key field doesn't contain 'id' in its name.

    Primary keys should be easily identifiable. Fields named 'id', 'entityId',
    'userId', etc. are preferred. This check uses the explicit primaryKey field
    if set, otherwise falls back to the _find_pk heuristic.
    """
    for entity in spec.get("entities", []):
        fields = entity.get("fields", [])
        if not fields:
            continue

        # Determine which field is the PK
        pk_field = None
        # Priority 1: explicit primaryKey field
        for f in fields:
            if f.get("primaryKey", False):
                pk_field = f
                break
        # Priority 2: field named 'id' (case-insensitive)
        if not pk_field:
            for f in fields:
                if f["name"].lower() == "id":
                    pk_field = f
                    break
        # Priority 3: field ending with 'Id' or 'id'
        if not pk_field:
            for f in fields:
                name = f["name"]
                if name.endswith("Id") or name.endswith("id"):
                    pk_field = f
                    break
        # Priority 4: first field
        if not pk_field:
            pk_field = fields[0]

        if pk_field and "id" not in pk_field["name"].lower():
            result.add("warning", "pk_naming",
                f"Entity '{entity['name']}': primary key field '{pk_field['name']}' "
                f"doesn't contain 'id' in its name.",
                hint=f"Consider renaming to '{pk_field['name']}Id' or 'entityId' "
                     "for consistency with diagram generators and DBML output.")




def check_duplicate_relationships(spec: dict, result: LayerResult):
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


def check_missing_descriptions(spec: dict, result: LayerResult):
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


def check_method_apiRef(spec: dict, api_spec: Optional[dict], result: LayerResult):
    """Verify apiRef references in entity methods exist in ApiSpec."""
    if not api_spec:
        return

    api_functions = {fn.get("id", "") for fn in api_spec.get("functions", [])}

    for entity in spec.get("entities", []):
        for method in entity.get("methods", []):
            api_ref = method.get("apiRef", "")
            if api_ref and api_ref not in api_functions:
                result.add("warning", "invalid_apiRef",
                    f"Entity '{entity['name']}': method '{method.get('name', '')}' "
                    f"references undefined apiRef '{api_ref}'.",
                    hint="Ensure the apiRef matches a function ID in ApiSpec.")


def match_glossary_term(name: str, glossary: dict) -> list[str]:
    """Match an entity/enum name against glossary terms.

    Strategy:
      1. Case-insensitive exact match
      2. Case-insensitive substring match (name in term or term in name)

    Returns list of matching GL-NNN IDs.
    """
    name_lower = name.lower()
    matches = []

    for term in glossary.get("terms", []):
        term_lower = term["name"].lower()
        # Exact match
        if name_lower == term_lower:
            return [term["id"]]  # Exact match is definitive
        # Substring match
        if name_lower in term_lower or term_lower in name_lower:
            matches.append(term["id"])

    return matches


def check_entity_glossary(spec: dict, glossary: Optional[dict], result: LayerResult):
    """ERROR: Every entity name must match a glossary term."""
    if not glossary:
        return

    for entity in spec.get("entities", []):
        ename = entity["name"]
        matches = match_glossary_term(ename, glossary)
        if not matches:
            result.add("error", "entity_not_in_glossary",
                f"Entity '{ename}' has no matching glossary term.",
                hint="Add a glossary entry for this entity, or rename it to match an existing term.")


def check_enum_glossary(spec: dict, glossary: Optional[dict], result: LayerResult):
    """ERROR: Every enum name must match a glossary term."""
    if not glossary:
        return

    for enum in spec.get("enums", []):
        ename = enum["name"]
        matches = match_glossary_term(ename, glossary)
        if not matches:
            result.add("error", "enum_not_in_glossary",
                f"Enum '{ename}' has no matching glossary term.",
                hint="Add a glossary entry for this enum, or rename it to match an existing term.")


def check_field_glossary_refs(spec: dict, glossary: Optional[dict], result: LayerResult):
    """INFO: Warn if field descriptions contain domain concepts but have no glossaryRefs."""
    if not glossary:
        return

    # Build glossary term set for matching
    glossary_lower = {t["name"].lower(): t["id"] for t in glossary.get("terms", [])}

    for entity in spec.get("entities", []):
        for field in entity.get("fields", []):
            desc = field.get("description", "")
            refs = field.get("glossaryRefs", [])

            if not desc or refs:
                continue  # No description or already has refs — skip

            # Check if description contains any glossary term
            desc_lower = desc.lower()
            has_domain_concept = any(
                len(term) > 3 and term in desc_lower
                for term in glossary_lower.keys()
            )

            if has_domain_concept:
                result.add("info", "field_no_glossary_refs",
                    f"Entity '{entity['name']}': field '{field['name']}' describes domain concepts but has no glossaryRefs.",
                    hint="Add glossaryRefs (GL-NNN) for domain concepts in this field's description.")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_lint(spec: dict, schema_path: Optional[Path], strict: bool,
             api_spec: Optional[dict] = None, glossary: Optional[dict] = None) -> LayerResult:
    result = LayerResult()

    # Schema validation (auto-generated from schema)
    if schema_path:
        schema = json.loads(Path(schema_path).read_text())
        schema_issues = SchemaValidator(schema).validate(spec)
        for issue in schema_issues:
            result.add(issue.severity, issue.category, issue.message, issue.hint)

    # Semantic checks
    check_primitives(spec, result)
    check_pk_naming(spec, result)
    entity_names = check_entities(spec, spec.get("enums", []), result)
    enum_names = check_enums(spec, result)

    check_abstract_entity_relationships(spec, result)
    check_relationships(spec, entity_names, result)
    check_enum_entity_conflict(spec, result)
    check_field_type_kinds(spec, entity_names, enum_names, result)
    check_duplicate_fields(spec, result)
    check_entity_should_be_field(spec, api_spec, result)
    check_field_should_be_entity(spec, api_spec, result)
    check_methods_coverage(spec, api_spec, result)
    check_entity_similarity(spec, result)
    check_similar_entities_connected(spec, result)
    check_bidirectional_relationships(spec, result)
    check_entity_list_fields(spec, result)

    # New semantic checks
    check_duplicate_relationships(spec, result)
    check_missing_descriptions(spec, result)
    check_method_apiRef(spec, api_spec, result)
    check_entity_glossary(spec, glossary, result)
    check_enum_glossary(spec, glossary, result)
    check_field_glossary_refs(spec, glossary, result)


    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output
# Uses shared.print_human and shared.print_json_output


def main():
    parser = argparse.ArgumentParser(description="Lint a DataSpec JSON.")
    parser.add_argument("input", help="Path to dataspec JSON")
    parser.add_argument("--schema", help="Path to dataspec.schema.json")
    parser.add_argument("--api", help="Path to apispec JSON (for cross-spec checks)")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    path = Path(args.input)
    spec = json.loads(path.read_text())
    schema_path = Path(args.schema) if args.schema else None
    api_spec = json.loads(Path(args.api).read_text()) if args.api else None

    result = run_lint(spec, schema_path, args.strict, api_spec)

    if args.json:
        print_json_output(result)
    else:
        print_human(result, str(path))

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
