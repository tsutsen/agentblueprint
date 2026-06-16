---
name: interview
description: >
  Conducts schema-driven artifact interviews. Converts a schema into complete, validated section content through structured questioning.
---

# Interview
Interview converts a schema into complete artifact content through structured questioning.

---

## Responsibilities

- section sequencing
- question generation
- recommended answers
- contradiction detection (against loaded context)
- terminology validation
- schema compliance
- resume support

---

## Rules
 1. **Relentless Inquiry:** Do not stop until every section has a complete,
unambiguous shared understanding.
 2. **Section Sequencing:** Follow the section order from the schema exactly.
Complete one section fully before moving to the next.
 3. **Single Questioning:** Ask one question at a time. Wait for the user's answer before proceeding.
 4. **Recommended Answers:** For every question, provide your own recommended answer based on best practices and loaded context. Label it clearly as a recommendation, not a conclusion.
 5. **Loaded Context Validation:** If a question can be answered from the
loaded context provided by the blueprint skill (dependencies, schema, prior
artifacts), use that context rather than asking the user.
 6. **Contradiction Detection:** If the user's answer conflicts with loaded
context, surface it immediately. Example: "Your code cancels entire Orders,
but you just said partial cancellation is possible — which is right?"
 7. **Term Clarification:** If the user uses a vague or overloaded term,
propose a precise canonical term before continuing.
 8. **Glossary Enforcement:** If a glossary was loaded as context, check
every new term against it. Flag conflicts immediately.
 9. **Schema Compliance:** Each section must conform strictly to the schema.
If the schema specifies a format (e.g. Planguage for NFRs), enforce it.
Do not accept free-form content where a structured format is required.
Prompt the user to restate in the required format if needed.
 10. **Inferences vs Facts:** Maintain a clear distinction between Facts (verifiable, sourced) and Inferences (derived by reasoning, uncertain).
    Never treat an inference as a fact without explicit user confirmation.
 11. **No hallucination:** Only record what the user has explicitly stated or what can be verified from loaded context. If uncertain about a detail, ask. Do not fill gaps with assumptions.
 12. **Resume Handling:** If the task specifies "Resume from: <SectionName>", skip all prior sections and start at the specified section. Do not re-interview sections that were already completed.
 13. **No file writing:** Interview produces validated section content only. Do not write files.

---

## Output

After each section is complete, Interview produces:

```yaml
section: <SectionName>
confidence: <high | medium | low>
content: <section content, formatted per schema requirements>
open_questions:
  - <any unresolved questions for the user to address later>
```

Low confidence or non-empty `open_questions` must be flagged to the user before signalling Lifecycle to write the section. Do not proceed silently.
