---
name: spec-upgrade
description: >
  Migrates artifact files (Markdown + JSON) from old schema format to new format.
  Detects missing fields, prompts the user for values, and updates both files.
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
2. Compare existing fields against the schema
3. Identify missing fields (new fields added since the artifact was created)
4. Prompt the user for values for each missing field
5. Update both the Markdown and JSON files

## Migration Workflow

### Step 1 — Detect changes

Load the artifact's current schema and compare against the existing file's frontmatter/JSON structure.

Identify which fields are:
- **Missing** — new fields not present in the artifact
- **Changed type** — fields that exist but have a different structure

### Step 2 — Prompt for values

For each missing field, ask the user for a value. Use these strategies:

1. **If the field has a clear default**: suggest it and ask for confirmation
   > "New field: `glossaryRefs` (array of GL-NNN). Suggested: [] (empty). OK?"

2. **If the field can be derived from context**: propose a value
   > "New field: `titleGlossaryRefs`. I found these glossary terms in the title: GL-001, GL-004. Use these?"

3. **If the field needs user input**: ask directly
   > "New field: `milestone`. What milestone should this issue belong to? (M1, M2, ...)"

4. **If the field is optional and empty is acceptable**: default to empty
   > "New field: `glossaryRefs`. Leave empty ([])? [yes/no]"

### Step 3 — Update files

After collecting all values:
1. Update the Markdown frontmatter with new fields
2. Update the JSON file with new fields
3. Verify both files are consistent
4. Report what was added

## Field Migration Reference

### GoalSpec
| New Field | Type | Default | Derivation |
|-----------|------|---------|------------|
| `objective.glossaryRefs` | GL-NNN[] | [] | Scan objective text for glossary terms |
| `functionalRequirements[].glossaryRefs` | GL-NNN[] | [] | Scan requirement text for glossary terms |
| `nonFunctionalRequirements[].glossaryRefs` | GL-NNN[] | [] | Scan NFR text for glossary terms |
| `userStories[].glossaryRefs` | GL-NNN[] | [] | Scan story text for glossary terms |
| `nonGoals[].glossaryRefs` | GL-NNN[] | [] | Scan non-goal text for glossary terms |

### DesignSpec
| New Field | Type | Default | Derivation |
|-----------|------|---------|------------|
| `userPersonas[].glossaryRefs` | GL-NNN[] | [] | Map persona role to glossary actors |
| `userJourneys[].steps[].glossaryRefs` | GL-NNN[] | [] | Scan step action for glossary terms |
| `screenInventory[].glossaryRefs` | GL-NNN[] | [] | Scan screen purpose for glossary terms |
| `screenSpecs[].components[].glossaryRefs` | GL-NNN[] | [] | Scan component purpose for glossary terms |

### ArchitectureSpec
| New Field | Type | Default | Derivation |
|-----------|------|---------|------------|
| `components[].glossaryRefs` | GL-NNN[] | [] | Scan component concepts for glossary terms |
| `dataFlows[].glossaryRefs` | GL-NNN[] | [] | Scan flow concepts for glossary terms |
| `constraints[].glossaryRefs` | GL-NNN[] | [] | Scan constraint concepts for glossary terms |

### DataSpec
| New Field | Type | Default | Derivation |
|-----------|------|---------|------------|
| `entities[].glossaryRefs` | GL-NNN[] | [] | Map entity name to glossary entry |
| `entities[].fields[].glossaryRefs` | GL-NNN[] | [] | Scan field description for glossary terms |

### TaskPlan
| New Field | Type | Default | Derivation |
|-----------|------|---------|------------|
| `epics[].titleGlossaryRefs` | GL-NNN[] | [] | Scan epic title + objective for glossary terms |
| `epics[].inScopeGlossaryRefs` | GL-NNN[] | [] | Collect from inScope items |
| `epics[].outOfScopeGlossaryRefs` | GL-NNN[] | [] | Collect from outOfScope items |
| `epics[].inScope[].glossaryRefs` | GL-NNN[] | [] | Scan scope item text for glossary terms |
| `epics[].outOfScope[].glossaryRefs` | GL-NNN[] | [] | Scan outOfScope item text for glossary terms |

### TestSpec
| New Field | Type | Default | Derivation |
|-----------|------|---------|------------|
| `tests[].glossaryRefs` | GL-NNN[] | [] | Scan description + contractClause for glossary terms |
| `functionCoverage[].outOfScope[].glossaryRefs` | GL-NNN[] | [] | Scan outOfScope item text for glossary terms |
| `functionCoverage[].outOfScope[]` | {description, glossaryRefs} | — | Convert string items to structured objects |

### Issue
| New Field | Type | Default | Derivation |
|-----------|------|---------|------------|
| `titleGlossaryRefs` | GL-NNN[] | [] | Scan title for glossary terms |
| `inScope[].glossaryRefs` | GL-NNN[] | [] | Scan scope item text for glossary terms |
| `outOfScope[].glossaryRefs` | GL-NNN[] | [] | Scan outOfScope item text for glossary terms |
| `acceptanceCriteria[].glossaryRefs` | GL-NNN[] | [] | Scan AC text for glossary terms |

## Output

After migration, report:

```
Upgrade complete for <ArtifactType>:
  Fields added: N
  - <field1>: <value>
  - <field2>: <value>
  ...

Files updated:
  - artifacts/<ArtifactType>.md
  - artifacts/<ArtifactType>.json

Run /skill:lint <artifactType> to verify.
```
