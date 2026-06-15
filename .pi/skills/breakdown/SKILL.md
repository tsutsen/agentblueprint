---
name: breakdown
version: 1.1.0
changelog:
  - version: 1.1.0
    date: 2026-06-09
    changes:
      - Normalized changelog format to structured {version, date, changes}.
description: >
  Breaks a single epic from tasks/epics/ into independently-grabbable issues using vertical slice (tracer bullet) decomposition. Reads the epic file, quizzes the user on the breakdown, then writes individual issue files to tasks/issues/. Updates the parent epic's front matter with the issue list. Use after /skill:blueprint plan has produced epic files. Invoke with an epic ID: /skill:breakdown EP-001.
---

# Breakdown

This skill takes a single epic and decomposes it into independently-grabbable issues using vertical slice decomposition. Each issue cuts end-to-end through all relevant layers rather than isolating a single layer.

breakdown reads from `tasks/epics/` and writes to `tasks/issues/`. It never modifies `tasks/PLAN.md` content — only the parent epic's front matter `issues:` list is updated.

---

## Invocation

```
/skill:breakdown <epic-id>
```

Example: `/skill:breakdown EP-001`

If no epic ID is provided, list all epics found in `tasks/epics/` with their current status and ask the user which one to work on.

---

## Issue Front Matter

```yaml
---
artifact: Issue
id: IS-<NNN>
title: <short title>
type: <HITL | AFK>
status: <not_started | in_progress | needs_review | complete>
epic: <EP-NNN>
blocked_by:
  - <IS-NNN>        # or empty list []
milestone: <milestone name or ID>
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---
```

**Type definitions:**

| Type   | Meaning                                                                          |
|--------|----------------------------------------------------------------------------------|
| `AFK`  | Can be implemented and merged by an agent without human interaction.             |
| `HITL` | Requires human input at some point — design decision, review gate, external dep. |

Prefer AFK over HITL. Only mark HITL when human judgment is genuinely required,
not just because the task is complex.

**Issue ID sequencing:** scan `tasks/issues/` for the highest existing IS-NNN before creating new issues. Continue the sequence — do not restart from IS-001 per epic. IDs are project-global, not epic-scoped.

---

## Process

### Step 1 — Orientation

Read the following files:

- `artifacts/ProjectManifest.md` — project context
- `artifacts/Glossary.md` — domain vocabulary (if present)
- `artifacts/ArchitectureSpec.md` — architectural constraints (if present)
- `tasks/PLAN.md` — milestone context
- `tasks/epics/<epic-id>-*.md` — the target epic (required; abort if not found)
- `tasks/issues/` — scan for highest existing IS-NNN to continue ID sequence

Do **not** read other epic files or any schema files not listed here.

Report a brief orientation summary:
- Epic title, objective, and scope
- Relevant ADRs or architectural constraints found
- Current highest issue ID (next will be IS-NNN+1)
- Any open questions noted in the epic's Notes section

### Step 2 — Explore the codebase (if available)

If the codebase is accessible, explore the areas relevant to this epic before drafting slices. Issue titles and descriptions should use the project's domain vocabulary from the Glossary and respect ADRs in the relevant area.

Do not ask the user about things that can be determined from the codebase.

### Step 3 — Draft vertical slices

Decompose the epic into tracer bullet issues. Each issue is a thin vertical slice that cuts through ALL relevant integration layers end-to-end, not a horizontal slice of one layer.

<vertical-slice-rules>
- Each slice delivers a narrow but complete path through every relevant layer
- A completed slice is independently demoable or verifiable
- Each slice maps to one or more of the epic's acceptance criteria
- Prefer many thin slices over few thick ones
- A slice that only touches one layer (e.g. "add database migration") is a horizontal slice — split or reframe it as end-to-end behaviour </vertical-slice-rules>

### Step 4 — Quiz the user

Present the proposed breakdown as a numbered list. For each slice show:

- **ID**: IS-NNN (proposed)
- **Title**: short descriptive name using domain vocabulary
- **Type**: HITL or AFK
- **Blocked by**: which other proposed issues (if any)
- **Acceptance criteria covered**: which of the epic's criteria this addresses

Then ask:
1. Does the granularity feel right — too coarse or too fine?
2. Are the dependency relationships correct?
3. Should any slices be merged or split?
4. Are HITL/AFK assignments correct?

Iterate until the user explicitly approves the breakdown. Do not write any files before approval.

### Step 5 — Write issues

Write issues in dependency order — blockers first — so that `blocked_by` can reference real IS-NNN identifiers rather than proposed ones.

For each issue, write `tasks/issues/IS-<NNN>-<slug>.md`:

```markdown
---
artifact: Issue
id: IS-<NNN>
title: <title>
type: <HITL | AFK>
status: not_started
epic: <EP-NNN>
blocked_by:
  - IS-<NNN>
milestone: <from parent epic>
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---
# IS-<NNN>: <title>
## What to build
<Concise description of this vertical slice. Describe end-to-end behaviour,
not layer-by-layer implementation.>
<Avoid specific file paths or code snippets unless a prototype produced a
snippet that encodes a decision more precisely than prose can — state machine,
reducer, schema, type shape. If included, note it came from a prototype and
trim to the decision-rich parts only.>
## Acceptance criteria
- [ ] <criterion>
- [ ] <criterion>
## Blocked by
<IS-NNN reference, or "None — can start immediately.">
```

After writing each file, verify the write by reading it back. Report each written file to the user as it completes.

### Step 6 — Update parent epic

After all issue files are written, update the parent epic file's front matter:

```yaml
issues:
  - IS-NNN
  - IS-NNN
  - ...
```

Also update the `updated` date. Do not modify any other part of the epic file.

Verify the update by reading back the front matter.

---

## Handoff

After all issues are written and the epic is updated:

```
breakdown complete for <EP-NNN>: <epic title>
Issues created:
  IS-NNN  <title>  [AFK]
  IS-NNN  <title>  [HITL]
  ...
Total: X issues (Y AFK, Z HITL)
Next steps:
  - Run /skill:breakdown EP-NNN for other epics that are ready
  - Run /skill:redline to check consistency across all artifacts
  - Pick up any AFK issue and begin implementation
```

Do not automatically invoke any other skill or open any session.
