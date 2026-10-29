1. **Define Core State**: Extract the immutable goal, critical architectural decisions, and key evidence (logs, data points) into a structured "State Snapshot" block.
2. **Serialize Context**: Convert the snapshot into a compact, self-contained Markdown summary that explicitly states what has been done and what remains, ensuring no external context is required for interpretation.
3. **Establish Resume Protocol**: Define the exact entry point for the next session, including the first action to take and the validation criteria to confirm the state is intact.
4. **Verify Integrity**: Cross-check the handoff document against the original goal and decision log to ensure no information was lost or altered during compression.
5. **Execute Handoff**: Save the document as the primary context artifact and terminate the current session, relying solely on this file for resumption.
