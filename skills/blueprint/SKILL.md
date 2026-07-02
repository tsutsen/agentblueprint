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

`instructions/*.md` explain spec semantics for the interview.
`schemas/*.schema.json` enforce structure. `schemas/example.*.json` show reference payloads.

---

## Interview Rules

When conducting an interview, follow these rules strictly:

1. **Section Sequencing:** Follow the section order from the schema exactly.
   Complete one section fully before moving to the next.
2. **Single Questioning:** Ask one question at a time. Wait for the user's
   answer before proceeding.
3. **Recommended Answers:** For every question, provide your own recommended
   answer based on best practices and loaded context. Label it clearly as a
   recommendation, not a conclusion.
4. **Loaded Context Validation:** If a question can be answered from the
   loaded context (dependencies, schema, prior artifacts), use that context
   rather than asking the user.
5. **Contradiction Detection:** If the user's answer conflicts with loaded
   context, surface it immediately. Example: "Your code cancels entire Orders,
   but you just said partial cancellation is possible — which is right?"
6. **Term Clarification:** If the user uses a vague or overloaded term,
   propose a precise canonical term before continuing.
7. **Glossary Enforcement:** If a glossary was loaded as context, check
   every new term against it. Flag conflicts immediately.
8. **Schema Compliance:** Each section must conform strictly to the schema.
   If the schema specifies a format (e.g., Planguage for NFRs), enforce it.
   Do not accept free-form content where a structured format is required.
   Prompt the user to restate in the required format if needed.
9. **Resume Handling:** If resuming, skip all prior sections and start at
   the specified section. Do not re-interview sections that were already
   completed.

---

## Session Orientation

Run the steps below at the start of every session, unless resuming a partial
interview (in which case skip to the first unanswered question).

---

### Artifact Table

| # | Command                | Artifact         | Dependencies                                                                                              | Output                                          |
|---|------------------------|------------------|-----------------------------------------------------------------------------------------------------------|-------------------------------------------------|
| 0 | `goal`                 | GoalSpec         | (none)                                                                                                  | `artifacts/GoalSpec.md` + `.json`              |
| 1 | `glossary`             | Glossary         | `GoalSpec.json`                                                                                           | `artifacts/Glossary.md` + `.json`              |
| 2 | `design`               | DesignSpec       | `GoalSpec.json`, `Glossary.json`                                                                          | `artifacts/DesignSpec.md` + `.json`            |
| 3 | `architecture`         | ArchitectureSpec | `GoalSpec.json`, `Glossary.json`                                                                          | `artifacts/ArchitectureSpec.md` + `.json`      |
| 4 | `data`                 | DataSpec         | `GoalSpec.json`, `ArchitectureSpec.json`                                                                  | `artifacts/DataSpec.md` + `.json`              |
| 5 | `api`                  | ApiSpec          | `GoalSpec.json`, `ArchitectureSpec.json`, `DataSpec.json`                                                | `artifacts/ApiSpec.md` + `.json`               |
| 6 | `test`                 | TestSpec         | `GoalSpec.json`, `ApiSpec.json`, `DataSpec.json`                                                         | `artifacts/TestSpec.md` + `.json`              |
| 7 | `plan`                 | TaskPlan         | `GoalSpec`, `DesignSpec`, `ArchitectureSpec`, `DataSpec`, `ApiSpec`, `TestSpec`                          | `tasks/PLAN.md` + `tasks/epics/`               |
| 8 | `gh_create_issue`      | Issue            | `tasks/PLAN.md`, `tasks/epics/EP-NNN/`                                                                    | `tasks/epics/EP-NNN/IS-NNN/` (md + json)       |

All artifact paths under `artifacts/` are relative to project root.
`instructions/*.md` and `schemas/*.schema.json` are relative to `skills/blueprint/`.

`plan` produces multiple files. All behaviour is defined in `instructions/TaskPlan.md`.
`gh_create_issue` decomposes an epic into independently-grabbable issues, each with acceptance
criteria traceable to the epic. Sub-issues (`SI-NNN`) are created via `gh_create_sub_issue`.

**Epic → Issue → SubIssue flow:**
- TaskPlan (`plan`) produces epics in `tasks/epics/`.
- Each epic decomposes into issues (`IS-NNN`) via `gh_create_issue`.
- Issues decompose further into sub-issues (`SI-NNN`) via `gh_create_sub_issue`.
- For the issues process, follow `instructions/Issue.md`.

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

Version drift between specs is caught by the linter (`version_drift` rule);
no manual sync is needed.

After the last section is written, proceed to Step 6.

---

### Step 6 — Confirmation

Ask the user to review and confirm before finalizing.

### Step 7 — Finalize

Run `lint(mode: "assess")`. On success, run `generate_artifact_markdown`
then `handoff` to display next steps.

---

## Troubleshooting

See `TROUBLESHOOTING.md` for common lint failures and fixes.
