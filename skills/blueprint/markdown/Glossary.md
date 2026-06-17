---
name: Glossary
type: schema
version: 1.0.0
---

# Glossary

Project vocabulary. Defines all domain terms used across specs. Version 1.0.0.

## Output Format

This artifact produces two files:

- `artifacts/Glossary.md` — human-readable document (this format)
- `artifacts/Glossary.json` — machine-readable, conforming to `schemas/glossary.schema.json`

## Schema Reference

### Root Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | `string` | Yes | pattern: `^\d+\.\d+\.\d+$` (e.g. d+.d+.d+) |
| `schemaVersion` | `string` | Yes | must be: `1.0.0` |
| `project` | `string` | Yes | Must match project name across all other specs. (min length: 1) |
| `terms` | `array` of `array` of `object` | Yes | All domain terms. Each must be independently understandable. (min items: 1) |

### Nested Structures

#### `terms` items

Each `terms` must have:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `term` | `string` | Yes | The term exactly as it appears in other specs. Case-sensitive. (min length: 1) |
| `definition` | `string` | Yes | Precise, unambiguous definition. Must not use the term itself in the definition. (min length: 10) |
| `examples` | `array` of `array` of `string` | No | Optional concrete examples that clarify the definition. |
| `synonyms` | `array` of `array` of `string` | No | Other names for this term used in the project. Synonyms should not have their own entry. |
| `relatedTerms` | `array` of `array` of `string` | No | GL-NNN identifiers of other terms in this glossary that are closely related. |
| `category` | `string` | No | Optional grouping tag, e.g. 'domain', 'technical', 'process'. |
| `id` | `string` | Yes | Unique glossary term identifier. Format: GL-NNN (3-digit zero-padded, sequential). (pattern: `^GL-\d{3}$` (e.g. GL-d{3})) |

## Minimal Example

```json
{
  "version": "example",
  "schemaVersion": "1.0.0",
  "project": "Example Project",
  "terms": [
    {
      "term": "example",
      "definition": "example",
      "id": "GL-001",
      "examples": [
        "example"
      ],
      "synonyms": [
        "example"
      ],
      "relatedTerms": [
        "example"
      ],
      "category": "example"
    }
  ]
}
```
