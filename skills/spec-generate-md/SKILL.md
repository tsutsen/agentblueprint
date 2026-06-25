---
name: spec-generate-md
description: >
  Regenerates agent instruction documentation from JSON schema files.
  The JSON schema is the single source of truth; markdown is derived.
  Run after any JSON schema change to keep docs in sync.
version: 1.0.0
---

# Generate Markdown Schemas

Regenerates agent instruction documentation from JSON schema files.

## When invoked

**Run the tool immediately.** Do not show documentation or ask for clarification.

```
tool: generate_markdown_schemas
args:
  artifactType: []  # omit for all; or ["goal", "glossary", "design", ...]
```

## What It Does

1. Reads each `*.schema.json` file from `skills/blueprint/schemas/json/`
2. Extracts all properties, types, constraints, enums, and descriptions
3. Generates a corresponding `*.md` file in `skills/blueprint/instructions/`
4. Each generated markdown includes:
   - Frontmatter with artifact name and type
   - Title and description from JSON schema
   - Output format section
   - Field table with type, required, description, constraints
   - Nested structure definitions (recursive)
   - Enum definitions
   - Minimal valid JSON example

## Artifact Types

| Type | JSON Schema | Markdown Output |
|------|-------------|-----------------|
| `goal` | goalspec.schema.json | GoalSpec.md |
| `glossary` | glossary.schema.json | Glossary.md |
| `design` | designspec.schema.json | DesignSpec.md |
| `arch` | archspec.schema.json | ArchitectureSpec.md |
| `data` | dataspec.schema.json | DataSpec.md |
| `api` | apispec.schema.json | ApiSpec.md |
| `test` | testspec.schema.json | TestSpec.md |
| `plan` | taskplan.schema.json | TaskPlan.md |
| `issue` | issue.schema.json | Issue.md |

## Usage

```
# Regenerate all schemas
tool: generate_markdown_schemas
args:
  artifactType: []

# Regenerate specific schemas
tool: generate_markdown_schemas
args:
  artifactType: ["glossary", "goal"]
```

## After Regeneration

1. Review the generated markdown for any sections that need manual refinement
2. The generated content covers all JSON schema fields — no desync possible
3. Run `/skill:lint` to verify artifacts still conform
4. Commit the updated markdown files
