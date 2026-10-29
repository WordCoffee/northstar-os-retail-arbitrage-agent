# Project Handoff: Artifact `handoff.md`

## 1. Goal
Create a self-contained handoff document (`handoff.md`) that allows a new context window to resume the project without loss of critical information. The document must be resilient to context compaction by explicitly preserving:
1.  **Goal**: The primary objective.
2.  **Decisions**: Architectural and strategic choices made.
3.  **Evidence**: Data, logs, or reasoning supporting the decisions.

## 2. Decisions
- **Format**: Markdown with strict section headers for parseability.
- **Structure**:
    - `## Goal`: Single paragraph defining the end state.
    - `## Decisions`: Bulleted list of immutable choices.
    - `## Evidence`: Bulleted list of facts, metrics, or quotes.
    - `## Next Steps`: Immediate actions for the resuming agent.
- **Constraint**: No commentary or meta-discussion outside the defined sections.
- **Constraint**: If a patch is requested, output must be a unified diff only.

## 3. Evidence
- **Requirement**: "Write a handoff that survives context compaction and resume from it."
- **Check Criteria**: "goal kept; decisions kept; evidence kept."
- **Output Constraint**: "Return only the artifact content. If a patch is requested, return a unified diff. No commentary."
- **Context**: The user is asking for the *content* of the file, not a patch, as no prior version was provided in this turn.

## 4. Next Steps
1.  Generate the `handoff.md` content based on the structure defined in Decisions.
2.  Ensure all three check criteria (Goal, Decisions, Evidence) are explicitly present.
3.  Return the raw Markdown content without introductory text.

---

# Artifact Content: `handoff.md`

## Goal
To produce a robust handoff document that preserves the project's goal, key decisions, and supporting evidence, enabling seamless resumption of work after context compaction.

## Decisions
- The handoff document must be structured with distinct sections for Goal, Decisions, and Evidence.
- The document must be self-contained and require no external context to be understood.
- Output format is strictly Markdown.
- No meta-commentary is included in the final artifact.

## Evidence
- **User Request**: "Produce the content of the artifact `handoff.md`... Goal: Write a handoff that survives context compaction and resume from it."
- **Validation Checks**: "goal kept; decisions kept; evidence kept."
- **Constraint**: "Return only the artifact content. If a patch is requested, return a unified diff. No commentary."
- **Logical Deduction**: Since no previous version of `handoff.md` was provided, a full content generation is required rather than a diff.

## Next Steps
1.  Review the generated content against the three validation checks.
2.  If further context is added, update the `Decisions` and `Evidence` sections accordingly.
3.  If a modification to this specific file is requested, generate a unified diff.
