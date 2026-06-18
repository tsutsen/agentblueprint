---
name: spec-upgrade
description: >
  Migrates artifact files (Markdown + JSON) from old schema format to new format.
  Detects and fixes schema mismatches (property renames, missing/extra fields).
  Loads the glossary and scans content to populate glossaryRefs intelligently.
  Converts old string arrays to structured objects.
  Use when schema changes require updating existing artifacts.
  By default (no extra arguments), scans and upgrades ALL artifacts.
version: 2.0.0
---

# Spec Upgrade

Migrates artifact files from old schema format to new format.

## When invoked

**Run the upgrade tool immediately.** Do not show documentation or ask for clarification.

### Default: Upgrade all artifacts

```
tool: spec_upgrade
args:
  artifactType: all
```

This scans all artifacts in `artifacts/`, compares each against its current schema,
and migrates as needed.

### Single artifact

```
tool: spec_upgrade
args:
  artifactType: <goal|glossary|design|arch|data|api|test|plan|issues>
  filePath: artifacts/<ArtifactType>.md
```

## What the tool does

The tool performs three types of upgrades:

### 1. Schema Mismatch Detection & Auto-Fix

Compares the artifact against its current schema:

- **Adds missing required properties** with sensible defaults
- **Auto-migrates** properties with high-confidence name alias matches:

  | Source field | Target schema property |
  |--------------|----------------------|
  | `parameters`, `args`, `arguments` | `inputs` |
  | `output`, `result`, `response` | `output` |
  | `description`, `desc`, `detail`, `summary` | `description` |
  | `name`, `title`, `label` | `name` |
  | `type`, `kind`, `category` | `type` |
  | `version`, `ver`, `revision` | `version` |
  | `component`, `module`, `part` | `component` |
  | `properties`, `fields`, `attributes` | `properties` |

- **Removes empty/no-data fields** (safe — no data loss)
- **Does NOT remove fields with meaningful data** — reports them as schema violations in `dataAtRisk`

### 2. Glossary Term Matching

Loads `artifacts/Glossary.json` and performs **whole-word, case-insensitive**
matching against all text fields. If a glossary term appears in a field's text,
its GL-NNN ID is added to that field's `glossaryRefs`.

### 3. Array Conversion

Old format (string arrays):
```json
"inScope": ["User login", "Password reset"]
```

New format (structured objects):
```json
"inScope": [
  { "description": "User login", "glossaryRefs": ["GL-001"] },
  { "description": "Password reset", "glossaryRefs": ["GL-002"] }
]
```

### 4. Schema Reference Validation

Checks the schema itself for broken `$ref` pointers (e.g., referencing a
definition that doesn't exist). Reports these as schema-level errors that
must be fixed in the JSON schema file.

## Migration Confidence

| Confidence | Action |
|------------|--------|
| **High** | Auto-migrate (clear name alias match) |
| **None** | Report as schema violation — field stays in JSON |

**The tool never removes data with meaningful content.** If a field has data
but doesn't match any schema property, it is reported in `dataAtRisk` for
the skill/agent to review.

## Output

After migration, the tool reports:

```
Upgrade complete for <ArtifactType>:
  Migrated: 5 field(s) → schema-compliant target
  Removed: 2 field(s) (empty/no data)
  Glossary fields added: 10
  Changes:
    - functions[0].parameters → inputs (auto-migrated)
    - functions[1].desc → description (auto-migrated)
    - titleGlossaryRefs: [GL-001, GL-004]
    ...

⚠️  Schema reference errors (schema-level issue — schema must be fixed):
    ✗ .properties.glossaryRefs.items: "$ref: #/definitions/glId" — definition "glId" not found.

⚠️  31 field(s) violate schema (additionalProperties: false) — not auto-removed:
    ✗ requirementsTests[0].glossaryRefs (array): [1 items]
      → Not in schema (additionalProperties: false)
    ✗ requirementsTests[1].glossaryRefs (array): [1 items]
      → Not in schema (additionalProperties: false)
    ...

  The tool does NOT remove fields with meaningful data.
  The skill/agent should review these violations and decide whether to:
    - Remove the fields from the artifact
    - Add the fields to the schema
    - Rename the fields to match the schema

  Run /skill:lint <artifactType> to verify these are resolved.

Files updated:
  - artifacts/TestSpec.md
  - artifacts/TestSpec.json

Run /skill:lint test to verify.
```

If no changes needed:

```
Upgrade complete for <ArtifactType>: No changes needed. Files are up to date.
```

## Skill/Agent Action Items

When the tool reports `dataAtRisk` violations, the skill/agent should:

1. **Review each violation** — is the field truly unnecessary, or does the schema need updating?
2. **If the field should be removed** — use the `edit` tool to remove it from the JSON, then regenerate the Markdown.
3. **If the field should be in the schema** — update the JSON schema file (after verifying with the team).
4. **If the field is a renamed schema property** — rename it to match the current schema.
5. **Re-run lint** to confirm all violations are resolved.
