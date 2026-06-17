---
name: lint
description: >
  Runs the SDLC spec lint suite against project artifacts. Validates JSON
  structure, cross-spec references, completeness gates, and Markdown/JSON
  consistency. Use anytime the user wants to check artifact quality, diagnose
  lint errors, or verify readiness for the next lifecycle stage.
version: 2.0.0
---

# Lint

Runs the full SDLC spec lint suite. Validates artifacts against their schemas,
checks cross-spec references, enforces completeness gates, and detects
Markdown/JSON drift.

---

## Invocation

```
/skill:lint                            # Quick check all artifacts in artifacts/
/skill:lint data                       # Lint only DataSpec
/skill:lint data api                   # Lint DataSpec + ApiSpec
/skill:lint --strict                   # Warnings as errors (all artifacts)
/skill:lint --json                     # Machine-readable output
/skill:lint data --strict              # Lint DataSpec, warnings as errors
```

---

## What It Checks

### lint_dataspec.py
| Check | Severity | Description |
|-------|----------|-------------|
| `entity_name_format` | ERROR | Entity names must be PascalCase |
| `field_name_format` | ERROR | Field names must be camelCase |
| `method_name_format` | ERROR | Method names must be camelCase |
| `method_api_ref_format` | ERROR | apiRef must match FN-<camelCase> |
| `entity_visibility_invalid` | ERROR | Visibility must be public/internal |
| `extends_missing` | ERROR | Parent entity must exist |
| `type_undefined` | ERROR | Field type must resolve to primitive/entity/enum |
| `rel_from_missing` | ERROR | Relationship from-entity must exist |
| `rel_to_missing` | ERROR | Relationship to-entity must exist |
| `rel_to_enum` | ERROR | Relationship cannot target an enum |
| `rel_type_invalid` | ERROR | Relationship type must be valid |
| `enum_name_format` | ERROR | Enum names must be PascalCase |
| `enum_value_format` | ERROR | Enum values must be SCREAMING_SNAKE_CASE |
| `enum_entity_conflict` | ERROR | Same name cannot be both entity and enum |
| `primitives_missing` | ERROR | Expected primitives (void, etc.) must be defined |
| `duplicate_field` | ERROR | No duplicate field names within an entity |
| `primitives_any` | WARNING | Warns if 'any' is in primitives |
| `rel_self_reference` | WARNING | Warns on self-referencing relationships |
| `type_ambiguous_kind` | WARNING | Field type exists as both entity and enum |
| `entity_should_be_field` | WARNING | Entity with ≤3 fields, all primitives, ≤1 relationship |
| `field_should_be_entity` | WARNING | Field with >5 fields, identity, ≥2 referrers |
| `methods_missing` | WARNING | Entity with ≥2 API functions but 0 methods |
| `entity_similarity` | WARNING | Similar names + high field overlap |
| `similar_entities_disconnected` | WARNING | Similar names but no relationship |
| `entity_list_field` | WARNING | Entity has `Entity[]` field — should be a relationship |
| `bidirectional_relationship` | WARNING | A → B and B → A both exist — DBML limitation |
| `duplicate_relationship` | WARNING | Same entity pair has multiple relationships of same type |
| `field_naming` | WARNING | Field doesn't follow camelCase convention |
| `missing_entity_description` | INFO | Entity has no description |
| `missing_field_description` | INFO | Field has no description |
| `invalid_cardinality` | ERROR | Relationship has invalid cardinality value |
| `invalid_apiRef` | WARNING | Method references undefined apiRef in ApiSpec |
| `enum_value_naming` | WARNING | Enum value doesn't follow UPPER_SNAKE_CASE |
| `orphan_relationship` | ERROR | Relationship references undefined entity |

### lint_apispec.py
| Check | Severity | Description |
|-------|----------|-------------|
| `fn_id_format` | ERROR | Function IDs must be FN-<camelCase> |
| `fn_name_format` | ERROR | Function names must be camelCase |
| `param_name_format` | ERROR | Parameter names must be camelCase |
| `output_type_format` | ERROR | Output type must be valid |
| `error_code_format` | ERROR | Error codes must be SCREAMING_SNAKE_CASE |
| `entity_ref_missing` | ERROR | Entity must exist in data spec |
| `type_ref_missing` | ERROR | Parameter type must resolve in data spec |
| `output_type_ref_missing` | ERROR | Output type must resolve in data spec |
| `output_type_not_in_data_spec` | ERROR | Output type is API primitive but not in data spec |
| `module_mismatch` | ERROR | Module must match data spec |
| `version_mismatch` | ERROR | dataSpecVersion must match data spec |
| `fn_visibility_invalid` | ERROR | Visibility must be public/internal |
| `fn_no_errors` | WARNING | Data-modifying functions should document errors |
| `duplicate_function_name` | ERROR | Multiple functions share the same name |
| `missing_function_description` | INFO | Function has no description |
| `missing_parameter_description` | INFO | Parameter has no description |
| `missing_output_description` | INFO | Output has no description |
| `required_param_no_description` | WARNING | Required parameter has no description |
| `internal_function_with_errors` | INFO | Internal function documents error conditions |
| `internal_function_public_tags` | INFO | Internal function has public-facing tags |
| `unused_function` | WARNING | Function not referenced by any entity's apiRef |
| `type_case_mismatch` | ERROR | Type case doesn't match data spec |

### lint_taskplan.py
| Check | Severity | Description |
|-------|----------|-------------|
| `milestones` | ERROR | Milestone structure is valid |
| `epics` | ERROR | Epic structure is valid |
| `coverage` | ERROR | All GoalSpec requirements are covered by epics |
| `non-goal` | ERROR | No epic implements a GoalSpec non-goal |
| `dependencies` | ERROR | Epics are in dependency order; blockers before dependents |
| `milestones` | ERROR | Milestones have demonstrable outcomes |
| `milestones` | ERROR | Every epic belongs to exactly one milestone |
| `cross-ref` | ERROR | All REQ-IDs in TaskPlan exist in GoalSpec |
| `duplicate_entity_name` | ERROR | Duplicate entity name in DataSpec |
| `duplicate_enum_name` | ERROR | Duplicate enum name in DataSpec |
| `abstract_entity_composition` | ERROR | Abstract entity is target of composition/aggregation |
| `duplicate_relationship` | WARNING | Same entity pair has multiple relationships of same type |
| `file-exists` | ERROR | Epic file does not exist at expected path |
| `ac-quality` | WARNING | Acceptance criterion uses vague or implementation language |
| `title-action` | WARNING | Epic title describes technical layer, not capability |
| `scope-specific` | WARNING | outOfScope item is vague |
| `milestone-consistency` | ERROR | Milestone epic list mismatches epic milestone field |
| `circular-dependency` | ERROR | Circular dependency detected among epics |
| `nfr-coverage` | WARNING | Non-functional requirement not covered by any epic |
| `cross-spec-coverage` | WARNING | Spec capability/component/entity may not be covered |

### lint_all.py (Completeness Gates)
| Gate | Required At | Description |
|------|-------------|-------------|
| `Has at least one entity` | draft | DataSpec |
| `Has at least one relationship` | draft | DataSpec |
| `All entities have descriptions` | review | DataSpec |
| `No orphan entities` | review | DataSpec |
| `Orphan entities < 20%` | review | DataSpec |
| `All entities have field examples` | confirmed | DataSpec |
| `Has at least one function` | draft | ApiSpec |
| `All functions have descriptions` | review | ApiSpec |
| `All functions have error conditions` | review | ApiSpec |
| `All functions declare entity affinity` | review | ApiSpec |
| `All functions declare pure/impure` | confirmed | ApiSpec |

### lint_consistency.py
| Check | Severity | Description |
|-------|----------|-------------|
| `entity_only_markdown` | WARNING | Entity in Markdown but not JSON |
| `entity_only_json` | WARNING | Entity in JSON but not Markdown |
| `enum_only_markdown` | WARNING | Enum in Markdown but not JSON |
| `enum_only_json` | WARNING | Enum in JSON but not Markdown |
| `rel_only_markdown` | WARNING | Relationship in Markdown but not JSON |
| `rel_only_json` | WARNING | Relationship in JSON but not Markdown |
| `fn_only_markdown` | WARNING | Function in Markdown but not JSON |
| `fn_only_json` | WARNING | Function in JSON but not Markdown |

---

## Linter Files

| File | Purpose |
|------|---------|
| `lint_all.py` | Unified orchestrator — runs all linters, cross-checks, completeness gates |
| `lint_dataspec.py` | DataSpec validation + semantic checks |
| `lint_apispec.py` | ApiSpec validation + cross-spec checks |
| `lint_consistency.py` | Markdown/JSON drift detection |

---

## Usage in Sessions

### Before starting an artifact interview
Run the linter to check existing artifacts:

```
/skill:lint data api
```

If errors are found, fix them before proceeding. If only warnings, note them
but proceed.

### After modifying an artifact
Run targeted lint to verify changes:

```
/skill:lint data
```

### Before advancing lifecycle status
Run the full suite to check completeness gates:

```
/skill:lint data api --strict
```

The `--strict` flag treats warnings as errors, ensuring no warnings remain
before advancing.

### Quick check
For a fast status check, run without arguments — it scans `artifacts/` for
any JSON files and lints them:

```
/skill:lint
```

---

## Output Formats

### Human-readable (default)
```
────────────────────────────────────────────────────────────
  SDLC Spec Suite — Lint + Completeness Report
────────────────────────────────────────────────────────────

  LINT
  ✓  goalspec      clean
  ⚠  dataspec      3 warning(s)
  ✗  apispec       1 error(s)  2 warning(s)

  COMPLETENESS
  ███░░  50%  dataspec  (status: draft)  [0 blocking gate(s)]
  █░░░░  25%  apispec   (status: review) [1 blocking gate(s)]

  ────────────────────────────────────────────────────────────
  FAIL  —  1 error(s), 5 warning(s) across 8 layers
────────────────────────────────────────────────────────────
```

### JSON (`--json`)
```json
{
  "clean": false,
  "totalErrors": 1,
  "totalWarnings": 5,
  "suiteCompletenessPct": 38,
  "layers": [...],
  "completeness": [...]
}
```

---

## Common Fixes

### "Entity 'X' does not exist"
Add the missing entity to DataSpec, or remove the reference from the
relationship/field that points to it.

### "Relationship targets enum 'X'"
Enums are type references, not relationship targets. Remove the relationship
and reference the enum via a field type instead.

### "Name 'X' is defined as both an enum and an entity"
Keep the enum for type references. Remove the entity and use the enum.

### "Orphan entities < 20%"
Add relationships to orphaned entities, or merge them into related entities.

### "Entity 'X' looks like it should be a field of 'Y'"
If the entity has ≤3 simple fields and few relationships, consider moving
its fields to the parent entity 'Y'.

### "Field 'X.Y' of type 'Z' looks like it should be a separate entity"
If the field type 'Z' has >5 fields, identity, and multiple referrers,
it may warrant being a top-level entity rather than a nested field.
