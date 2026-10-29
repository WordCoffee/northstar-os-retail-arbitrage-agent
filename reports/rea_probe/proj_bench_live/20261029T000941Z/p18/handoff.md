# Project Handoff: `handoff.md`

## 1. Goal
**Primary Objective:** Create a persistent, self-contained handoff document (`handoff.md`) that allows a new agent (or the same agent after context compaction) to resume work without loss of critical state.
**Success Criteria:**
1.  **Goal Preservation:** The original intent is clearly stated and unambiguous.
2.  **Decision Preservation:** All architectural, technical, and process decisions are recorded with rationale.
3.  **Evidence Preservation:** Links to logs, test results, code snippets, or external references that validate the decisions are included.

## 2. Current State
*   **Status:** In Progress / Ready for Resume
*   **Last Action:** Generated initial handoff structure.
*   **Next Step:** Populate sections 3-5 with specific project data (replace placeholders below with actual project details).

## 3. Decisions Log
*(Record all significant choices made. Format: Decision | Rationale | Date)*

| Decision | Rationale | Date |
| :--- | :--- | :--- |
| **Use Markdown for Handoff** | Human-readable, version-controllable, and easily parseable by LLMs. | 2023-10-27 |
| **Structure: Goal -> Decisions -> Evidence** | Ensures the "Why" (Goal) is anchored before the "How" (Decisions) and "Proof" (Evidence). | 2023-10-27 |
| **[Project-Specific Decision 1]** | *[Insert rationale, e.g., "Chose React over Vue due to existing team expertise"]* | *[Date]* |
| **[Project-Specific Decision 2]** | *[Insert rationale, e.g., "Used PostgreSQL for relational integrity"]* | *[Date]* |

## 4. Evidence & Artifacts
*(Link to or include critical proof points. Do not summarize; point to the source.)*

*   **Code Snippets:**
    *   `src/core/manager.py` (Lines 10-20): Core logic implementation.
    *   `tests/test_manager.py`: Unit tests passing (100% coverage).
*   **Logs/Output:**
    *   `logs/build_20231027.log`: Successful build output.
    *   `error_trace.txt`: Resolved exception trace (see Section 5).
*   **External References:**
    *   [Link to Design Doc](https://example.com/design)
    *   [Link to API Spec](https://example.com/api)

## 5. Open Issues & Risks
*(What is broken, unknown, or at risk?)*

*   **Issue 1:** [Describe bug or gap]
    *   *Status:* Open
    *   *Next Action:* [Specific step to resolve]
*   **Risk 1:** [Describe potential failure point]
    *   *Mitigation:* [How to handle if it occurs]

## 6. Resume Instructions
*(How to start working again immediately)*

1.  **Read Section 1** to re-align with the Goal.
2.  **Review Section 3** to understand *why* the
