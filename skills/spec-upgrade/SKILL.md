---
name: spec-upgrade
description: >
  Migrates artifact files (Markdown + JSON) from old schema format to new format.
  Loads the glossary and scans content to populate glossaryRefs intelligently.
  Converts old string arrays to structured objects.
  Use when schema changes require updating existing artifacts.
version: 1.0.0
---

# Spec Upgrade

Migrates artifact files from old schema format to new format.

## When invoked

**Run the upgrade tool immediately.** Do not show documentation or ask for clarification.

```
tool: spec_upgrade
args:
  artifactType: <goal|glossary|design|arch|data|api|test|plan|issues>
  filePath: artifacts/<ArtifactType>.md
```

The tool will:
1. Load the current schema for the artifact type
2. Load the Glossary.json if available
3. Scan all text fields for glossary term references
4. Populate `glossaryRefs` arrays with matched GL-NNN IDs
5. Convert old string arrays to structured `{description, glossaryRefs}` objects
6. Update both the Markdown and JSON files

## Migration Strategy

The upgrade is **fully automatic** — it does not ask the user for values.
It scans content and makes intelligent suggestions based on the glossary.

### Glossary Term Matching

The tool loads `artifacts/Glossary.json` and performs **whole-word, case-insensitive**
matching against all text fields. If a glossary term appears in a field's text,
its GL-NNN ID is added to that field's `glossaryRefs`.

### Array Conversion

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

### Fields Populated Per Artifact Type

- **GoalSpec**: `objective.glossaryRefs`, `functionalRequirements[].glossaryRefs`,
  `nonFunctionalRequirements[].glossaryRefs`, `userStories[].glossaryRefs`,
  `nonGoals[].glossaryRefs`
- **DesignSpec**: `userPersonas[].glossaryRefs`, `userJourneys[].steps[].glossaryRefs`,
  `screenInventory[].glossaryRefs`, `screenSpecs[].components[].glossaryRefs`
- **ArchitectureSpec**: `components[].glossaryRefs`, `dataFlows[].glossaryRefs`,
  `constraints[].glossaryRefs`
- **DataSpec**: `entities[].glossaryRefs`, `entities[].fields[].glossaryRefs`
- **TaskPlan**: `epics[].inScope[].glossaryRefs`, `epics[].outOfScope[].glossaryRefs`
- **TestSpec**: `tests[].glossaryRefs`, `functionCoverage[].outOfScope[].glossaryRefs`
- **Issue**: `titleGlossaryRefs`, `inScope[].glossaryRefs`,
  `outOfScope[].glossaryRefs`, `acceptanceCriteria[].glossaryRefs`

## Output

After migration, the tool reports:

```
Upgrade complete for <ArtifactType>:
  Fields added: N
  - titleGlossaryRefs: [GL-001, GL-004]
  - epics[].inScope[].glossaryRefs: [GL-002]
  ...

Files updated:
  - artifacts/<ArtifactType>.md
  - artifacts/<ArtifactType>.json

Run /skill:lint <artifactType> to verify.
```

If no glossary terms were found in the content:

```
Upgrade complete for <ArtifactType>: No glossary references found in content. Files are up to date.
```
