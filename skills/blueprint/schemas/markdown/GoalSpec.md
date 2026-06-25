---
name: GoalSpec
type: schema
version: 4.0.0
---

## Goal Spec

The Goal Spec captures the *why* and *what* of the project — not the *how*.
It is the root artifact from which all planning, design, and architecture flow.
Every requirement here must eventually be traceable to an epic, an
implementation, and a test. Non-goals constrain the entire project scope.

**Honesty rule:** Only record what the user has explicitly stated or what
can be verified from the codebase or loaded artifacts. Do not fill gaps
with assumptions. If uncertain, ask.

---

---

## Before the interview

If a codebase exists, explore it briefly before asking the first question.
Look for: README, existing docs, prior spec files, domain concepts in file
and function names. Use findings to seed recommended answers — do not ask
about things the code already shows.

---

### Project Objective

A concise description of the problem being solved and the desired outcome.

Must answer:
* What are we building?
* Who is it for?
* Why does it exist — what problem does it solve that isn't solved today?

Must NOT describe implementation, architecture, or technology choices.

**glossaryRefs** (array of GL-NNN): Key domain concepts from the objective. Maps the objective to the project vocabulary.

Good: "A local-first tool that routes developer queries to the most capable
available LLM based on task complexity, minimising latency and cost."

Bad: "A FastAPI server that calls llama.cpp for simple queries and OpenRouter
for complex ones."

> **Note:** After all other sections are complete, re-read the Project
> Objective and ask the user: "Now that we've captured requirements, stories,
> and success criteria — does this objective still accurately describe the
> project, or should we refine it?" Revise if needed before marking complete.

---

### Functional Requirements

Observable capabilities the system must provide.

Each requirement must:
* Have a unique identifier in format `REQ-NNN-slug` (REQ-001-initiate-research-session)
* Be independently testable
* Describe observable behaviour, not implementation
* Be owned by one actor
* Have **glossaryRefs** (array of GL-NNN): Domain concepts referenced in the requirement description

If a requirement contains a measurable target (latency, size, rate,
percentage), it is an NFR or success criterion — not a functional requirement.
Split it: write the capability as an FR, write the threshold as an NFR.

Good:
* REQ-001: User can import PDF documents.
* REQ-002: User can search imported documents by keyword.

Bad:
* Use a PDF parser library. ← implementation
* The system should be responsive. ← not testable
* User can import and search documents. ← two requirements in one
* Search results return within 500ms. ← measurable threshold → NFR

If the user states a vague or compound requirement, surface it immediately:
"That sounds like two requirements — shall we split them?"

---

### Non-Functional Requirements

Quality attributes and operational constraints. NFRs describe *how well*
the system performs, not *what* it does.

Each NFR may also have:
* **glossaryRefs** (array of GL-NNN): Domain concepts in the scale/meter descriptions

**You MUST use Planguage format for every NFR. Do not accept free-form
NFR descriptions. If the user provides a vague NFR (e.g. "should be fast"),
prompt them to provide Scale and Meter before recording it.**

Each NFR must have a unique identifier in format `NFR-NNN-slug` (NFR-001-response-time).

```
NFR-<NNN>
Category:  <see categories below>
Scale:     <what is measured and in what unit>
Meter:     <how it will be measured — tool, condition, methodology>
Must:      <minimum acceptable; below this the system fails>
Plan:      <realistic target the team is aiming for>
Wish:      <ideal outcome if conditions allow>
```

Example:
```
NFR-001
Category:  Performance
Scale:     P95 response latency in milliseconds
Meter:     Load test at 100 concurrent users on reference hardware
Must:      < 1000ms
Plan:      < 500ms
Wish:      < 200ms
```

Categories:

If the user cannot define Scale or Meter, record the best available
description and flag it: "(Scale/Meter TBD — needs measurement before
implementation)". If only one level is available, record it as Must and
flag Plan and Wish as TBD.

---

### User Stories

Desired outcomes from the user's perspective. Stories provide context for
requirements but do not replace them — every story must link to at least
one functional requirement.

Each story must also have **glossaryRefs** (array of GL-NNN): Domain concepts in the capability or outcome descriptions.

Each story must have a unique identifier in format `US-NNN-slug` (US-001-start-research-question).

Format:
As a <actor>,
I want <capability>,
so that <outcome>.
→ REQ-NNN[, REQ-NNN...]

Each story must:
* Name a specific actor (not "user" if a more specific role exists)
* Express a goal, not a feature
* Link to one or more REQ-IDs that exist in this document

If a story has no clear requirement link: "Which functional requirement
does this story motivate?"

---

### Success Criteria

Objective, binary conditions that determine the project is complete.
Success criteria are the measurable thresholds for NFRs and the acceptance
gates for FRs.

Each criterion must have a unique identifier in format `SC-NNN-slug` (SC-001-percentage-completed-sessions).

Each criterion must:
* Be binary — passes or fails, no partial credit
* Be independently verifiable without subjective judgement
* Map to at least one FR (`REQ-NNN`) or NFR (`NFR-NNN`) that exists in this document

Good:
* PDF import works for files up to 100MB with no data loss.
* P95 search latency is under 500ms at 100 concurrent users.

Bad:
* The system feels fast. ← subjective
* Users are happy. ← not verifiable

If a criterion cannot be made binary: "Can we define a specific
measurement that makes this verifiable?"

---

### Non-Goals

Explicit statements of what this project will NOT attempt to solve.
Non-goals prevent scope creep and tell downstream artifacts what to exclude.

Each non-goal must:
* Have a unique identifier in format `NG-NNN-slug` (NG-001-general-web-search)
* Name a specific capability being excluded
* Give a brief reason (deferred, out of scope, handled elsewhere)
* Have **glossaryRefs** (array of GL-NNN): Glossary mapping for the excluded capability

Format:
* <Capability> — <reason>.

---

## Output

After the interview is complete and `artifacts/GoalSpec.json` has been
written via `write_section`, the Markdown file must be regenerated from
the JSON to ensure zero drift between formats.

```
tool: generate_artifact_markdown
args:
  artifactType: goal
  jsonPath: artifacts/GoalSpec.json
```

This overwrites `artifacts/GoalSpec.md` with content derived from the
JSON artifact. The JSON is the single source of truth; the Markdown is
derived.

## Linting

After producing `artifacts/GoalSpec.json`, run:

```
python extensions/blueprint/linters/lint_goalspec.py artifacts/GoalSpec.json \
  --schema schemas/goalspec.schema.json --json
```

All errors must be resolved before handoff. Warnings should be reviewed
with the user but do not block handoff.
