# 22 — Account and Onboarding Specification

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Account sections (production-ready control center)

| Section | Content |
|---|---|
| Profile | name, email, password, MFA |
| Organization | org name, plan, billing address |
| Plan & Billing | plan tier, included credits, invoices, payment method (owner Q3) |
| Credits & Usage | derived balance, consumption, breakdown (see `12`) |
| Team & Roles | members, roles (customer/operator/admin), invites |
| Security & Sessions | sessions, revocation, MFA, JWT rotation |
| Notifications | delivery preferences per channel |
| Connections | Amazon account, Amazon Ads, social (Meta/TikTok/IG), suppliers, AI providers (local/cloud), GitHub/Cloudflare (owner Q) |
| AI Providers | per-provider enable/disable, model selection, budget caps, sandbox vs prod routing |
| Brand Voice | single shared brand voice store (resolves Phase 0 triplication) |
| Data & Privacy | data export, retention, deletion requests |
| Audit Log | unified audit query (org-scoped) |
| Modes & Customer Preview | environment (sandbox/prod) indicator, preview entry with persistent banner + reauthorization (see `05`) |
| Help & Tours | replay tours, documentation links, contextual help |

## 2. Connections security

- Credentials NEVER stored in browser. Backend stores reference-only; secret values in secret store.
- Connection health/permissions display; revoke flows; re-auth for expired grants.

## 3. Authorization posture (real, not presentation)

- Phase 0 finding: "Authorization Posture" badges were presentation-only. New design: badges render real gate/approval state from provider_registry + approvals; clicking a badge opens the real connection/gate config (not a toast).

## 4. Onboarding (tours)

| Feature | Spec |
|---|---|
| First-entry tour per service | yes (11 services + Account) |
| Skip / Back / Next | yes |
| Don't show again | per user, persisted (DB) |
| Replay from Help | yes |
| Per-user per-service completion | `tour_completion` table |
| Role-sensitive steps | operator/admin steps differ from customer |
| Analytics | tour start/completion/drop-off events |

## 5. Tour infrastructure

- `help` module: `help_content`, `tour_completion`; API `/api/v1/help/tours` (list), `POST /api/v1/help/tours/{id}/complete`, `GET /api/v1/help/context?route=` (contextual help).
- Frontend: tour driver component; first-run gating by `tour_completion`.

## 6. Mode/preview controls (in Account)

- Environment indicator + sandbox/production selector (tenant-scoped, audited).
- Customer preview entry: pick target org/user; persistent banner; entry/exit/actions logged; sensitive actions reauthorized; no production writes while previewing; no impersonation (owner decision `00`).

## 7. Responsive

Account = settings-panel layout; tabs → stacked accordion on mobile.

## 8. Tour steps

1. Complete your profile.
2. Connect your first provider.
3. Set brand voice.
4. Invite a team member.
5. Try customer preview (operator).

## 9. Events

Emits: `user.updated`, `org.changed`, `connection.changed`, `provider.status_changed`, `tour.completed`, `preview.started`, `preview.ended`. Consumes: auth/session events.

## 10. Downstream

- All services (connections, brand voice, permissions, providers).
