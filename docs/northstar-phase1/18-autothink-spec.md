# 18 — AutothinK Specification

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / INFERRED (I). Specification only.

## 1. Primary user job

Run AI-driven research, creation, and automation as auditable, budgeted, resumable agentic runs.

## 2. Entry points

- `/autothink` (workbench), `/autothink/runs/:runId` (run detail).

## 3. Main workspace (agentic workbench, not a single textarea)

| Section | Content |
|---|---|
| Objective | natural-language objective |
| Plan | generated plan (steps, tools, estimated cost) |
| Tool selection | tools from registry (catalog lookup, supplier match, economics, keyword research, listing draft, social draft, monitor check) |
| Execution | multi-step timeline; intermediate results; per-step status |
| Artifacts | files produced (listings, captions, plans, reports) |
| Approvals | checkpoints for write_external/purchase/cost-above-budget |
| Cost | per-step estimate + running total; budget cap |
| Runs | history; resume/cancel/retry |
| Audit | full run audit trail |

## 4. Workflow

1. Enter objective.
2. Brain plans (tool selection + cost estimate).
3. User approves plan (or adjusts).
4. Execute steps (local LLM default; cloud gated).
5. Approval checkpoints pause run when a sensitive step is reached.
6. Resume after approval; produce artifacts; finish with summary + audit.

## 5. Model routing

- Local Ollama default (free); cloud OpenRouter gated (`CLOUD_MODEL_LIVE=1` + per-org provider config); tier consent T1→T2→T3 (reuse `model_router`).

## 6. Actions

| Action | Gate |
|---|---|
| Run local generation | local, credited 0 |
| Run cloud generation | provider gated + budget |
| Tool call (read) | read gates |
| Tool call (write_external) | approval checkpoint |
| Purchase step | blocked (manual purchase) |
| Schedule recurring run | none (but every run gated by its steps) |

## 7. States

- Loading: plan estimation; step skeletons.
- Awaiting approval: run paused at checkpoint with cost/diff summary.
- Provider failure: step error + bounded retry; never fabricated; run resumes or fails cleanly.
- Permission denied: tool not permitted for role.
- Cancelled: partial results preserved; audit records cancellation.

## 8. Responsive

Workbench → single column on mobile; run timeline readable.

## 9. Tour steps

1. Enter an objective.
2. Review the plan + cost estimate.
3. Watch execution timeline.
4. Handle an approval checkpoint.
5. Open an artifact.

## 10. Events

Emits: `brain.run_started`, `brain.step_completed`, `brain.approval_required`, `brain.run_completed`, `brain.run_failed`, `brain.artifact.created`. Consumes: domain events (context), `usage.event.recorded`.

## 11. Downstream

- All services (artifacts/runs feed Hub activity, Ledger cost, notifications, approvals).

## 12. Tool registry + cost

- Tool contract per `04`. Cost estimation per step using pricing policy (`07`); every step records usage_event.

## 13. What this resolves

- Phase 0 finding: "Decision Run does nothing beyond submitting text" → full agentic lifecycle with planning, tools, artifacts, checkpoints, persistence, cost, audit.
