# Troubleshooting Common Lint Failures

The linter checks three layers: **schema validation** (JSON Schema),
**semantic rules** (cross-field consistency), and **completeness gates**
(declarative readiness criteria).

## Schema errors

| Error | Cause | Fix |
|-------|-------|-----|
| `type_undefined` | Field references an ID not in the glossary or referenced spec | Add the ID to the correct spec or use a valid primitive type |
| `schema_additional_properties` | Field not allowed by schema | Check the proto-schema `fields` list; add field if legitimate |
| `id_format` | ID doesn't match pattern (e.g. `REQ-000-Name`) | Use `PREFIX-NNN-Name` format from `refs.yaml` |
| `id_gap` | Non-sequential ID numbers | IDs must be sequential from 0; fill gaps or renumber |

## Semantic rule errors

| Error | Cause | Fix |
|-------|-------|-----|
| `version_drift` | `archspec.goalSpecVersion` ≠ `goalspec.version` | Sync the version reference (strip/add `v` prefix as needed) |
| `rel_from_missing` / `rel_to_missing` | Relationship references non-existent entity ID | Use valid entity IDs from `entities[].id` |
| `fr_uncovered` | FR not referenced by any component in archspec | Add FR ID to a component's `reqRefs` |
| `nfr_uncovered` | NFR not referenced by any component | Add NFR ID to a component's `nfrRefs` |
| `us_uncovered` | User story not in any designspec user journey | Add US ID to a journey's `usRefs` |
| `component_unassigned` | Component not in any subsystem | Add component ID to a subsystem's `componentRefs` |
| `component_not_in_flow` | Component not in any data flow step | Add step referencing the component |

## Completeness gate warnings

| Warning | Cause | Fix |
|---------|-------|-----|
| `nfr_single_level` | NFR only has `must`, missing `plan`/`wish` | Add all three levels |
| `missing_expected_output` | Test lacks `expectedOutput` | Add output (skip for error-path tests) |
| `error_path_missing_code` | Error-path test lacks `errorCode` | Add error code |
| `*_gate` (future) | Gate required at higher lifecycle status | Will block when status advances; fix proactively |

## Gate levels

Gates have `required_at` status: `draft` → `review` → `confirmed`.
- Gates required at current status = **errors** (block)
- Gates required at future status = **warnings** (advisory)

To advance an artifact's status, all gates for that level must pass.
