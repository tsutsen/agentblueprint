# Proto-Schema System — Implementation Guide

## Overview

A new proto-schema system where YAML files define artifact schemas using a simple, declarative format. A generator assembles complete JSON Schema files from proto-schemas + shared blocks.

**Before:** Each `*.schema.json` file contains ~500-1500 lines of JSON Schema with duplicated ID patterns, cross-refs, and base fields.

**After:** Each `artifact/*.yaml` file is ~50-150 lines of YAML. The generator injects all shared infrastructure.

---

## Architecture

```
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

---

## Proto-Schema Format

### Complete Example (ArchitectureSpec)

```yaml
artifact: archspec
title: ArchitectureSpec
schemaVersion: "2.0.0"
description: "Structural specification of the system"

fields:
  - name: overview
    type: object
    required: [summary, subsystems]
    fields:
      - name: summary
        type: string
        minLength: 30
      - name: subsystems
        type: array
        minItems: 1
        of:
          type: object
          required: [name, purpose]
          fields:
            - name: name
              type: string
              minLength: 1
            - name: purpose
              type: string
              minLength: 5
            - name: componentRefs
              type: array
              ref: comp
      - name: glossaryRefs
        type: array
        ref: gl

  - name: components
    type: array
    minItems: 1
    of:
      type: object
      ref: comp
      required: [purpose, responsibilities]
      fields:
        - name: purpose
          type: string
          minLength: 10
        - name: responsibilities
          type: array
          minItems: 1
          of: { type: string, minLength: 5 }
        - name: dependencies
          type: array
          ref: comp
        - name: reqRefs
          type: array
          ref: req
        - name: nfrRefs
          type: array
          ref: nfr
        - name: visibility
          type: enum
          enum: [external, internal]
          default: internal
        - name: glossaryRefs
          type: array
          ref: gl

  - name: dataFlow
    type: array
    minItems: 1
    of:
      type: object
      ref: flw
      required: [name, steps]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: steps
          type: array
          minItems: 2
          of:
            type: object
            required: [componentRef, action]
            fields:
              - name: componentRef
                type: string
                ref: comp
              - name: action
                type: string
                minLength: 5
              - name: dataRef
                type: string
        - name: nfrRefs
          type: array
          ref: nfr
        - name: componentRefs
          type: array
          ref: comp

  - name: constraints
    type: array
    minItems: 1
    of:
      type: object
      ref: con
      required: [description]
      fields:
        - name: description
          type: string
          minLength: 10
        - name: rationale
          type: string
        - name: nfrRefs
          type: array
          ref: nfr
        - name: reqRefs
          type: array
          ref: req
```

### Rules

| Rule | How |
|------|-----|
| **Object has an ID** | `ref: <name>` on the `type: object` |
| **`id` / `name` / `description`** | Auto-injected. Never list them in `fields`. |
| **`required`** | Only lists extra fields beyond id/name/description |
| **Array of strings** | `type: array` (no `ref`) |
| **Array of refs** | `type: array` + `ref: <name>` at same level |
| **Enum** | `type: enum` with `enum: [a, b]` |
| **Nested object** | `type: object` + `fields: [...]` |
| **String with constraints** | `type: string` + `minLength: 10` |
| **Patterns** | BANNED — all patterns live in `blocks/refs.yaml` |
| **`$ref` to named type** | `of: { $ref: "typeName" }` |
| **`$ref` to self (recursive)** | `of: { $ref: "self" }` |
| **Any type** | `type: any` (string/number/boolean/object/array/null) |

### Auto-Injected Fields

When an object has `ref: <type>`, the generator automatically adds:

```json
{
  "id":     { "$ref": "#/definitions/<type>Id", "x_idPattern": "<type>" },
  "name":   { "type": "string", "minLength": 1, "description": "Human-readable <type> name" },
  "description": { "type": "string", "description": "Longer description" }
}
```

These are always present. They are NOT listed in `fields` or `required`.

---

## Blocks

### `blocks/refs.yaml`

All ID patterns in one place. Each entry defines a reference type.

```yaml
gl:  { pattern: "^GL-\\d{3}-[A-Z][a-zA-Z0-9]*$", title: "Glossary term" }
req: { pattern: "^REQ-\\d{3}$", title: "Functional requirement" }
nfr: { pattern: "^NFR-\\d{3}$", title: "Non-functional requirement" }
sc:  { pattern: "^SC-\\d{3}$", title: "Success criterion" }
us:  { pattern: "^US-\\d{3}$", title: "User story" }
ng:  { pattern: "^NG-\\d{3}$", title: "Non-goal" }
comp:{ pattern: "^COMP-\\d{3}-[A-Za-z][A-Za-z0-9]*$", title: "Component" }
con: { pattern: "^CON-\\d{3}-[A-Za-z][A-Za-z0-9]*$", title: "Constraint" }
fn:  { pattern: "^FN-[a-z][A-Za-z0-9]*$", title: "Function" }
ent: { pattern: "^ENT-\\d{3}-[A-Z][A-Za-z0-9]*$", title: "Entity" }
scr: { pattern: "^SCR-\\d{3}-[A-Z][A-Za-z0-9]*$", title: "Screen" }
tst: { pattern: "^TST-\\d{3}-[A-Z][A-Za-z0-9]*$", title: "Test case" }
ep:  { pattern: "^EP-\\d{3}-[A-Z][A-Za-z0-9]*$", title: "Epic" }
is:  { pattern: "^IS-\\d{3}$", title: "Issue" }
mil: { pattern: "^MIL-\\d{3}-[A-Z][A-Za-z0-9]*$", title: "Milestone" }
flw: { pattern: "^FLW-\\d{3}-[A-Za-z][A-Za-z0-9]*$", title: "Data flow" }
uj:  { pattern: "^UJ-\\d{3}-[a-z][A-Za-z0-9]*$", title: "User journey" }
fc:  { pattern: "^FC-\\d{3}$", title: "Function coverage" }
rel: { pattern: "^REL-\\d{3}-[A-Za-z][A-Za-z0-9]*$", title: "Relationship" }
num: { pattern: "^NUM-\\d{3}-[A-Z][A-Za-z0-9]*$", title: "Enum" }
prim:{ pattern: "^PRIM-\\d{3}-[A-Za-z][A-Za-z0-9]*$", title: "Primitive" }
dg:  { pattern: "^DG-\\d{3}$", title: "Design goal" }
prs: { pattern: "^PRS-\\d{3}-[A-Za-z][A-Za-z0-9]*$", title: "Persona" }
spc: { pattern: "^SPC-\\d{3}$", title: "Screen spec" }
pat: { pattern: "^PAT-\\d{3}-[a-z][A-Za-z0-9]*$", title: "Interaction pattern" }
vdr: { pattern: "^VDR-\\d{3}$", title: "Visual design requirement" }
ar:  { pattern: "^AR-\\d{3}$", title: "Accessibility requirement" }
uxac:{ pattern: "^UXAC-\\d{3}$", title: "UX acceptance criterion" }
dt:  { pattern: "^DT-\\d{3}-[A-Za-z][A-Za-z0-9]*$", title: "Design token" }
FLD: { pattern: "^FLD-\\d{3}-[a-z][A-Za-z0-9]*$", title: "Entity field" }
FUNC:{ pattern: "^FUNC-\\d{3}-[a-z][A-Za-z0-9]*$", title: "Entity method" }
ENDP:{ pattern: "^ENDP-[a-z][A-Za-z0-9]*$", title: "API endpoint" }
```

**Note:** `FN` has been replaced by `ENDP` for API endpoints. `FLD` is for entity fields. `FUNC` is for entity methods.

### `blocks/base.yaml`

```yaml
version:
  type: string
  description: "Semver version of this spec document instance."
  pattern: "^\\d+\\.\\d+\\.\\d+$"

project:
  type: string
  description: "Project name. Must match across all specs."
  minLength: 1

status:
  type: string
  description: "Lifecycle status of this spec."
  enum: [draft, review, confirmed, superseded]
  default: draft

goalSpecVersion:
  type: string
  description: "Version of the GoalSpec this spec was reviewed against."
  pattern: "^v\\d+\\.\\d+\\.\\d+$"
```

---

## Generator Script (`generate_schema.py`)

### CLI

```bash
python generate_schema.py <type>          # Generate one schema
python generate_schema.py --all           # Generate all schemas
python generate_schema.py --dry-run <type> # Show assembled schema without writing
```

### Assembly Algorithm

1. Load proto-schema from `artifact/<type>.yaml`
2. Load `blocks/refs.yaml` and `blocks/base.yaml`
3. Build schema structure:
   - Add `$schema`, `$id`, `title`, `description`
   - Add `type: object`, `additionalProperties: false`
   - Inject base fields (`version`, `project`, `status`, `goalSpecVersion`)
   - Inject `schemaVersion` with artifact's `schemaVersion` as const
   - Inject all ID patterns from `refs.yaml` as `#/definitions/<type>Id`
   - Process each field in `fields` → convert to JSON Schema
4. Output to `specs/<type>.schema.json`

### Field Conversion Logic

```python
def convert_field(field, refs):
    prop = {}

    # Type
    if field["type"] == "object":
        prop["type"] = "object"
        prop["additionalProperties"] = False
        prop["properties"] = {}
        prop["required"] = []
        for sub in field.get("fields", []):
            sub_prop = convert_field(sub, refs)
            prop["properties"][sub["name"]] = sub_prop
            if sub.get("required") or sub["name"] in field.get("required", []):
                prop["required"].append(sub["name"])
        # Auto-inject id/name/description if ref is present
        if "ref" in field:
            _auto_inject_id_name_desc(prop, field["ref"])
    elif field["type"] == "array":
        prop["type"] = "array"
        if "minItems" in field:
            prop["minItems"] = field["minItems"]
        if "of" in field:
            prop["items"] = convert_type(field["of"], refs)
    elif field["type"] == "enum":
        prop["type"] = "string"
        prop["enum"] = field["enum"]
        if "default" in field:
            prop["default"] = field["default"]
    else:
        prop["type"] = field["type"]

    # Ref (cross-reference)
    if "ref" in field:
        ref_name = field["ref"]
        if field.get("type") == "array":
            prop["type"] = "array"
            prop["items"] = {"$ref": f"#/definitions/{ref_name}Id"}
            prop["description"] = f"{refs[ref_name]['title']} IDs."
            if ref_name == "gl":
                prop["uniqueItems"] = True
        else:
            prop["$ref"] = f"#/definitions/{ref_name}Id"
            prop["description"] = refs[ref_name]["title"]

    # String constraints
    if field.get("type") == "string":
        if "minLength" in field:
            prop["minLength"] = field["minLength"]
        if "maxLength" in field:
            prop["maxLength"] = field["maxLength"]

    # Boolean
    if field.get("type") == "boolean":
        if "default" in field:
            prop["default"] = field["default"]

    # Integer
    if field.get("type") == "integer":
        if "minimum" in field:
            prop["minimum"] = field["minimum"]

    # Description
    if "desc" in field:
        prop["description"] = field["desc"]

    return prop
```

---

## Proto-Schema Files to Create

### 1. `artifact/goalspec.yaml`

```yaml
artifact: goalspec
title: GoalSpec
schemaVersion: "4.0.0"
description: "Root artifact capturing the why and what of a project"

fields:
  - name: objective
    type: object
    required: [statement, for, problem]
    fields:
      - name: statement
        type: string
        minLength: 20
      - name: for
        type: string
        minLength: 1
      - name: problem
        type: string
        minLength: 10
      - name: glossaryRefs
        type: array
        ref: gl

  - name: functionalRequirements
    type: array
    minItems: 1
    of:
      type: object
      ref: req
      required: [description, actor]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: description
          type: string
          minLength: 10
        - name: actor
          type: string
          minLength: 1
        - name: status
          type: enum
          enum: [draft, review, confirmed, implemented, deprecated]
          default: draft
        - name: priority
          type: enum
          enum: [P0, P1, P2, P3]
          default: P2
        - name: scRefs
          type: array
          ref: sc
        - name: glossaryRefs
          type: array
          ref: gl
        - name: reqRefs
          type: array
          ref: req
        - name: nfrRefs
          type: array
          ref: nfr

  - name: nonFunctionalRequirements
    type: array
    of:
      type: object
      ref: nfr
      required: [category, scale, meter, must]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: description
          type: string
        - name: category
          type: enum
          enum: [Performance, Reliability, Security, Scalability, Maintainability, Portability]
        - name: scale
          type: string
          minLength: 5
        - name: meter
          type: string
          minLength: 5
        - name: must
          type: string
          minLength: 1
        - name: plan
          type: string
          minLength: 1
        - name: wish
          type: string
          minLength: 1
        - name: glossaryRefs
          type: array
          ref: gl

  - name: userStories
    type: array
    minItems: 1
    of:
      type: object
      ref: us
      required: [actor, capability, outcome, reqRefs]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: actor
          type: string
          minLength: 1
        - name: capability
          type: string
          minLength: 5
        - name: outcome
          type: string
          minLength: 5
        - name: reqRefs
          type: array
          ref: req
        - name: glossaryRefs
          type: array
          ref: gl

  - name: successCriteria
    type: array
    minItems: 1
    of:
      type: object
      ref: sc
      required: [description]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: description
          type: string
          minLength: 10
        - name: refs
          type: object
          fields:
            - name: reqRefs
              type: array
              ref: req
            - name: nfrRefs
              type: array
              ref: nfr
        - name: glossaryRefs
          type: array
          ref: gl

  - name: nonGoals
    type: array
    minItems: 1
    of:
      type: object
      ref: ng
      required: [capability, reason]
      fields:
        - name: capability
          type: string
          minLength: 5
        - name: reason
          type: string
          minLength: 5
        - name: glossaryRefs
          type: array
          ref: gl
```

### 2. `artifact/glossary.yaml`

```yaml
artifact: glossary
title: Glossary
schemaVersion: "2.0.0"
description: "Project vocabulary"

fields:
  - name: terms
    type: array
    minItems: 1
    of:
      type: object
      ref: gl
      required: [definition, category]
      fields:
        - name: definition
          type: string
          minLength: 10
        - name: description
          type: string
          minLength: 10
        - name: examples
          type: array
          of: { type: string, minLength: 1 }
        - name: synonyms
          type: array
          of: { type: string, minLength: 1 }
        - name: relatedTerms
          type: array
          ref: gl
        - name: category
          type: enum
          enum: [domain, technical, security, ui]
```

### 3. `artifact/designspec.yaml`

```yaml
artifact: designspec
title: DesignSpec
schemaVersion: "4.0.0"
description: "User experience, interaction model, and visual design requirements"

fields:
  - name: designGoals
    type: array
    minItems: 1
    of:
      type: object
      ref: dg
      required: [goal]
      fields:
        - name: goal
          type: string
          minLength: 5
        - name: description
          type: string
        - name: rationale
          type: string
        - name: reqRefs
          type: array
          ref: req
        - name: glossaryRefs
          type: array
          ref: gl

  - name: personas
    type: array
    minItems: 1
    of:
      type: object
      ref: prs
      required: [name, role, goals, painPoints, technicalSkillLevel]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: description
          type: string
        - name: role
          type: string
          minLength: 1
        - name: goals
          type: array
          minItems: 1
          of: { type: string, minLength: 3 }
        - name: painPoints
          type: array
          minItems: 1
          of: { type: string, minLength: 3 }
        - name: technicalSkillLevel
          type: enum
          enum: [non-technical, basic, intermediate, advanced, expert]
        - name: glossaryRefs
          type: array
          ref: gl

  - name: userJourneys
    type: array
    minItems: 1
    of:
      type: object
      ref: uj
      required: [name, personaRef, usRefs, startingState, steps, desiredOutcome]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: personaRef
          type: string
          ref: prs
        - name: usRefs
          type: array
          ref: us
        - name: reqRefs
          type: array
          ref: req
        - name: startingState
          type: string
          minLength: 5
        - name: steps
          type: array
          minItems: 2
          of:
            type: object
            required: [actor, action]
            fields:
              - name: actor
                type: enum
                enum: [user, system]
              - name: action
                type: string
                minLength: 3
              - name: screenRef
                type: string
                ref: scr
              - name: glossaryRefs
                type: array
                ref: gl
        - name: desiredOutcome
          type: string
          minLength: 5
        - name: glossaryRefs
          type: array
          ref: gl

  - name: informationArchitecture
    type: object
    required: [root]
    fields:
      - name: root
        type: array
        minItems: 1
        of:
          type: object
          fields:
            - name: name
              type: string
              minLength: 1
            - name: screenRef
              type: string
              ref: scr
            - name: children
              type: array
              of: { $ref: "self" }
          # No ref on iaNode — it's a recursive structure, not an ID'd entity

  - name: screenInventory
    type: array
    minItems: 1
    of:
      type: object
      ref: scr
      required: [name, purpose, primaryActions]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: description
          type: string
        - name: purpose
          type: string
          minLength: 10
        - name: primaryActions
          type: array
          minItems: 1
          of: { type: string, minLength: 2 }
        - name: inputs
          type: array
          of: { type: string }
        - name: outputs
          type: array
          of: { type: string }
        - name: usRefs
          type: array
          ref: us
        - name: reqRefs
          type: array
          ref: req
        - name: glossaryRefs
          type: array
          ref: gl

  - name: screenSpecs
    type: array
    minItems: 1
    of:
      type: object
      ref: spc
      required: [screenRef, layout, components, states]
      fields:
        - name: screenRef
          type: string
          ref: scr
        - name: layout
          type: string
          minLength: 10
        - name: wireframe
          type: string
        - name: components
          type: array
          minItems: 1
          of:
            type: object
            required: [name, purpose]
            fields:
              - name: name
                type: string
                minLength: 1
              - name: purpose
                type: string
                minLength: 5
              - name: designSystemRef
                type: string
              - name: patternRefs
                type: array
                ref: pat
              - name: glossaryRefs
                type: array
                ref: gl
        - name: states
          type: array
          minItems: 1
          of:
            type: object
            required: [name, description]
            fields:
              - name: name
                type: string
                minLength: 1
              - name: description
                type: string
                minLength: 5
        - name: interactions
          type: array
          of:
            type: object
            required: [trigger, response]
            fields:
              - name: trigger
                type: string
                minLength: 3
              - name: response
                type: string
                minLength: 3
              - name: patternRef
                type: string
                ref: pat
        - name: glossaryRefs
          type: array
          ref: gl
        - name: componentRefs
          type: array
          ref: comp

  - name: interactionPatterns
    type: array
    of:
      type: object
      ref: pat
      required: [name, description]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: description
          type: string
          minLength: 10
        - name: examples
          type: array
          of: { type: string }
        - name: keyboardShortcuts
          type: array
          of:
            type: object
            required: [keys, action]
            fields:
              - name: keys
                type: string
              - name: action
                type: string
        - name: usageNotes
          type: string

  - name: visualDesignRequirements
    type: array
    minItems: 1
    of:
      type: object
      ref: vdr
      required: [description]
      fields:
        - name: description
          type: string
          minLength: 10
        - name: rationale
          type: string
        - name: reqRefs
          type: array
          ref: req

  - name: designSystem
    type: object
    required: [components]
    fields:
      - name: baseStyle
        type: string
      - name: components
        type: array
        minItems: 1
        of:
          type: object
          required: [name, purpose]
          fields:
            - name: name
              type: string
              minLength: 1
            - name: purpose
              type: string
              minLength: 5
            - name: variants
              type: array
              of: { type: string }
            - name: usageNotes
              type: string

  - name: accessibilityRequirements
    type: array
    minItems: 1
    of:
      type: object
      ref: ar
      required: [description]
      fields:
        - name: description
          type: string
          minLength: 10
        - name: rationale
          type: string
        - name: reqRefs
          type: array
          ref: req

  - name: uxAcceptanceCriteria
    type: array
    minItems: 1
    of:
      type: object
      ref: uxac
      required: [description]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: description
          type: string
          minLength: 10
        - name: refs
          type: object
          fields:
            - name: usRefs
              type: array
              ref: us
            - name: reqRefs
              type: array
              ref: req
        - name: verificationMethod
          type: string

  - name: designTokens
    type: array
    of:
      type: object
      ref: dt
      required: [name, category, value]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: category
          type: enum
          enum: [color, typography, spacing, border-radius, shadow, opacity, z-index]
        - name: value
          type: string
        - name: description
          type: string
          minLength: 10
        - name: glossaryRefs
          type: array
          ref: gl
```

### 4. `artifact/archspec.yaml`

```yaml
artifact: archspec
title: ArchitectureSpec
schemaVersion: "2.0.0"
description: "Structural specification of the system: components, responsibilities, data flow, and constraints"

fields:
  - name: overview
    type: object
    required: [summary, subsystems]
    fields:
      - name: summary
        type: string
        minLength: 30
      - name: subsystems
        type: array
        minItems: 1
        of:
          type: object
          required: [name, purpose]
          fields:
            - name: name
              type: string
              minLength: 1
            - name: purpose
              type: string
              minLength: 5
            - name: componentRefs
              type: array
              ref: comp
      - name: glossaryRefs
        type: array
        ref: gl

  - name: components
    type: array
    minItems: 1
    of:
      type: object
      ref: comp
      required: [purpose, responsibilities]
      fields:
        - name: purpose
          type: string
          minLength: 10
        - name: description
          type: string
        - name: responsibilities
          type: array
          minItems: 1
          of: { type: string, minLength: 5 }
        - name: dependencies
          type: array
          ref: comp
        - name: reqRefs
          type: array
          ref: req
        - name: nfrRefs
          type: array
          ref: nfr
        - name: visibility
          type: enum
          enum: [external, internal]
          default: internal
        - name: glossaryRefs
          type: array
          ref: gl
        - name: notes
          type: string
        - name: status
          type: enum
          enum: [draft, review, confirmed, implemented, deprecated]
        - name: constraintRefs
          type: array
          ref: con

  - name: dataModel
    type: object
    required: [dataSpecRef]
    fields:
      - name: dataSpecRef
        type: string
        minLength: 1
      - name: notes
        type: string

  - name: apiContract
    type: object
    fields:
      - name: apiSpecRef
        type: string
        minLength: 1
      - name: authStrategy
        type: string
        minLength: 10
      - name: notes
        type: string

  - name: dataFlow
    type: array
    minItems: 1
    of:
      type: object
      ref: flw
      required: [name, steps]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: description
          type: string
        - name: glossaryRefs
          type: array
          ref: gl
        - name: reqRefs
          type: array
          ref: req
        - name: steps
          type: array
          minItems: 2
          of:
            type: object
            required: [componentRef, action]
            fields:
              - name: componentRef
                type: string
                ref: comp
              - name: action
                type: string
                minLength: 5
              - name: dataRef
                type: string
              - name: notes
                type: string
        - name: nfrRefs
          type: array
          ref: nfr
        - name: componentRefs
          type: array
          ref: comp

  - name: constraints
    type: array
    minItems: 1
    of:
      type: object
      ref: con
      required: [description]
      fields:
        - name: description
          type: string
          minLength: 10
        - name: rationale
          type: string
        - name: glossaryRefs
          type: array
          ref: gl
        - name: nfrRefs
          type: array
          ref: nfr
        - name: reqRefs
          type: array
          ref: req
```

### 5. `artifact/dataspec.yaml`

```yaml
artifact: dataspec
title: DataSpec
schemaVersion: "1.0.0"
description: "Structural specification of all entities, types, and relationships"

fields:
  - name: primitives
    type: array
    minItems: 1
    of:
      type: object
      ref: prim

  - name: enums
    type: array
    of:
      type: object
      ref: num
      required: [values]
      fields:
        - name: description
          type: string
        - name: values
          type: array
          minItems: 1
          of:
            type: object
            required: [name]
            fields:
              - name: name
                type: string
              - name: description
                type: string

  - name: entities
    type: array
    minItems: 1
    of:
      type: object
      ref: ent
      required: [fields]
      fields:
        - name: description
          type: string
        - name: abstract
          type: boolean
          default: false
        - name: extends
          type: string
        - name: fields
          type: array
          minItems: 1
          of:
            type: object
            ref: FLD
            required: [name, type]
            fields:
              - name: type
                type: string
              - name: required
                type: boolean
                default: true
              - name: description
                type: string
              - name: example
                type: any
              - name: primaryKey
                type: boolean
                default: false
        - name: methods
          type: array
          of:
            type: object
            ref: FUNC
            required: [name, apiRef]
            fields:
              - name: name
                type: string
              - name: apiRef
                type: string
                ref: ENDP
              - name: description
                type: string
        - name: visibility
          type: enum
          enum: [public, internal]
          default: public
        - name: componentRefs
          type: array
          ref: comp
        - name: reqRefs
          type: array
          ref: req
        - name: nfrRefs
          type: array
          ref: nfr
        - name: constraintRefs
          type: array
          ref: con

  - name: relationships
    type: array
    minItems: 1
    of:
      type: object
      ref: rel
      required: [from, to, type]
      fields:
        - name: from
          type: string
        - name: to
          type: string
        - name: type
          type: enum
          enum: [association, composition, aggregation, dependency, realization]
        - name: cardinality
          type: object
          fields:
            - name: fromLabel
              type: enum
              enum: ["1", "0..1", "1..*", "*", "0..*"]
            - name: toLabel
              type: enum
              enum: ["1", "0..1", "1..*", "*", "0..*"]
        - name: label
          type: string
        - name: description
          type: string
        - name: reqRefs
          type: array
          ref: req
```

### 6. `artifact/apispec.yaml`

```yaml
artifact: apispec
title: ApiSpec
schemaVersion: "2.0.0"
description: "Interface specification for all functions exposed by a module"

fields:
  - name: functions
    type: array
    minItems: 1
    of:
      type: object
      ref: ENDP
      required: [name, inputs, output]
      fields:
        - name: name
          type: string
        - name: description
          type: string
        - name: entity
          type: string
        - name: inputs
          type: array
          of:
            type: object
            required: [name, type]
            fields:
              - name: name
                type: string
              - name: type
                type: string
              - name: required
                type: boolean
                default: true
              - name: description
                type: string
              - name: example
                type: any
        - name: output
          type: object
          required: [type]
          fields:
            - name: type
              type: string
            - name: description
              type: string
            - name: example
              type: any
            - name: name
              type: string
        - name: errors
          type: array
          of:
            type: object
            required: [code, condition]
            fields:
              - name: code
                type: string
                pattern: "^[A-Z][A-Z0-9_]*$"
              - name: condition
                type: string
              - name: returnType
                type: string
        - name: visibility
          type: enum
          enum: [public, internal]
          default: public
        - name: pure
          type: boolean
          default: false
        - name: tags
          type: array
          of: { type: string }
        - name: status
          type: enum
          enum: [draft, review, confirmed, implemented, deprecated]
          default: draft
        - name: priority
          type: enum
          enum: [P0, P1, P2, P3]
          default: P2
        - name: reqRefs
          type: array
          ref: req
        - name: nfrRefs
          type: array
          ref: nfr
        - name: screenRefs
          type: array
          ref: scr
        - name: ujRefs
          type: array
          ref: uj
        - name: componentRefs
          type: array
          ref: comp
        - name: constraintRefs
          type: array
          ref: con
```

### 7. `artifact/testspec.yaml`

```yaml
artifact: testspec
title: TestSpec
schemaVersion: "3.0.0"
description: "Test specification for all API functions"

fields:
  - name: functionCoverage
    type: array
    minItems: 1
    of:
      type: object
      ref: fc
      required: [fnRef, happyPathCount, edgeCaseCount, errorPathCount, outOfScope]
      fields:
        - name: fnRef
          type: string
          ref: ENDP
        - name: happyPathCount
          type: integer
          minimum: 0
        - name: edgeCaseCount
          type: integer
          minimum: 0
        - name: errorPathCount
          type: integer
          minimum: 0
        - name: outOfScope
          type: array
          minItems: 1
          of:
            type: object
            required: [description]
            fields:
              - name: description
                type: string
                minLength: 1
        - name: reqRefs
          type: array
          ref: req

  - name: tests
    type: array
    minItems: 1
    of:
      type: object
      ref: tst
      required: [fnRef, category, description, input, contractClause]
      fields:
        - name: name
          type: string
          minLength: 1
        - name: fnRef
          type: string
          ref: ENDP
        - name: category
          type: enum
          enum: [happy-path, edge-case, error-path]
        - name: description
          type: string
          minLength: 5
        - name: input
          type: object
        - name: expectedOutput
          type: any
        - name: expectedOutputType
          type: string
        - name: contractClause
          type: string
          minLength: 5
        - name: reqRefs
          type: array
          ref: req
        - name: errorCode
          type: string
        - name: expectedError
          type: object
          fields:
            - name: code
              type: string
            - name: returnType
              type: string
            - name: messageContains
              type: string
        - name: scRefs
          type: array
          ref: sc
        - name: nfrRefs
          type: array
          ref: nfr
        - name: entityRefs
          type: array
          ref: ent
        - name: constraintRefs
          type: array
          ref: con
        - name: usRefs
          type: array
          ref: us
        - name: ujRefs
          type: array
          ref: uj
        - name: screenRefs
          type: array
          ref: scr
```

### 8. `artifact/taskplan.yaml`

```yaml
artifact: taskplan
title: TaskPlan
schemaVersion: "1.0.0"
description: "Sequenced set of epics and milestones"

fields:
  - name: milestones
    type: array
    minItems: 1
    of:
      type: object
      ref: mil
      required: [name, outcome, epics]
      fields:
        - name: name
          type: string
          minLength: 5
        - name: outcome
          type: string
          minLength: 10
        - name: epics
          type: array
          minItems: 1
          of: { ref: ep }

  - name: epics
    type: array
    minItems: 1
    of:
      type: object
      ref: ep
      required: [title, milestone, requirements, summary]
      fields:
        - name: title
          type: string
          minLength: 5
        - name: milestone
          type: string
          ref: mil
        - name: requirements
          type: array
          minItems: 1
          of: { ref: req }
        - name: summary
          type: string
          minLength: 10
        - name: objective
          type: string
        - name: scope
          type: object
          fields:
            - name: inScope
              type: array
              minItems: 1
              of: { type: string, minLength: 5 }
            - name: outOfScope
              type: array
              minItems: 1
              of: { type: string, minLength: 5 }
        - name: acceptanceCriteria
          type: array
          minItems: 1
          of: { type: string, minLength: 10 }
        - name: specDependencies
          type: object
          fields:
            - name: blockedBy
              type: array
              of: { ref: ep }
            - name: blocks
              type: array
              of: { ref: ep }
        - name: notes
          type: string
        - name: filePath
          type: string
        - name: designRefs
          type: array
          of: { type: string }
        - name: archRefs
          type: array
          of: { type: string }
```

### 9. `artifact/issue.yaml`

```yaml
artifact: issue
title: Issue
schemaVersion: "1.0.0"
description: "A single vertical slice decomposed from an Epic"

fields:
  - name: id
    type: string
    ref: is
  - name: title
    type: string
    minLength: 5
    maxLength: 120
  - name: type
    type: enum
    enum: [AFK, HITL]
  - name: status
    type: enum
    enum: [not_started, in_progress, needs_review, complete]
  - name: epic
    type: string
    ref: ep
  - name: blocked_by
    type: array
    of: { ref: is }
  - name: milestone
    type: string
    ref: mil
  - name: inScope
    type: array
    of:
      type: object
      required: [description]
      fields:
        - name: description
          type: string
          minLength: 1
        - name: glossaryRefs
          type: array
          ref: gl
  - name: outOfScope
    type: array
    of:
      type: object
      required: [description]
      fields:
        - name: description
          type: string
          minLength: 1
        - name: glossaryRefs
          type: array
          ref: gl
  - name: acceptanceCriteria
    type: array
    of:
      type: object
      required: [description]
      fields:
        - name: description
          type: string
          minLength: 1
        - name: glossaryRefs
          type: array
          ref: gl
```

---

## Files to Modify

### `extensions/blueprint/tools/load-artifact.ts`

Update schema paths from current location to `specs/`:
- Change `def.schema` references to point to `skills/blueprint/schemas/specs/<type>.schema.json`

### `extensions/blueprint/linters/id_patterns.py`

Add new patterns:
```python
ID_PATTERNS = {
    ...
    "FLD":  { "pattern": "^FLD-\\d{3}-[a-z][A-Za-z0-9]*$", "description": "Entity field" },
    "FUNC": { "pattern": "^FUNC-\\d{3}-[a-z][A-Za-z0-9]*$", "description": "Entity method" },
    "ENDP": { "pattern": "^ENDP-[a-z][A-Za-z0-9]*$", "description": "API endpoint" },
}
```

### `extensions/blueprint/linters/lint_schemas.py`

No changes needed — it already handles `x_idPattern` resolution from `ID_PATTERNS`.

### `extensions/blueprint/linters/linter_types.py`

Update any type mappings that reference `FN` → `ENDP`.

### `skills/blueprint/schemas/suite.json`

Update paths:
```json
{
  "schemas": ".",
  "linters": "../../../../extensions/blueprint/linters",
  "specs": {
    "goal":     "example.goalspec.json",
    "design":   "example.designspec.json",
    ...
  }
}
```

### `skills/blueprint/instructions/*.md`

Update any references to schema file paths if they contain hardcoded paths.

---

## Validation Steps

1. **Generate all schemas:** `python generate_schema.py --all`
2. **Compare with existing:** `diff -r specs/ ../skills/blueprint/schemas/*.schema.json`
3. **Run lint:** `python extensions/blueprint/linters/lint_all.py`
4. **Regenerate Markdown:** For each artifact, run `generate_artifact_markdown` and compare with existing `.md` files
5. **Update examples:** Regenerate example JSON files to match new schema structure
6. **Full integration test:** Run the blueprint skill end-to-end with the new schemas

---

## Migration Strategy

**Option A: Parallel (safer)**
1. Generate new schemas alongside old ones
2. Update tooling to read from `specs/` (new location)
3. Keep old `*.schema.json` files until migration is verified
4. Delete old files after validation

**Option B: In-place (faster)**
1. Generate new schemas to `specs/`
2. Move `specs/*.schema.json` → `skills/blueprint/schemas/*.schema.json` (overwrite)
3. Update tooling paths
4. Run full validation suite

---

## Edge Cases to Handle

1. **Recursive types** (informationArchitecture `children` → self): Use `of: { $ref: "self" }`
2. **Named type references**: Use `of: { $ref: "typeName" }` to reference types defined in the same artifact
3. **Empty required arrays**: Omit `required` entirely if nothing is required beyond id/name/description
4. **`type: any`**: Maps to JSON Schema `["string", "number", "boolean", "object", "array"]`
5. **Nested enums**: `type: enum` with `enum: [a, b]` at any level
6. **`pattern` on non-ref fields**: Patterns are banned from proto-schema. If a field needs a custom pattern (like `filePath`), add a new ref to `refs.yaml` or handle it as a special case in the generator.
