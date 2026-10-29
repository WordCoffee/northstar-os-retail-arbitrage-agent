1. **Define Immutable State**: Extract the core goal, critical decisions, and supporting evidence into a structured, atomic format (e.g., JSON or YAML) that is independent of conversational history.
2. **Serialize to Artifact**: Write this state to a persistent, version-controlled file (e.g., `handoff.md` or `state.json`) to ensure it exists outside the volatile context window.
3. **Establish Resume Protocol**: Define a specific trigger or command (e.g., "Resume from `state.json`") that instructs the agent to load the artifact and verify its integrity before proceeding.
4. **Validate Continuity**: Upon resumption, cross-check the loaded state against the original goal to confirm no data loss or drift occurred during compaction.
5. **Execute Next Action**: Proceed with the next task using only the validated state as the source of truth, ignoring prior conversational context.
