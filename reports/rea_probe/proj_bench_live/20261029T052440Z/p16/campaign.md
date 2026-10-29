# Campaign: Inspect-Then-Browser

## Objective
Execute a two-lane campaign where Lane A performs static inspection and Lane B performs dynamic browsing, separated by a mandatory human gate.

## Lanes

### Lane A: Inspection
- **Scope**: Static analysis, code review, configuration audit.
- **Actions**:
  - Run linters and static analyzers.
  - Review dependency manifests.
  - Generate inspection report.
- **Output**: `inspection_report.json`

### Lane B: Browsing
- **Scope**: Dynamic interaction, UI validation, runtime behavior.
- **Actions**:
  - Launch headless browser.
  - Execute scripted navigation and interaction.
  - Capture screenshots and console logs.
- **Output**: `browser_results.json`

## Human Gate
- **Location**: Between Lane A and Lane B.
- **Trigger**: Automatic pause after Lane A completion.
- **Requirement**: Human must review `inspection_report.json` and explicitly approve proceeding to Lane B.
- **Mechanism**:
  - System halts and prompts: "Review inspection report. Type 'approve' to proceed to Lane B."
  - Lane B does not start until explicit approval is received.

## Execution Flow
1. Start Lane A.
2. Complete Lane A → Generate `inspection_report.json`.
3. **GATE**: Pause. Await human approval.
4. If approved → Start Lane B.
5. Complete Lane B → Generate `browser_results.json`.
6. End campaign.

## Constraints
- Lane B must not execute without human approval.
- Lane A and Lane B are strictly scoped to their respective domains (static vs. dynamic).
- No automated bypass of the gate.
