---

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

---

---

## Clarification Phase

**⚠ DO NOT create a data model immediately.** Before proposing any entities,
relationships, or fields, go through a structured clarification process.
A data model built on unverified assumptions will cascade errors into ApiSpec
and TestSpec.

1. **List assumptions** — Load `ArchitectureSpec.json` and `GoalSpec.json`.
   Extract component names (potential entities), domain nouns from
   requirements, and implied relationships. Present them to the user for
   validation: confirm, correct, or add.

2. **Clarify ambiguous terms** — When the user uses different terms that
   might refer to the same concept (e.g., "user" vs "customer"), ask
   explicitly. Do not assume.

3. **Clarify cardinality** — For every relationship, ask about cardinality:
   `1→1`, `1→0..1`, `1→*`, or `*→*`. For many-to-many, ask whether to
   create an association entity and what fields it should have.

4. **Enum vs entity** — For each enumerated type, ask whether it should be
   an enum (simple values) or an entity (methods, relationships). Default
   to enum.

5. **Field details** — For each entity, confirm: required fields, primary key
   (default: first field or field ending with `Id`), and example values.

6. **Relationship labels** — For every relationship, ask the user for a
   meaningful verb label (e.g., "places", "contains", "belongs to").

7. **Final validation** — Summarize all decisions (entities, relationships,
   enums) and ask the user to confirm before proceeding.

---

## Before the interview

Load `artifacts/ArchitectureSpec.json`. Extract component names — these are
candidates for entities. Also load `artifacts/GoalSpec.json` and note the
domain nouns in functional requirements. Use these as a starting point for the
clarification process described above. **Never propose a final data model without
first completing the clarification phase.**

---

### Primitives

The set of primitive type definitions used as field types.

Each primitive must have:

Defaults: `string`, `number`, `boolean`, `null`, `any`.

Additional primitives may be added for the project (e.g. `Date`, `UUID`).

Every field type must resolve to a primitive, an entity name, or an enum name
defined in this spec.

---

### Enums

Enumerated types used across entities and API contracts.

Each enum must have:
* **Description** (optional)
  * **Description** (optional)

**Rules:**

* No duplicate enum names.
* Each enum must have at least one value.
* Enums with only one value should be questioned — may be better as a boolean.

---

### Entities

All domain entities (classes) in the system.

Each entity must have:
* **glossaryRefs** (array of GL-NNN): Glossary terms the entity maps to. The entity name itself should have a corresponding glossary entry.
    (e.g. `string`, `User`, `OrderStatus`, `OrderItem[]`)
  * **Description** (optional)
    Only one field per entity should be marked. If not set, the first field
    or a field ending with `Id`/`id` is assumed to be the primary key.
    **Required:** must contain `id` in its name (e.g. `id`, `userId`, `orderId`).
  * **glossaryRefs** (array of GL-NNN): Domain concepts in the field's description
  reference a function ID in ApiSpec via `apiRef`.

**Rules:**

* No duplicate entity names.
* Every field type must resolve to a defined primitive, entity, or enum.
* If a field has an entity type, a relationship must exist between them.
* Every `extends` reference must name a real entity in this spec.
* `abstract` entities should not have composition/aggregation relationships as targets (they are base classes, not leaf types).

**Inheritance (`extends`):**

When an entity extends another, the diagram generator will render a UML
inheritance arrow (`--|>` in PlantUML, `<|--` in Mermaid).

**Abstract entities** cannot be instantiated directly — they exist only as
base classes. Use when multiple entities share common fields or you have a
clear "is-a" hierarchy. Abstract entities should NOT be targets of
composition/aggregation relationships.

---

### Relationships

Directional relationships between entities.

Each relationship must have:
  * `association` — general link
  * `composition` — target cannot exist without source
  * `aggregation` — target can exist independently
  * `dependency` — source uses target but does not own it
  * `realization` — source implements target interface

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

DataSpec is the **source of truth** for all types used across ApiSpec and
TestSpec. When a type changes in DataSpec, run the linter to identify all
affected references and update ApiSpec/TestSpec accordingly.

**Rules:**

* Type names must match exactly (e.g., `User` not `user` or `Users`).
* Primitives must match JSON Schema casing (`string` not `String`).
* Always run the full lint suite after type changes.

#### Relationship Notation

Use the **deletion test** (see Relationships section) to determine type.
For visual notation conventions:

| Relationship | Smell | Notation |
|---|---|---|
| Association | "uses / knows" | Solid line + open arrow (→) |
| Inheritance | "is a" | Solid line + open triangle (▷) |
| Aggregation | "has a (weak)" | Open diamond on whole side (◇—) |
| Composition | "owns (strong)" | Filled diamond on whole side (◆—) |
| Dependency | "needs temporarily" | Dashed line + open arrow (- - →) |


