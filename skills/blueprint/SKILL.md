---
name: blueprint
description: >
  Orchestrates creation of software lifecycle artifacts (GoalSpec, Glossary,
  DesignSpec, ArchitectureSpec, DataSpec, ApiSpec, TestSpec) and epic
  decomposition (issues). Conducts schema-driven interviews, writes sections
  via the write_spec_fields tool, and produces JSON + Markdown output.
  Use when creating artifacts or breaking down epics into issues.
version: 3.0.0
---

# Blueprint

Blueprint is the project artifact orchestrator. It conducts schema-driven
interviews, writes sections via tools, and produces JSON + Markdown output
for every artifact.

---

## Responsibilities

Blueprint is responsible for:

1. Determining which artifact is being created.
2. Loading the artifact schema (JSON Schema, generated from proto YAML).
3. Loading dependency artifacts.
4. Running structural lint on existing artifacts and surfacing findings.
5. Conducting schema-driven interviews (one question at a time).
6. Writing sections via the `write_spec_fields` tool.
7. Producing JSON and Markdown output for every completed artifact.
8. Producing handoff recommendations.

`instructions/*.md` explain section semantics for the interview. `schemas/*.schema.json` enforce structure for validation.

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

## Session Orientation

Run the steps below at the start of every session, unless resuming a partial
interview (in which case skip to the first unanswered question).

**Epic → Issue → SubIssue flow:**
- TaskPlan (`plan`) produces epics in `tasks/epics/`.
- Each epic decomposes into issues (`IS-NNN`) via the `issues` command.
- Issues decompose further into sub-issues (`SI-NNN`) via `issues` on the issue.

For the issues process, follow `instructions/Issue.md`.

---

### Artifact Table

| # | Command        | Artifact         | Guide (instructions)                            | JSON Schema (generated)                   | Dependencies                                                                                              | Output (Markdown + JSON)                                          |
|---|----------------|------------------|-------------------------------------------------|-------------------------------------------|-----------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| 0 | `goal`         | GoalSpec         | `instructions/GoalSpec.md`              | `goalspec.schema.json`             | (none)                                                                                                  | `artifacts/GoalSpec.md` + `artifacts/GoalSpec.json`              |
| 1 | `glossary`     | Glossary         | `instructions/Glossary.md`              | `glossary.schema.json`               | `artifacts/GoalSpec.json`                                                                                 | `artifacts/Glossary.md` + `artifacts/Glossary.json`              |
| 2 | `design`       | DesignSpec       | `instructions/DesignSpec.md`            | `designspec.schema.json`             | `artifacts/GoalSpec.json`, `artifacts/Glossary.json`                                                      | `artifacts/DesignSpec.md` + `artifacts/DesignSpec.json`          |
| 3 | `architecture` | ArchitectureSpec | `instructions/ArchitectureSpec.md`      | `archspec.schema.json`               | `artifacts/GoalSpec.json`, `artifacts/Glossary.json`                                                      | `artifacts/ArchitectureSpec.md` + `artifacts/ArchitectureSpec.json` |
| 4 | `data`         | DataSpec         | `instructions/DataSpec.md`          | `dataspec.schema.json`       | `artifacts/GoalSpec.json`, `artifacts/ArchitectureSpec.json`                                              | `artifacts/DataSpec.md` + `artifacts/DataSpec.json`              |
| 5 | `api`          | ApiSpec          | `instructions/ApiSpec.md`         | `apispec.schema.json`        | `artifacts/GoalSpec.json`, `artifacts/ArchitectureSpec.json`, `artifacts/DataSpec.json`               | `artifacts/ApiSpec.md` + `artifacts/ApiSpec.json`   |
| 6 | `test`         | TestSpec         | `instructions/TestSpec.md`        | `testspec.schema.json`       | `artifacts/GoalSpec.json`, `artifacts/ApiSpec.json`, `artifacts/DataSpec.json`                        | `artifacts/TestSpec.md` + `artifacts/TestSpec.json` |
| 7 | `plan`         | TaskPlan         | `instructions/TaskPlan.md`              | `taskplan.schema.json`             | `artifacts/GoalSpec.json`, `artifacts/DesignSpec.json`, `artifacts/ArchitectureSpec.json`, `artifacts/DataSpec.json`, `artifacts/ApiSpec.json`, `artifacts/TestSpec.json` | `tasks/PLAN.md` + `tasks/epics/` |
| 8 | `issues <epic-id>` | Issue | `instructions/Issue.md` | `issue.schema.json` | `tasks/PLAN.md`, `tasks/epics/EP-NNN/` | `tasks/epics/EP-NNN/IS-NNN/` (md + json) |

All paths under `instructions/` and `.schema.json` are relative to `skills/blueprint/`.

`plan` produces multiple files. All behaviour is defined in `instructions/TaskPlan.md`.
`issues` decomposes an epic into independently-grabbable issues, each with acceptance
criteria traceable to the epic. Sub-issues (`SI-NNN`) can further decompose an issue.

**Dependency note:** Prefer `.json` over `.md` when loading dependencies.

---

### Step 1 — Load artifact

Call `load_artifact` with the artifact type. If required dependencies are
missing, stop and ask the user to create them first.

### Step 2 — Lint existing artifacts

If no JSON artifacts exist on disk, skip to Step 3.

Otherwise call `lint(mode: "assess")` listing only artifact types whose JSON
exists. If `decision: "block"`, report errors and ask the user to fix them
now or defer. If `"proceed"` with warnings, note the count and continue.
If clean, proceed silently.

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

Conduct the interview directly, following the **Interview Rules**.

**For each section, in order:**

1. Present a single question about the section.
2. Provide a recommended answer based on best practices and loaded context.
3. Wait for the user's answer.
4. Validate the answer against the schema, loaded context, and other specs.
5. If the answer is incomplete, ask follow-up questions.
6. If confidence is low or there are open questions, flag them to the user
   before proceeding. Do not write the section yet.
7. Once the user confirms the section content, proceed to Step 5 to write it.

**If the user has resolved all open questions and confidence is high:**
Write the section via `write_spec_fields` (Step 5), then move to the next section.

**Resume support:** If resuming from a section, skip all prior sections
and start at the specified section.

---

### Step 5 — Section persistence

After each section is confirmed, write the JSON field using `write_spec_fields`.
The tool is atomic and incremental — no need to track full JSON state.

On success, show the JSON path and updated timestamp:
"Field written: <FieldLabel>. JSON: <path>."

On revision request: re-interview affected sections, rewrite, re-verify.

**Error recovery:** If `write_spec_fields` fails (disk error, JSON parse error,
permission denied), report the error to the user immediately. Do not continue
the interview. Help the user resolve the underlying issue and retry the write.
If the JSON file becomes corrupted, load the last known good state from disk
before retrying.

**Cross-spec version sync:** When creating ArchitectureSpec, DataSpec, ApiSpec,
or TestSpec, ensure the version reference field matches the referenced spec:
- `archspec.goalSpecVersion` must match `goalspec.version` (with optional `v` prefix)
- `dataspec.goalSpecVersion` must match `goalspec.version`
- `apispec.dataSpecVersion` must match `dataspec.version`
- `testspec.apiSpecVersion` must match `apispec.version`

After the last section is written, proceed to Step 6.

---

### Step 6 — Confirmation gate

Present the completed artifact to the user for review. Do not proceed until
the user explicitly confirms.

### Step 7 — Finalize

Run `lint(mode: "assess")` on the artifact type. If it fails, show errors
and fix only with user approval, then re-validate. On success:

1. `generate_artifact_markdown` — regenerate Markdown from JSON (JSON is the single source of truth)
2. `handoff` — display available next steps

Remind the user to open a fresh session for the next artifact.

---

## Troubleshooting

See `TROUBLESHOOTING.md` for common lint failures and fixes.
