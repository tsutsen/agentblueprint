# Proto-Schema System

Declarative YAML schemas that generate complete JSON Schema files.

## Directory Structure

```
proto/
  blocks/
    refs.yaml              # All ID patterns (single source of truth)
    base.yaml              # Shared base fields (version, project, status, etc.)
  artifact/
    goalspec.yaml          # Proto-schema for GoalSpec
    glossary.yaml          # Proto-schema for Glossary
    designspec.yaml        # Proto-schema for DesignSpec
    archspec.yaml          # Proto-schema for ArchitectureSpec
    dataspec.yaml          # Proto-schema for DataSpec
    apispec.yaml           # Proto-schema for ApiSpec
    testspec.yaml          # Proto-schema for TestSpec
    taskplan.yaml          # Proto-schema for TaskPlan
    issue.yaml             # Proto-schema for Issue
  specs/                   # Generated output (commit these)
    goalspec.schema.json
    glossary.schema.json
    ...
  generate_schema.py       # Generator script
```

## Usage

```bash
python3 generate_schema.py <type>          # Generate one schema
python3 generate_schema.py --all           # Generate all schemas
python3 generate_schema.py --dry-run <type> # Show assembled schema without writing
```

## Proto-Schema Format

### Top-Level Keys

| Key | Description |
|-----|-------------|
| `artifact` | Artifact type slug (e.g. `goalspec`, `apispec`) |
| `title` | Human-readable title (e.g. `GoalSpec`) |
| `schemaVersion` | Schema version string (e.g. `"4.0.0"`) |
| `description` | Short description of the artifact |
| `customDefinitions` | Simple type aliases (string with constraints) |
| `namedTypes` | Complex object types (for recursion, shared structures) |
| `fields` | Top-level fields of the artifact |

### Field Types

| Proto-Schema | JSON Schema Output |
|---|---|
| `type: string` + `minLength: 5` | `{"type": "string", "minLength": 5}` |
| `type: integer` + `minimum: 0` | `{"type": "integer", "minimum": 0}` |
| `type: boolean` + `default: false` | `{"type": "boolean", "default": false}` |
| `type: enum` + `enum: [a, b]` | `{"type": "string", "enum": ["a", "b"]}` |
| `type: any` | Any JSON value |
| `$ref: "typeName"` | `{"$ref": "#/definitions/typeName"}` |
| `type: array` + `ref: gl` | Array of glossary IDs |
| `type: object` + `ref: comp` + `fields` | Object with auto-injected id/name/description |
| `type: object` + `fields` | Plain object with nested properties |
| `of: { $ref: "self" }` | Recursive reference to parent type |
| `of: { $ref: "iaNode" }` | Reference to named type |
| `of: { ref: "ep" }` | Array of epic IDs (shorthand) |

### Auto-Injected Fields

When an object has `ref: <type>`, the generator automatically adds:

- `id` — references `#/definitions/<type>Id` with `x_idPattern`
- `name` — string with `minLength: 1`
- `description` — plain string

These fields are always present and NOT listed in `fields` or `required`.

### Rules

1. **Patterns are banned** — all ID patterns live in `blocks/refs.yaml`
2. **Auto-injected fields** — never list `id`, `name`, or `description` for ref'd objects
3. **`required`** — only lists extra fields beyond auto-injected ones
4. **`desc`** — human-readable description (maps to JSON Schema `description`)
5. **Recursive types** — use `namedTypes` + `$ref: "self"` for self-referencing structures

## Migration from JSON Schema

The proto-schema system replaces the existing `*.schema.json` files in the parent `schemas/` directory. To migrate:

1. Edit the proto-schema YAML to match desired structure
2. Run `python3 generate_schema.py --all`
3. Compare: `diff -r specs/ ../`
4. Once verified, copy `specs/*.schema.json` to parent directory

## Adding New Reference Types

1. Add entry to `blocks/refs.yaml` with `pattern` and `title`
2. Use `ref: <key>` in any artifact proto-schema
3. Run generator — the definition is auto-injected
