# 11 — Operations Hub Specification

Evidence states: INFERRED (I) from Phase 0 `04` + owner directive. Specification only.

## 1. Primary user job

Answer "what needs my attention across my entire operation right now" and route to the right action. Actionable command center — not a static dashboard.

## 2. Widgets (customizable)

| Widget | Source (canonical) | Content |
|---|---|---|
| Portfolio health | portfolio read-model (economics + snapshots) | profit/ROI/margin health, BSR health |
| Opportunity pipeline | opportunity_assessment | qualified counts by tier, funnel |
| Listings needing attention | listing (compliance/health) | alerts |
| Advertising alerts | advertising + performance snapshots | ACoS overages, negative harvest candidates |
| Monitoring alerts | alert (watch/rank/rival) | price/rank/seller signals |
| Social schedule | social_content calendar | upcoming/approved/due posts |
| AutothinK activity | brain_run | running/queued/recent runs |
| Approval queue | approval_request | pending approvals (with cost/diff) |
| Integration health | provider_registry | per-provider status + budget remaining |
| Credit/spend posture | usage projection | balance, consumed, run-rate |
| Failed jobs | refresh_job dead-letter | failed jobs with retry |
| Recommended next actions | recommendation engine (opportunity + monitoring) | prioritized actions |
| Recent activity | audit_event (recent) | last actions across org |

## 3. Workflow

- Entry: `/` → Hub.
- Load: aggregate read-model (async prefetch); skeleton states per widget.
- Widget customization: add/remove/reorder; per-user persistence (DB); responsive stacking.
- Drill-down: every widget row → the owning service (`/prospector/:id`, `/auctioneer/campaigns/:id`, etc.).
- Actions: one primary action per alert (e.g., "Review opportunity", "Approve listing draft", "Re-run job").

## 4. States

- Empty: no org data → onboarding CTA (connect provider/run first scan).
- Loading: per-widget skeletons.
- Partial: widgets with no data show "No data yet" + CTA; never fabricated numbers.
- Stale: banner "some widgets stale as of <t>"; refresh action explicit.
- Provider failure: widget-level error + retry (bounded); integration-health widget shows degraded.
- Permission denied: widget hidden or "requires role" if sensitive.

## 5. Responsive

- Desktop: grid of widgets (customizable layout, 3–4 cols).
- Tablet: 2 cols; Mobile: single column, widget menu drawer.
- Keyboard: widget menu focusable; palette opens widgets.

## 6. Tour steps

1. "This is your command center" — widget grid.
2. "Add/remove widgets" — customization.
3. "Approval queue" — review a pending approval.
4. "Drill into a service" — open Prospector from a pipeline widget.
5. "Integration health" — check providers.

## 7. Events

Emits: `hub.widget.customized`, `hub.alert.acknowledged`, `hub.action.launched`. Consumes: all widget-source events.

## 8. Downstream

- Routes to every service; approval widget links to `approvals` module; alerts link to monitoring.

## 9. Gates/integrations/authorizations

- **Moved to Account** (owner directive). Hub only surfaces an operational exception alert (e.g., provider down, budget exhausted) via integration-health widget.

## 10. Answers the five questions

- What happened → widget summary with counts/timestamps.
- Why it matters → per-alert rationale.
- What evidence → source + captured_at + provenance on each widget.
- What next → primary action per widget.
- If you act → links to the owning service workflow; approval actions open the approval modal (cost estimate + diff).
