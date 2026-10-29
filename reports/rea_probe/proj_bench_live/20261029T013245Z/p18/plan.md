1. **Define Immutable State**: Extract the core goal, critical decisions, and key evidence into a structured "State Snapshot" (e.g., JSON or YAML) to ensure data integrity during compaction.
2. **Create Checkpoint Artifact**: Save the State Snapshot to a persistent file or external storage, ensuring it is independent of the active context window.
3. **Implement Resume Protocol**: Define a specific trigger or command that reads the checkpoint artifact and re-injects the state into the context upon resumption.
4. **Validate Continuity**: Execute a test cycle where the context is artificially compacted, then resume using the protocol to verify that the goal, decisions, and evidence remain intact and accessible.
