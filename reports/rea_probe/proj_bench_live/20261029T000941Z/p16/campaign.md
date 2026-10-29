```markdown
# Campaign: Inspect-Then-Browser

## Objective
Execute a two-lane campaign where Lane A performs static inspection of target assets, and Lane B performs dynamic browser interaction. A mandatory human gate separates the lanes to ensure inspection findings are validated before proceeding to browser actions.

## Lanes

### Lane A: Inspect
- **Scope**: Static analysis of target URLs, headers, and metadata.
- **Actions**:
  - Fetch target URLs.
  - Record HTTP status codes and headers.
  - Extract metadata (e.g., titles, descriptions).
  - Log findings to `inspect_results.json`.
- **Exit Condition**: All targets inspected and results logged.

### Gate: Human Validation
- **Requirement**: A human must review `inspect_results.json` and explicitly approve proceeding to Lane B.
- **Action**:
  - Review findings for anomalies or risks.
  - Set `gate_approved = true` in `campaign_state.json`.
- **Exit Condition**: `gate_approved` is `true`.

### Lane B: Browser
- **Scope**: Dynamic interaction with approved targets.
- **Actions**:
  - Launch browser session.
  - Navigate to approved targets.
  - Perform scripted interactions (e.g., clicks, form submissions).
  - Capture screenshots and console logs.
  - Log results to `browser_results.json`.
- **Exit Condition**: All approved targets processed and results logged.

## Workflow
1. **Start Lane A**: Execute inspection tasks.
2. **Gate**: Pause campaign. Human reviews `inspect_results.json` and sets `gate_approved = true`.
3. **Start Lane B**: Execute browser tasks only if `gate_approved` is `true`.

## State Management
- `campaign_state.json`:
  - `lane_a_status`: "pending" | "completed"
  - `gate_approved`: false
  - `lane_b_status`: "pending" | "completed"

## Constraints
- Lane B must not start until the gate is approved.
- Lane A and Lane B are strictly scoped to their respective actions.
- All results must be logged to JSON files for auditability.
```
