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
* **ID** — format `GL-NNN`, e.g. `GL-001`
* **Name** — exactly as it appears in other specs. Case-sensitive.
* **Description** — precise and unambiguous. Must not use the term itself
  in its own definition. Must be at least one full sentence.
* **Examples** (optional) — concrete instances that clarify the definition.
* **Synonyms** (optional) — other names for this term used in the project.
  Synonyms must NOT have their own glossary entry.
* **Related Terms** (optional) — GL-NNN identifiers of other terms in this glossary
  that are closely related. Must reference terms that exist.
* **Category** (optional) — one of: `domain`, `technical`, `security`, `ui`.
* **reqRefs** (optional) — REQ-NNN-slug IDs from GoalSpec that reference this term.
* **fnRefs** (optional) — FN-NNN-slug IDs from ApiSpec that use this term.

**Description Rules:**

* **No self-reference** — the term must not appear in its own description.
* **No file paths or schema names** — describe the concept abstractly, not by file reference.
* **No "related to" / "refers to" starters** — these belong in the `relatedTerms` field.
  Start with what the term IS (e.g., "A structured piece of information..." not "Related to
  extraction, this is...").
* **At least one full sentence** — aim for 8-50 words.
* **No circular descriptions** — term A must not be described using term B if
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

---

## Output

After the interview is complete and the JSON artifact has been written via
`write_section`, the Markdown file must be regenerated from the JSON to
ensure zero drift between formats.

```
tool: generate_artifact_markdown
args:
  artifactType: glossary
  jsonPath: artifacts/Glossary.json
```

This overwrites the Markdown file with content derived from the JSON.
The JSON is the single source of truth; the Markdown is derived.

---

## Linting

After producing `artifacts/Glossary.json`, run:

```
python extensions/blueprint/linters/lint_glossary.py artifacts/Glossary.json \
  --schema schemas/glossary.schema.json \
  --goal   artifacts/GoalSpec.json \
  --arch   artifacts/ArchitectureSpec.json \
  --data   artifacts/DataSpec.json \
  --api    artifacts/ApiSpec.json \
  --json
```

Skip any `--flag` whose file does not yet exist.

All errors must be resolved before handoff.
