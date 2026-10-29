# Campaign: Inspect-Then-Browser

## Objective
Execute a two-lane campaign where Lane A performs static inspection and Lane B performs dynamic browsing, separated by a mandatory human gate to validate findings before proceeding.

## Lanes

### Lane A: Inspect
- **Scope**: Static analysis of codebase, configuration files, and dependency manifests.
- **Actions**:
  - Run linters and security scanners.
  - Identify potential vulnerabilities or misconfigurations.
  - Generate a report of findings.
- **Output**: `inspect_report.json`

### Lane B: Browser
- **Scope**: Dynamic interaction with the deployed application.
- **Actions**:
  - Navigate to target URLs.
  - Execute predefined user flows.
  - Capture screenshots and console logs.
- **Output**: `browser_results.json`

## Human Gate
- **Location**: Between Lane A and Lane B.
- **Trigger**: After Lane A completes and generates `inspect_report.json`.
- **Action**:
  - Human reviews `inspect_report.json`.
  - Human approves or rejects proceeding to Lane B.
  - If rejected, campaign halts and returns to Lane A for remediation.
  - If approved, Lane B begins execution.
- **Gate Status**: `pending` | `approved` | `rejected`

## Workflow
1. **Start Lane A**: Execute inspection tasks.
2. **Gate Check**: Pause and await human approval.
3. **Start Lane B**: If approved, execute browsing tasks.
4. **Final Report**: Combine outputs from both lanes.

## Constraints
- Lane B must not start until the gate is explicitly approved.
- Lane A and Lane B are strictly scoped to their respective tasks.
- No automated bypass of the human gate.
