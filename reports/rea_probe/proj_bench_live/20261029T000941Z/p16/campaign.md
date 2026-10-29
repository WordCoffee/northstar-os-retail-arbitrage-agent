# Campaign: Inspect-then-Browser

## Objective
Execute a two-lane campaign where Lane A performs static inspection and Lane B performs dynamic browsing, separated by a mandatory human gate.

## Lanes

### Lane A: Inspection
- **Scope**: Static analysis of target artifacts (code, configs, logs).
- **Actions**:
  1. Parse and validate target files.
  2. Generate inspection report.
  3. Flag anomalies for review.
- **Output**: `inspection_report.json`

### Gate: Human Review
- **Trigger**: After Lane A completes.
- **Action**: Human reviews `inspection_report.json`.
- **Decision**:
  - **Approve**: Proceed to Lane B.
  - **Reject**: Halt campaign; return to Lane A for re-inspection.
- **Status**: `pending_human_approval`

### Lane B: Browsing
- **Scope**: Dynamic interaction with target environment (web, API, UI).
- **Actions**:
  1. Initialize browser session.
  2. Execute predefined navigation paths.
  3. Capture screenshots and logs.
  4. Validate expected states.
- **Output**: `browsing_log.json`, `screenshots/`

## Workflow
1. **Start Lane A** → Generate inspection report.
2. **Gate** → Human approves or rejects.
3. **If Approved** → Start Lane B.
4. **If Rejected** → Return to Lane A.
5. **End** → Compile final report from both lanes.

## Constraints
- Lane B **must not** start without explicit human approval at the gate.
- Lane A and Lane B are strictly scoped: Lane A does not browse; Lane B does not inspect.
- All outputs are versioned and timestamped.
