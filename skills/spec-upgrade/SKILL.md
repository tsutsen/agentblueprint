---
name: spec-upgrade
description: >
  Migrates artifact files (Markdown + JSON) from old schema format to new format.
  Detects and fixes schema mismatches (property renames, missing/extra fields).
  Loads the glossary and scans content to populate glossaryRefs intelligently.
  Converts old string arrays to structured objects.
  Use when schema changes require updating existing artifacts.
  By default (no extra arguments), scans and upgrades ALL artifacts.
version: 1.0.0
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

## What it does

The tool performs three types of upgrades:

### 1. Schema Mismatch Detection & Auto-Fix

Compares the artifact against its current schema and:
- **Adds missing required properties** with sensible defaults
- **Auto-migrates** properties with high-confidence name matches:
  - `parameters` → `inputs`
  - `output.name` → `output.description`
  - `component` → `description`
- **Reports** medium/low-confidence matches for approval (shows field, value preview, suggested target, confidence level)
- **Removes** empty/no-data fields safely
- **Does NOT remove** data without a clear migration target

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

## Migration Confidence Levels

| Confidence | Action | Example |
|------------|--------|---------|
| **High** | Auto-migrate | `parameters` → `inputs` |
| **Medium** | Report for approval | `output.properties` → `output` |
| **Low/None** | Report for manual review | Unknown field with no clear target |

## Output

After migration, the tool reports:

```
Upgrade complete for <ArtifactType>:
  Migrated: 5 field(s) → schema-compliant target
  Removed: 2 field(s) (empty/no data)
  Glossary fields added: 10
  Changes:
    - functions[0].parameters → inputs (auto-migrated)
    - functions[1].output.name → output.description (auto-migrated)
    - titleGlossaryRefs: [GL-001, GL-004]
    ...

⚠️  3 field(s) need approval before migration:
  ~ functions[0].output.properties (object): {"type":"string",...}
    → Suggested target: output
    Confidence: medium
  ? (root).apiSpecVersion (string): "1.0.0"
    Confidence: none

These fields were NOT migrated. Run /skill:lint <artifactType> to verify.
```

If no changes needed:

```
Upgrade complete for <ArtifactType>: No changes needed. Files are up to date.
```
