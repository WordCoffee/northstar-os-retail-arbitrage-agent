# 24 — Event Catalog

Evidence states: INFERRED (I) from module ownership (`01`) and service specs. Specification only.

## 1. Event envelope

Every event: `{event_id, event_type, version, occurred_at, organization_id, actor, aggregate_type, aggregate_id, correlation_id, payload, provenance}`. Published to the domain event bus (Redis stream / outbox → consumer).

## 2. Domain events (producer → consumers)

| Event | Producer | Consumers |
|---|---|---|
| `user.created`, `session.revoked`, `org.changed` | identity | help, audit, notifications |
| `product.created`, `product.updated`, `identity.merged` | catalog | keyword, economics, opportunity, listing, advertising, social, monitoring, rival, brain |
| `normalization.done` | normalization | catalog, opportunity |
| `supplier.ingested`, `supplier.offer.updated` | supplier | opportunity, economics, brain |
| `snapshot.recorded` | market | economics, opportunity, monitoring, rival, rankledger |
| `economics.computed` | economics | opportunity, auctioneer, brain, hub |
| `opportunity.assessed`, `opportunity.approved`, `opportunity.dismissed`, `opportunity.assigned` | opportunity | hub, watch, approvals |
| `keyword.observed` | keyword | listing, advertising, social, rankledger, rival |
| `listing.drafted`, `listing.version.created`, `listing.approved`, `listing.published`, `listing.audited` | listing | hub, keyword, notifications |
| `campaign.changed`, `ad.performance.recorded`, `recommendation.generated` | advertising | hub, keyword, brain |
| `social.drafted`, `social.approved`, `social.scheduled`, `social.published`, `social.asset.uploaded` | social | hub, notifications |
| `alert.raised`, `watch.triggered` | monitoring | hub, notifications |
| `rival.observed`, `rival.alert.raised` | rival | hub |
| `brain.run_started`, `brain.step_completed`, `brain.approval_required`, `brain.run_completed`, `brain.run_failed`, `brain.artifact.created` | ai_orchestration | hub, ledger, notifications, approvals |
| `provider.status_changed`, `provider.budget_exhausted` | provider | hub, account, notifications |
| `usage.event.recorded`, `credits.adjusted`, `invoice.generated` | usage | ledger, hub, notifications |
| `approval.requested`, `approval.granted`, `approval.revoked` | approvals | hub, listing, social, advertising, brain |
| `tour.completed` | help | analytics |
| `preview.started`, `preview.ended` | identity/modes | audit |
| ALL | — | audit (subscriber) |

## 3. Event ordering and idempotency

- Consumers are idempotent by `event_id`; at-least-once delivery.
- Outbox pattern: domain writes emit events transactionally with the write.

## 4. Audit stream

- Every event is also persisted to `audit_event` (unified audit) with actor + organization; retention policy (owner Q13).

## 5. What this resolves

- Phase 0 `08`: no shared event bus / recommendations store → event-driven shared intelligence; shared recommendations derive from event consumers.
