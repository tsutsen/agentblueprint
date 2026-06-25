---
name: Glossary
type: schema
version: 2.0.0
---

## Glossary

Defines project vocabulary. Every domain term used in any spec must have
an entry here. This document is the single source of truth for terminology
across the entire project.

---

---

## Before the interview

Load `artifacts/GoalSpec.json`. Extract all actor names from functional
requirements and user stories. These actors are the first terms to define.

Then scan GoalSpec for domain nouns that appear repeatedly — these are
candidates for glossary entries. Propose them to the user rather than
asking them to enumerate terms from scratch.

---

### Terms

Defines project vocabulary.

Each term must include:
  in its own definition. Must be at least one full sentence.
  Synonyms must NOT have their own glossary entry.
  that are closely related. Must reference terms that exist.

**Description Rules:**

  Start with what the term IS (e.g., "A structured piece of information..." not "Related to
  extraction, this is...").
  term B is described using term A (direct or transitive).
* **Synonyms must not also have independent entries.**
* **Every term referenced as a `relatedTerm` must exist in this glossary.**
* **Actor names from GoalSpec must have entries.**
* **Entity names from DataSpec (when it exists) should have entries.**
* **Component names from ArchSpec (when it exists) should have entries.**
* **UI screen names from DesignSpec (when it exists) should have entries.**

**Category Definitions:**

* `domain` — Research concepts, entities, and relationships (papers, sources, queries, concepts, findings).
* `technical` — System components, data models, engines, interfaces, data types.
* `security` — Authentication, authorization, access control.
* `ui` — Screen, interface, and presentation terms (panels, dashboards, dialogs).


