---
name: DataSpec
type: schema
version: 1.0.0
---

## Data Spec

Defines the logical data model of the system: all entities, their fields,
enumerated types, and the relationships between them.

DataSpec is the source of truth for types used across ApiSpec and TestSpec.
It produces a machine-readable JSON artifact and a deterministically
generated PlantUML class diagram.

The DataSpec does NOT define:

* Function signatures or API contracts — those belong to **ApiSpec**
* Database schemas, table definitions, or ORM models — those are implementation
* Any UI or screen structure — that belongs to **DesignSpec**

---

## Output Format

This artifact produces two files:

- `artifacts/DataSpec.md` — human-readable document
- `artifacts/DataSpec.json` — machine-readable, conforming to `schemas/dataspec.schema.json`

### Diagram Generation

After finalizing the DataSpec JSON, regenerate all diagrams by calling the
`generate_diagrams` tool:

```
tool: generate_diagrams
args:
  dataSpecPath: artifacts/Data.json
  formats: all
  outputDir: diagrams
```

This produces:
- `diagrams/plantuml_data_diagram.puml` — PlantUML class diagram
- `diagrams/mermaid_data_diagram.md` — Mermaid class diagram (embeds in Markdown)
- `diagrams/drawio_data_diagram.drawio` — draw.io XML (import at app.diagrams.net)
- `diagrams/dbml_data_diagram.dbml` — DBML (import at dbdiagram.io)
- `diagrams/d2_data_diagram.d2` — D2 diagram (render with `d2 Data.d2`)

**Regenerate after every DataSpec change.** Diagrams are derived artifacts
and must always match the JSON source of truth.

---

## Inputs

* GoalSpec (`artifacts/GoalSpec.json`) — required
* ArchitectureSpec (`artifacts/ArchitectureSpec.json`) — required

---

## Clarification Phase

**⚠ DO NOT create a data model immediately.** Before proposing any entities,
relationships, or fields, you MUST go through a structured clarification process.
A data model built on unverified assumptions will cascade errors into ApiSpec
and TestSpec.

### Step 1: List All Assumptions

Load `artifacts/ArchitectureSpec.json` and `artifacts/GoalSpec.json`. Extract:
- Component names from ArchitectureSpec (potential entities)
- Domain nouns from functional requirements in GoalSpec
- Any relationships implied by the architecture

**Then ask the user to validate every assumption:**

```
Based on the architecture and requirements, I have the following assumptions
about the data model. Please confirm, correct, or add:

1. Entities: [list each entity with a one-line description]
   - Is this entity correct? Should it be renamed? Should any be added/removed?
2. Domain terms: [list terms like "user" vs "customer"]
   - Do these refer to the same entity or different ones?
3. Relationships: [list implied relationships]
   - Are these correct? Are any missing?
```

### Step 2: Clarify Ambiguous Terms

When the user uses different terms that might refer to the same concept
(e.g., "user" in one requirement, "customer" in another), **explicitly ask**:

```
"You mentioned 'user' in [requirement X] and 'customer' in [requirement Y].
Are these the same entity, or are they different?"
```

Do not assume they are the same. Do not assume they are different. Ask.

### Step 3: Clarify Relationship Cardinality

For every relationship between entities, **ask the user about cardinality**:

```
Relationship: [EntityA] → [EntityB]

Cardinality options:
- 1 → 1: Each A has exactly one B, each B has exactly one A
- 1 → 0..1: Each A has zero or one B
- 1 → *: Each A has zero or more B's, each B belongs to exactly one A
- * → *: Many-to-many (requires an association entity)

Which applies here?"
```

### Step 4: Clarify Many-to-Many Relationships

When the user describes a many-to-many relationship (e.g., "Orders have many
Products" and "Products appear in many Orders"), **explicitly ask**:

```
"[EntityA] and [EntityB] have a many-to-many relationship. This requires an
association entity (e.g., 'OrderItem' for Order ↔ Product). Should I create
one? What fields should it have?"
```

### Step 5: Clarify Enum vs Entity Decisions

For each enumerated type, **ask the user**:

```
"[Type] has values: [list values]. Should this be:
- An enum (simple list of values, no methods)?
- An entity (has methods, relationships, or complex behavior)?"
```

**Default to enum** unless the user indicates the type needs methods,
relationships, or complex behavior.

### Step 6: Clarify Field-Level Details

For each entity, **ask the user**:

```
Entity: [EntityName]

Fields:
- [FieldName] ([Type]): [description]
  - Is this field required? (default: yes)
  - What is the primary key? (default: first field or field ending with 'Id')
  - Can you give an example value?"
```

### Step 7: Clarify Relationship Labels

For every relationship, **ask the user for a meaningful label**:

```
Relationship: [EntityA] → [EntityB]

What verb describes this relationship? (e.g., 'places', 'contains', 'belongs to')
This becomes the label on the relationship arrow."
```

### Step 8: Final Validation

Before proceeding to create the data model, **summarize all decisions** and
ask the user to confirm:

```
Here is the complete data model summary. Please confirm:

Entities: [list with key fields]
Relationships: [list with type, cardinality, label]
Enums: [list with values]

Any changes before I finalize?"
```

---

## Before the interview

Load `artifacts/ArchitectureSpec.json`. Extract component names — these are
candidates for entities. Also load `artifacts/GoalSpec.json` and note the
domain nouns in functional requirements. Use these as a starting point for the
clarification process described above. **Never propose a final data model without
first completing the clarification phase.**

---

### Primitives

The set of primitive type names used as field types.

Defaults: `string`, `number`, `boolean`, `null`, `any`.

Additional primitives may be added for the project (e.g. `Date`, `UUID`).

Every field type must resolve to a primitive, an entity name, or an enum name
defined in this spec.

---

### Enums

Enumerated types used across entities and API contracts.

Each enum must have:

* **Name** — PascalCase, e.g. `OrderStatus`
* **Description** (optional)
* **Values** — each with:
  * **Name** — SCREAMING_SNAKE_CASE, e.g. `PENDING`
  * **Description** (optional)

**Rules:**

* No duplicate enum names.
* Each enum must have at least one value.
* Enums with only one value should be questioned — may be better as a boolean.

---

### Entities

All domain entities (classes) in the system.

Each entity must have:

* **Name** — PascalCase, unique, e.g. `User`, `OrderItem`
* **Description** — what this entity represents in the domain
* **Fields** — each with:
  * **Name** — camelCase, e.g. `createdAt`, `userId`
  * **Type** — a primitive, entity name, enum name, or array thereof
    (e.g. `string`, `User`, `OrderStatus`, `OrderItem[]`)
  * **Required** — boolean, default true
  * **Description** (optional)
  * **Example** (optional) — a concrete example value
  * **primaryKey** (optional) — true if this field is the primary key.
    Only one field per entity should be marked. If not set, the first field
    or a field ending with `Id`/`id` is assumed to be the primary key.
    **Required:** must contain `id` in its name (e.g. `id`, `userId`, `orderId`).
* **Methods** (optional) — functions this entity exposes. Each method must
  reference a function ID in ApiSpec via `apiRef`.
* **Abstract** (optional) — true if this entity cannot be instantiated directly
* **Extends** (optional) — parent entity name for inheritance
* **Visibility** — `public` or `internal`

**Rules:**

* No duplicate entity names.
* Every field type must resolve to a defined primitive, entity, or enum.
* If a field has an entity type, a relationship must exist between them.
* Every `extends` reference must name a real entity in this spec.
* `abstract` entities should not have composition/aggregation relationships as targets (they are base classes, not leaf types).
* **Every entity must have a primary key field** — the first field, or a field ending with `Id`/`id`, must contain `id` in its name (e.g. `id`, `userId`, `orderId`). This is required for diagram generators and DBML output.

**Inheritance (`extends`):**

When an entity extends another, the diagram generator will render a
UML inheritance arrow (`--|>` in PlantUML, `<|--` in Mermaid, `--|>` in D2).
The parent entity will also be rendered in the same visibility group.

**Abstract entities:**

An `abstract` entity cannot be instantiated directly — it exists only as
a base class for other entities. Use abstract entities when:

* Multiple entities share common fields (e.g., `AuditEntity` with `createdAt`, `updatedAt`)
* You have a clear "is-a" hierarchy (e.g., `Payment` → `CreditCardPayment`, `BankTransferPayment`)
* You want to enforce that only subclasses are used in relationships

**Rules for abstract entities:**

* Abstract entities should NOT have composition/aggregation relationships as targets
  (they are base classes, not leaf types that can be "owned").
* Abstract entities SHOULD have association/dependency relationships (they can reference other types).
* All concrete (non-abstract) entities that extend an abstract entity must be listed explicitly.
* When a field references an abstract entity type, it means the field can be any of the
  concrete subclasses (e.g., `payment: Payment` where `Payment` is abstract and has
  `CreditCardPayment` and `BankTransferPayment` as subclasses).

**Ask the user:**

```
"[Entity] is marked as abstract. Is this correct? Are there concrete
subclasses that should be listed?"
```

---

### Relationships

Directional relationships between entities.

Each relationship must have:

* **From** — source entity name
* **To** — target entity name
* **Type** — one of:
  * `association` — general link
  * `composition` — target cannot exist without source
  * `aggregation` — target can exist independently
  * `dependency` — source uses target but does not own it
  * `realization` — source implements target interface
* **Cardinality** (optional) — labels on each end, e.g. `1` to `0..*`
* **Label** (optional) — verb on the arrow, e.g. `places`, `contains`

**Rules:**

* Both `from` and `to` must name real entities in this spec.
* No orphan entities — every entity must appear in at least one relationship
  (except in single-entity specs).
* No duplicate relationships of the same type between the same pair.

#### Choosing the relationship type — the deletion test

When deciding which relationship type to assign, ask:

> **"If entity X (the source) is deleted, what happens to the target entity?"**

| Answer | Relationship Type |
|---|---|
| The target is destroyed along with X | `composition` |
| The target survives independently (shared ownership) | `aggregation` |
| The target is unaffected (independent existence) | `association` |
| X only used the target temporarily (no stored reference) | `dependency` |

**This question is more reliable than keyword matching.** Keywords are
surface-level signals that LLMs can pattern-match incorrectly. The deletion
test forces reasoning about actual ownership semantics.

**Examples:**

* `Order` → `OrderItem` as `composition`: when an order is deleted, its items
  cease to exist (they belong to that specific order).
* `Department` → `Employee` as `aggregation`: when a department is deleted,
  employees still exist (they may be reassigned to another department).
* `Report` → `Author` as `association`: when a report is deleted, the author
  still exists independently.
* `UserService` → `Database` as `dependency`: the service uses the database
  during method execution but doesn't own it.

---

### Cross-Spec Consistency

The DataSpec is the **source of truth** for all types used across ApiSpec
and TestSpec. Changes to DataSpec types must be reflected in all dependent
specs.

**Rules:**

* **Entity names must match exactly** — case-sensitive, no variations
  (e.g., if DataSpec has `User`, ApiSpec must use `User`, not `user` or `Users`).
* **Enum names must match exactly** — same case-sensitivity rule.
* **Primitive names must match exactly** — use the primitives defined in
  DataSpec (e.g., `string` not `String`, `number` not `Number`).
* **Array notation must be consistent** — use `Type[]` notation everywhere.
* **When a type changes in DataSpec, check all dependent specs** —
  ApiSpec, TestSpec, and any other spec that references the type.

**Type change workflow:**

1. Make the change in DataSpec.
2. Run the linter to identify all affected references.
3. Update ApiSpec function signatures and parameter types.
4. Update TestSpec test cases that reference the changed types.
5. Regenerate all diagrams.
6. Run the full lint suite to verify consistency.

**Ask the user:**

```
"This type change affects [N] references across [M] specs. Should I
update all of them, or should some references be kept for backward
compatibility?"
```

#### Relationship Notation

When defining relationships between entities, use the following conventions:

| Relationship | Smell | Notation | Key Rule | Keywords |
|---|---|---|---|---|
| Association | "uses / knows" | Solid line + open arrow (→) | Both exist independently. A holds a reference to B. Weakest structural link. | uses, knows about, communicates with, linked to, talks to, references, points to, maintains a reference to, holds a reference to, interacts with, delegates to, notifies, subscribes to, observes, publishes to, queries, retrieves from, is associated with |
| Inheritance | "is a" | Solid line + open triangle (▷) | Child IS-A Parent. Child extends or specializes the parent class. | is a, extends, inherits from, specializes, is a type / kind of, is a subtype of, is a subclass of, is a variant of, is a form of, is a specific type of, is a derived class of, is a specialization of |
| Aggregation | "has a (weak)" | Open diamond on whole side (◇—) | Part can exist without the Whole. Whole "has" the Part. Shared ownership. | has, contains, consists of, is part of, belongs to, includes, comprises, groups, collects, maintains a list of, maintains a set of, maintains a collection of, is an element of |
| Composition | "owns (strong)" | Filled diamond on whole side (◆—) | Part CANNOT exist without the Whole. Whole creates and destroys the Part. | owns, is composed of, manages, controls, is responsible for, creates and owns, destroys, manages the lifecycle of, is the lifecycle owner of, instantiates, is the aggregate root of, is the parent of, is the container of, is responsible for creation and destruction, is a part of |
| Dependency | "needs temporarily" | Dashed line + open arrow (- - →) | A uses B only momentarily (e.g. method param, local var). No stored reference. | depends on, calls, uses temporarily, creates locally, imports, receives as parameter, receives as argument, uses as local variable, references as parameter, references as argument, uses as a local variable, references as a local variable, instantiates locally, invokes, throws, catches |


