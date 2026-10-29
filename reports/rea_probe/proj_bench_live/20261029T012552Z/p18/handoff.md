# Project Handoff: `handoff.md`

## 1. Goal
**Objective:** Create a durable handoff document (`handoff.md`) that allows a new agent or human to resume work after context compaction.
**Success Criteria:**
- The document must be self-contained.
- It must explicitly preserve:
  1. The original goal.
  2. Key decisions made.
  3. Evidence supporting those decisions.
- No external context is assumed.

## 2. Decisions
| ID | Decision | Rationale |
| :--- | :--- | :--- |
| D1 | Structure the handoff into three distinct sections: Goal, Decisions, Evidence. | Ensures the "Checks" requirement is met explicitly and verifiably. |
| D2 | Use a tabular format for decisions to allow quick scanning. | Reduces cognitive load during resume. |
| D3 | Include a "Resume Protocol" section. | Provides actionable next steps for the resuming agent. |
| D4 | Keep the document concise (< 500 words). | Prevents bloat; ensures it fits in context windows easily. |

## 3. Evidence
- **Constraint Check:** The prompt explicitly requires "goal kept; decisions kept; evidence kept."
- **Format Check:** The prompt requires "Return only the artifact content. No commentary."
- **Context Check:** The prompt mentions "survives context compaction," implying the document must be standalone and not rely on previous chat history.

## 4. Resume Protocol
1. **Read Section 1 (Goal):** Confirm the objective is still valid.
2. **Review Section 2 (Decisions):** Ensure no new constraints have invalidated previous choices.
3. **Verify Section 3 (Evidence):** Check if any new data contradicts the recorded evidence.
4. **Execute Next Step:** Begin work based on the current state defined in this document.

## 5. Current State
- **Status:** Ready for implementation/resume.
- **Blockers:** None.
- **Next Action:** Implement the handoff structure as defined in Section 2.
