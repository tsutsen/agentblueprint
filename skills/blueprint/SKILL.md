---
name: blueprint
description: >
  Orchestrates creation of software lifecycle artifacts (GoalSpec, Glossary,
  DesignSpec, ArchitectureSpec, DataSpec, ApiSpec, TestSpec) and epic
  decomposition (issues). Conducts schema-driven interviews, writes sections
  via the write_spec_fields tool, and produces JSON + Markdown output.
  Use when creating artifacts or breaking down epics into issues.
version: 2.0.0
---

# Blueprint

Blueprint is the project artifact orchestrator. It conducts schema-driven
interviews, writes sections via tools, and produces JSON + Markdown output
for every artifact.

---

## Responsibilities

Blueprint is responsible for:

1. Determining which artifact is being created.
2. Loading the artifact schema.
3. Loading dependency artifacts.
4. Running structural lint on existing artifacts and surfacing findings.
5. Conducting schema-driven interviews (one question at a time).
6. Writing sections via the `write_spec_fields` tool.
7. Producing JSON and Markdown output for every completed artifact.
8. Producing handoff recommendations.

---

## Suite Overview

| Concern              | Command                     |
|----------------------|-----------------------------|
| Artifact creation    | `/skill:blueprint <type>`   |
| Epic decomposition   | `/skill:blueprint issues`   |

---

## Interview Rules

When conducting an interview, follow these rules strictly:

1. **Relentless Inquiry:** Do not stop until every section has a complete,
   unambiguous shared understanding.
2. **Section Sequencing:** Follow the section order from the schema exactly.
   Complete one section fully before moving to the next.
3. **Single Questioning:** Ask one question at a time. Wait for the user's
   answer before proceeding.
4. **Recommended Answers:** For every question, provide your own recommended
   answer based on best practices and loaded context. Label it clearly as a
   recommendation, not a conclusion.
5. **Loaded Context Validation:** If a question can be answered from the
   loaded context (dependencies, schema, prior artifacts), use that context
   rather than asking the user.
6. **Contradiction Detection:** If the user's answer conflicts with loaded
   context, surface it immediately. Example: "Your code cancels entire Orders,
   but you just said partial cancellation is possible — which is right?"
7. **Term Clarification:** If the user uses a vague or overloaded term,
   propose a precise canonical term before continuing.
8. **Glossary Enforcement:** If a glossary was loaded as context, check
   every new term against it. Flag conflicts immediately.
9. **Schema Compliance:** Each section must conform strictly to the schema.
   If the schema specifies a format (e.g., Planguage for NFRs), enforce it.
   Do not accept free-form content where a structured format is required.
   Prompt the user to restate in the required format if needed.
10. **Inferences vs Facts:** Maintain a clear distinction between Facts
    (verifiable, sourced) and Inferences (derived by reasoning, uncertain).
    Never treat an inference as a fact without explicit user confirmation.
11. **No hallucination:** Only record what the user has explicitly stated
    or what can be verified from loaded context. If uncertain about a detail,
    ask. Do not fill gaps with assumptions.
12. **Resume Handling:** If resuming, skip all prior sections and start at
    the specified section. Do not re-interview sections that were already
    completed.

---

## Output Format

After each section is complete, produce:

```yaml
section: <SectionName>
confidence: <high | medium | low>
content: <section content, formatted per schema requirements>
open_questions:
  - <any unresolved questions for the user to address later>
```

Low confidence or non-empty `open_questions` must be flagged to the user
before writing the section. Do not proceed silently.

---

## Session Orientation

**Every time a command is invoked at the start of a session**, perform the
following steps before anything else. Do not skip them or read any files
beyond what is listed.

> **Resumption exception:** If the current session already contains a partial
> interview for this artifact type, skip orientation and resume from the first
> unanswered question.

### Issues command

If the command is `issues <epic-id>` (e.g., `issues EP-001`):

1. Extract the epic ID from the argument.
2. Verify the epic exists at `tasks/epics/EP-NNN/EP-NNN-slug.md`.
3. If not found, abort and ask the user to run `/skill:blueprint plan` first.
4. Proceed to the schema's Process Override section (defined in Issue.md).

---

### Artifact Table

| # | Command        | Artifact         | Schema                        | Dependencies                                                                                              | Output (Markdown + JSON)                                          |
|---|----------------|------------------|-------------------------------|-----------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| 0 | `goal`         | GoalSpec         | `skills/blueprint/instructions/GoalSpec.md`         | (none)                                                                                                  | `artifacts/GoalSpec.md` + `artifacts/GoalSpec.json`              |
| 1 | `glossary`     | Glossary         | `skills/blueprint/instructions/Glossary.md`         | `artifacts/GoalSpec.json`                                                                                 | `artifacts/Glossary.md` + `artifacts/Glossary.json`              |
| 2 | `design`       | DesignSpec       | `skills/blueprint/instructions/DesignSpec.md`       | `artifacts/GoalSpec.json`, `artifacts/Glossary.json`                                                      | `artifacts/DesignSpec.md` + `artifacts/DesignSpec.json`          |
| 3 | `architecture` | ArchitectureSpec | `skills/blueprint/instructions/ArchitectureSpec.md` | `artifacts/GoalSpec.json`, `artifacts/Glossary.json`                                                      | `artifacts/ArchitectureSpec.md` + `artifacts/ArchitectureSpec.json` |
| 4 | `data`         | DataSpec         | `skills/blueprint/instructions/DataSpec.md`   | `artifacts/GoalSpec.json`, `artifacts/ArchitectureSpec.json`                                              | `artifacts/DataSpec.md` + `artifacts/DataSpec.json`              |
| 5 | `api`          | ApiSpec          | `skills/blueprint/instructions/ApiSpec.md`    | `artifacts/GoalSpec.json`, `artifacts/ArchitectureSpec.json`, `artifacts/DataSpec.json`               | `artifacts/ApiSpec.md` + `artifacts/ApiSpec.json`   |
| 6 | `test`         | TestSpec         | `skills/blueprint/instructions/TestSpec.md`   | `artifacts/GoalSpec.json`, `artifacts/ApiSpec.json`, `artifacts/DataSpec.json`                        | `artifacts/TestSpec.md` + `artifacts/TestSpec.json` |
| 7 | `plan`         | TaskPlan         | `skills/blueprint/instructions/TaskPlan.md`         | `artifacts/GoalSpec.json`, `artifacts/DesignSpec.json`, `artifacts/ArchitectureSpec.json`, `artifacts/DataSpec.json`, `artifacts/ApiSpec.json`, `artifacts/TestSpec.json` | `tasks/PLAN.md` + `tasks/epics/` |
| 8 | `issues <epic-id>` | Issue | `skills/blueprint/instructions/Issue.md` | `tasks/PLAN.md`, `tasks/epics/EP-NNN/` | `epics/EP-NNN/IS-NNN/` (md + json) |

`plan` produces multiple files. All behaviour is defined in `skills/blueprint/instructions/TaskPlan.md`.
`issues` decomposes an epic into independently-grabbable issues.

**Dependency note:** JSON artifacts are preferred over Markdown as dependencies
because they are machine-readable and can be validated. When loading dependencies,
prefer `.json` over `.md` when both exist. Load `.md` only when `.json` is absent.

**Process Override note:** If the loaded schema contains a `## Process Override`
section, execute it instead of Steps 1–7 of the Standard Flow. Pass the schema's
context (dependencies, loaded content) to the override steps.

---

### Step 1 — Load artifact (schema + dependencies)

Call the `load_artifact` tool:

```
tool: load_artifact
args:
  artifactType: <goal|glossary|design|arch|data|api|test|plan|issues>
```

The tool resolves the schema and all dependencies (preferring JSON over Markdown),
validates that required dependencies exist, and returns a structured result.

**For `issues`:** the tool returns the Issue schema. Proceed to Step 2.

**If required dependencies are missing:** the tool returns an error. Do not proceed.
Ask the user to create the missing artifacts first.

---

### Step 2 — Lint existing artifacts

Call the `lint` tool with `mode: "assess"` (default) to run the suite linter
and get a decision:

```
tool: lint
args:
  artifacts: [<list only artifact types whose JSON exists on disk>]
  mode: "assess"
```

Dynamically determine which artifact types have JSON files on disk and include
only those. Do not hardcode a static list.

**If `decision: "block"`:**

Report the blocking errors to the user before starting the interview:

> "The linter found <N> error(s) in existing artifacts before we begin.
> These must be resolved for the suite to remain consistent."

List each error with its category, message, and hint.

Ask the user: "Fix these now before continuing, or proceed with the interview
and address them in the affected artifact's own session?"

If the user chooses to fix now: do not start the interview. Help the user
correct the affected artifacts, re-run the linter, and confirm clean before
proceeding.

**If `decision: "proceed"` with warnings:**

Briefly note the warning count but do not block:

> "Linter passed. <N> warning(s) noted — see lint report for details."

**If `decision: "proceed"` with no warnings:**

Proceed silently.

---

### Step 3 — Orientation

Check whether the JSON artifact file exists on disk (e.g., `artifacts/GoalSpec.json`).

- **File absent:** proceed normally — this is a fresh start.
- **File present:** load the JSON and inspect which top-level fields have
  content. Report the artifact name, its sections, which sections have content
  (by checking which fields are populated), and any missing dependencies.

Output before the first interview question:

- artifact being produced and its sections
- dependencies loaded; any missing
- last confirmed section (if resuming)

If resuming, ask: "Resume from the last confirmed section, or restart from the beginning?" Wait for the user's answer.

---

### Step 4 — Interview

Conduct the interview directly, following the **Interview Rules** and **Output Format**
defined at the top of this document.

**For each section, in order:**

1. Present a single question about the section.
2. Provide a recommended answer based on best practices and loaded context.
3. Wait for the user's answer.
4. Validate the answer against the schema, loaded context, and other specs.
5. If the answer is incomplete, ask follow-up questions.
6. When the section is complete, produce the YAML output:

```yaml
section: <SectionName>
confidence: <high | medium | low>
content: <validated section content>
open_questions:
  - <any unresolved questions>
```

7. If confidence is low or there are open questions, flag them to the user
   before proceeding. Do not write the section yet.
8. Once the user confirms the section content, proceed to Step 5 to write it.

**If the user has resolved all open questions and confidence is high:**
Write the section via `write_spec_fields` (Step 5), then move to the next section.

**Resume support:** If resuming from a section, skip all prior sections
and start at the specified section.

---

### Step 5 — Section persistence

After each section is confirmed, write the JSON field using the
`write_spec_fields` tool. The tool loads the existing JSON from disk,
applies all updates, and writes back — **atomic and incremental**. No need
to track the full JSON state.

```
tool: write_spec_fields
args:
  filePath: artifacts/<ArtifactType>.json
  field: <field label>
  content: <validated section content>
  updates: [
    { jsonPath: <dot-separated path>, jsonValue: <value> },
    ...
  ]
```

**Single field:**

```
tool: write_spec_fields
args:
  filePath: artifacts/GoalSpec.json
  field: Project Objective
  content: "The system shall provide..."
  updates: [
    { jsonPath: "objective.statement", jsonValue: "The system shall provide..." }
  ]
```

**Multiple fields (one call):**

```
tool: write_spec_fields
args:
  filePath: artifacts/GoalSpec.json
  field: Functional Requirements
  content: "FR-001: User can login. FR-002: User can logout."
  updates: [
    { jsonPath: "functionalRequirements", jsonValue: [
      { "id": "FR-001", "description": "User can login", "priority": "high" },
      { "id": "FR-002", "description": "User can logout", "priority": "medium" }
    ]}
  ]
```

The JSON is the single source of truth — Markdown is derived later via
`generate_artifact_markdown`.

On success, show the JSON path and updated timestamp:
"Field written: <FieldLabel>. JSON: <path>."

On revision request: re-interview affected sections, rewrite, re-verify.

After the last section is written, proceed to Step 6.

---

### Step 6 — Confirmation gate

Before linting, present the completed artifact to the user for review:

> "Here is the completed <ArtifactName>. Please review it and confirm
> it is correct, or let me know what needs to change."

Do not proceed to lint or handoff until the user explicitly confirms.
This gate is mandatory for all artifacts except GoalSpec (which is the
starting point).

### Step 7 — Lint

Now validate the JSON artifact against its schema:

```
tool: lint
args:
  artifacts: ["<type>"]  # e.g. ["goal"]
  mode: "assess"
```

If validation fails, show the errors to the user and suggest fixes. Do
not modify the JSON without explicit user approval. After user confirms,
apply the fix and re-validate.

---

### Step 8 — Generate Markdown from JSON

After lint passes, regenerate the Markdown from the JSON to ensure zero
drift between formats. The JSON is the single source of truth; Markdown
is derived.

```
tool: generate_artifact_markdown
args:
  artifactType: <goal|glossary|design|arch|data|api|test|plan|issue>
  jsonPath: artifacts/<ArtifactType>.json
```

This overwrites `artifacts/<ArtifactType>.md` with content derived from
the JSON. The Markdown is now guaranteed to match the JSON exactly.

---

### Step 9 — Handoff

Call the `handoff` tool to produce a handoff table:

```
tool: handoff
args: {}
```

The tool checks all artifacts' dependencies against the DEPS constant,
reads frontmatter for accurate status, and returns a formatted table
of available next steps.

Display the tool's output to the user. Do not modify the table — the
tool produces the authoritative list of available next steps.

---

## Session Hygiene

Each artifact interview should be conducted in its own dedicated session.

After handoff completes, remind the user:

> "Open a fresh session for the next artifact and run the corresponding
> command — the skill orients itself automatically from `artifacts/`."

---

## Glossary Alignment Pass (Final Step)

**When to run:** After ALL other specs (GoalSpec, DesignSpec, ArchitectureSpec,
DataSpec, ApiSpec, TestSpec, TaskPlan) are complete and linted.

**Purpose:** Ensure the glossary is the single source of truth — every term
used in any spec has a glossary entry, and every spec has glossaryRefs for
terms it references.

### Process

1. **Scan all specs for glossary terms** — Extract all terms referenced in
   spec text (requirements, descriptions, function names, entity names,
   screen names, etc.).

2. **Compare against glossary** — For each term found:
   - If it exists in the glossary: verify it has a `glossaryRefs` entry in
     the spec where it appears.
   - If it does NOT exist in the glossary: **offer to add it**.

3. **Add missing terms** — For each term not in the glossary:
   - Present the term and its context to the user.
   - Propose a definition (based on how it's used in the spec).
   - Propose a category (domain, technical, security, ui).
   - Propose related terms.
   - On approval: add to glossary, re-generate Glossary.md.

4. **Fix missing glossaryRefs** — For each spec that references a glossary
   term without a `glossaryRefs` entry:
   - Add the term's GL-NNN ID to the appropriate level (top-level,
     section-level, or item-level).
   - Re-run lint to confirm.

5. **Check for near-duplicates** — Run the linter's near-duplicate check.
   If two terms are >70% lexically similar, present them to the user and
   suggest consolidation.

6. **Final lint** — Run `lint()` across all artifacts. All errors must be
   resolved. Warnings about intentional ID gaps (from removed terms) are
   acceptable.

### Integration with Other Specs

When creating any spec (DesignSpec, ArchitectureSpec, DataSpec, ApiSpec,
TestSpec, TaskPlan):

- **During the interview:** When a term is identified that might need a
  glossary entry, note it for the alignment pass. Do NOT add terms directly
  to the glossary during spec creation.
- **After the spec is written:** Note any new terms for the alignment pass.
- **The glossary is updated in bulk** during the alignment pass, not incrementally.

This keeps spec creation focused and prevents glossary churn during iterative
development.
