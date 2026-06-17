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
| `missing_entity_description` | INFO | Entity has no description |
| `missing_field_description` | INFO | Field has no description |
| `invalid_apiRef` | WARNING | Method references undefined apiRef in ApiSpec |

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

### lint_archspec.py
| Check | Severity | Description |
|-------|----------|-------------|
| `project_match` | ERROR | Project name mismatch between ArchSpec and GoalSpec |
| `version_drift` | ERROR | GoalSpec version mismatch |
| `duplicate_id` | ERROR | Duplicate component/constraint/flow ID |
| `dependency_ref` | ERROR | Component dependency references undefined component |
| `subsystem_ref` | ERROR | Subsystem references undefined component |
| `flow_component_ref` | ERROR | Data flow step references undefined component |
| `flow_too_short` | ERROR | Data flow has fewer than 2 steps |
| `constraint_id_gap` | WARNING | Constraint numbering skips |
| `constraint_implementation_leak` | WARNING | Constraint mentions specific technology |
| `req_ref_missing` | ERROR | REQ ref not found in GoalSpec |
| `nfr_ref_missing` | ERROR | NFR ref not found in GoalSpec |
| `component_no_reqs` | WARNING | Component has no reqRefs at non-draft status |
| `component_no_subsystem` | WARNING | Component not assigned to any subsystem |
| `overlapping_responsibility` | WARNING | Two components claim the same responsibility |
| `circular_dependency` | ERROR | Circular component dependency detected |
| `fr_uncovered` | WARNING | GoalSpec FR not covered by any component |
| `nfr_uncovered` | WARNING | GoalSpec NFR not covered by any component or constraint |
| `constraint_no_nfr` | WARNING | Constraint has no NFR refs |
| `subsystem_empty` | WARNING | Subsystem has no components assigned |
| `subsystem_overlap` | WARNING | Component assigned to multiple subsystems |
| `data_ref_missing` | WARNING | Data flow references undefined DataSpec entity |
| `component_responsibility_count` | WARNING | Component has >8 responsibilities |
| `flow_step_count` | WARNING | Data flow has >15 steps |
| `external_component_count` | WARNING | >50% of components are external |
| `dependency_depth` | WARNING | Component has dependency chain >5 levels deep |

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
| `duplicate-requirements` | WARNING | Requirement covered by >2 epics (cross-cutting concerns OK in 2) |
| `milestone-size` | WARNING | Milestone has >10 epics — consider splitting |
| `self-dependency` | ERROR | Epic lists itself as blockedBy or blocks |
| `unknown-dependency` | ERROR | Dependency references unknown epic |
| `duplicate-name` | WARNING | Two milestones or epics share the same name |
| `ac-length` | WARNING | Acceptance criterion too short |
| `scope-length` | WARNING | Scope item too short |
| `missing-objective` | WARNING | Epic has no objective field |
| `ac-quality` | WARNING | Acceptance criterion uses vague or implementation language |
| `title-action` | WARNING | Epic title describes technical layer, not capability |
| `scope-specific` | WARNING | outOfScope item is vague |
| `non-goal` | ERROR | Epic implements a GoalSpec non-goal |
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
| `Has at least one milestone` | draft | TaskPlan |
| `Has at least one epic` | draft | TaskPlan |
| `Every epic covers at least one requirement` | draft | TaskPlan |
| `All epics assigned to a milestone` | draft | TaskPlan |
| `All epics have acceptance criteria` | review | TaskPlan |
| `All epics have scope (inScope + outOfScope)` | review | TaskPlan |
| `All epics have explicit dependencies` | review | TaskPlan |
| `Epics are in dependency order` | review | TaskPlan |
| `No circular dependencies` | review | TaskPlan |
| `All milestones have demonstrable outcomes` | review | TaskPlan |
| `All epics have an objective` | review | TaskPlan |
| `All acceptance criteria are meaningful length` | review | TaskPlan |
| `All scope items are meaningful length` | review | TaskPlan |
| `All GoalSpec requirements covered by epics` | review | TaskPlan |
| `All DesignSpec capabilities covered by epics` | review | TaskPlan |
| `All ArchitectureSpec components covered by epics` | review | TaskPlan |
| `No epic implements a non-goal` | review | TaskPlan |
| `No self-referencing dependencies` | review | TaskPlan |
| `No unknown dependencies` | review | TaskPlan |

### lint_issues.py
| Check | Severity | Description |
|-------|----------|-------------|
| `dependency_ref` | ERROR | blocked_by reference does not exist |
| `blocked_by_pattern` | ERROR | blocked_by item is not a valid IS-NNN |
| `blocked_by_cycles` | ERROR | Circular dependency in blocked_by graph |
| `epic_consistency` | ERROR | issue.epic does not match target epic ID |
| `missing_section` | ERROR | Required markdown section missing (What to build, Acceptance criteria, Blocked by) |
| `schema_field` | ERROR | Missing or invalid required field |
| `dependency_ordering` | WARNING | Blocked issue has higher IS-NNN than blocker |
| `duplicate_blocked_by` | WARNING | Duplicate entries in blocked_by |
| `date_ordering` | WARNING | updated date before created date |
| `title_too_short` | WARNING | Title is fewer than 5 characters |
| `milestone_consistency` | WARNING | Milestone not found in TaskPlan |
| `ac_too_few` | WARNING | Fewer than 2 acceptance criteria |
| `ac_all_checked` | WARNING | All acceptance criteria already checked |
| `ac_bad_format` | WARNING | AC does not use '- [ ]' format |
| `body_too_short` | WARNING | 'What to build' section is fewer than 10 words |
| `id_gap` | WARNING | Gap in issue ID sequence within epic |

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
