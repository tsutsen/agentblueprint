---
name: Glossary
type: schema
version: 1.0.0
---

## Glossary

Defines project vocabulary. Every domain term used in any spec must have
an entry here. This document is the single source of truth for terminology
across the entire project.

---

## Output Format

This artifact produces two files:

- `artifacts/Glossary.md` — human-readable document
- `artifacts/Glossary.json` — machine-readable, conforming to `schemas/glossary.schema.json`

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

* **Name** — exactly as it appears in other specs. Case-sensitive.
* **Definition** — precise and unambiguous. Must not use the term itself
  in its own definition. Must be at least one full sentence.
* **Examples** (optional) — concrete instances that clarify the definition.
* **Synonyms** (optional) — other names for this term used in the project.
  Synonyms must NOT have their own glossary entry.
* **Related Terms** (optional) — names of other terms in this glossary
  that are closely related. Must reference terms that exist.
* **Category** (optional) — grouping tag: `domain`, `technical`, `process`.

**Rules:**

* No circular definitions — term A must not be defined using term B if
  term B is defined using term A.
* Synonyms must not also have independent entries.
* Every term referenced as a `relatedTerm` must exist in this glossary.
* Actor names from GoalSpec must have entries.
* Entity names from DataSpec (when it exists) should have entries.
* Component names from ArchSpec (when it exists) should have entries.

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
