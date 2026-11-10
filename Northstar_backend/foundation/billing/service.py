"""Billing service — test-mode, redirect-based, exactly-once (1C-06 / Phase A).

- Hosted checkout only (redirect), no embedded card fields.
- Stores ONLY processor customer/subscription/price IDs + status — never card
  data.
- Webhook-driven settlement reusing the existing exactly-once ledger pattern,
  keyed on the processor event ID (billing_events UNIQUE + usage_events
  `billing:{event_id}` UNIQUE), with HMAC signature verification.
- Downgrade/cancel/non-payment refreshes entitlements so gated features are
  revoked on the next entitlement check.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Optional

from ..audit import AuditService
from ..context import RequestContext
from ..models import (
    BillingCustomer, BillingEvent, CheckoutSession, Subscription,
    UsageEvent, utcnow,
)
from ..repositories import Repositories
from ..enums import CostKind, UsageEventStatus
from . import processor as proc
from . import tiers as tiers_mod
from .entitlements import EntitlementService


class BillingError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class BillingService:
    def __init__(self, repos: Repositories, *,
                 entitlements: Optional[EntitlementService] = None,
                 audit: Optional[AuditService] = None) -> None:
        self.repos = repos
        self.entitlements = entitlements or EntitlementService(repos)
        self.audit = audit or AuditService(repos)

    # -- Phase A: checkout (redirect-based, hosted) ---------------------------

    def create_checkout(self, ctx: RequestContext, *, price_id: str) -> dict:
        org_id = ctx.effective_organization_id
        if not org_id:
            raise BillingError("no_organization")
        if not tiers_mod.is_known_price(price_id):
            raise BillingError("unknown_price", "unknown price id")
        session = CheckoutSession(
            organization_id=org_id, price_id=price_id,
            tier=tiers_mod.price_tier(price_id), status="open",
            expires_at=utcnow() + timedelta(hours=2))
        row = self.repos.checkout_sessions.add(session)
        # redirect-based hosted checkout (no card fields anywhere)
        return {
            "checkout_id": row["id"],
            "redirect_url": f"/api/v1/foundation/billing/checkout/{row['id']}",
            "mode": "redirect_hosted", "test_mode": True,
        }

    def checkout_page(self, checkout_id: str) -> dict:
        cs = self.repos.checkout_sessions.get(checkout_id)
        if cs is None or cs["status"] != "open":
            raise BillingError("checkout_not_found", "checkout session unavailable")
        price = tiers_mod.PRICES.get(cs["price_id"], {})
        return {
            "checkout_id": checkout_id,
            "price_label": price.get("label", cs["price_id"]),
            "tier": cs["tier"],
            "test_mode": True,
            "card_fields": False,
            "confirm_label": "Confirm test subscription (no card required)",
        }

    # -- Phase A: webhook-driven settlement (exactly-once) ---------------------

    def handle_webhook(self, payload: dict, signature: str) -> dict:
        if not proc.verify_signature(payload, signature, proc.webhook_secret()):
            raise BillingError("invalid_signature", "webhook signature invalid")
        event_id = payload.get("id")
        if not event_id:
            raise BillingError("missing_event_id")
        event_type = payload.get("type", "")
        existing = self.repos.billing_events.by_processor_event_id(event_id)
        if existing:
            # exactly-once: already processed
            return {"status": "already_processed", "event_id": event_id}
        # idempotent claim (UNIQUE processor_event_id) — concurrent duplicates
        # race; the loser is detected below and treated as already-processed.
        event = BillingEvent(
            processor_event_id=event_id, event_type=event_type,
            payload_hash=proc.payload_hash(payload), status="processed",
            processed_at=utcnow())
        try:
            self.repos.billing_events.add(event)
        except Exception:  # noqa: BLE001 - unique race
            again = self.repos.billing_events.by_processor_event_id(event_id)
            if again:
                return {"status": "already_processed", "event_id": event_id}
            raise
        try:
            self._apply_event(event_type, payload)
        except Exception as e:  # noqa: BLE001 - record failure, never roll back
            self.repos.db.conn.execute(
                "UPDATE billing_events SET status='failed' WHERE processor_event_id=?",
                (event_id,))
            self.repos.db.conn.commit()
            raise BillingError("webhook_failed", f"{type(e).__name__}: {e}")
        return {"status": "processed", "event_id": event_id}

    def _apply_event(self, event_type: str, payload: dict) -> None:
        if event_type == "checkout.session.completed":
            self._on_checkout_completed(payload)
        elif event_type == "customer.subscription.updated":
            self._on_subscription_updated(payload)
        elif event_type in ("invoice.payment_failed",
                            "customer.subscription.deleted"):
            self._on_payment_failed(payload)
        else:
            # unknown event types are recorded but ignored
            return

    def _on_checkout_completed(self, payload: dict) -> None:
        cs = self.repos.checkout_sessions.get(payload.get("checkout_session_id"))
        if cs is None:
            raise BillingError("checkout_not_found")
        if cs["status"] != "open":
            return
        org_id = cs["organization_id"]
        customer = self.repos.billing_customers.for_org(org_id)
        if customer is None:
            customer = self.repos.billing_customers.add(BillingCustomer(
                organization_id=org_id, processor="test",
                processor_customer_id=payload.get("customer_id") or f"cus_test_{org_id[:8]}"))
        self.repos.db.conn.execute(
            "UPDATE checkout_sessions SET status='completed' WHERE id=?", (cs["id"],))
        sub = Subscription(
            organization_id=org_id, billing_customer_id=customer["id"],
            processor_subscription_id=payload.get("subscription_id")
            or f"sub_test_{org_id[:8]}",
            price_id=cs["price_id"], tier=cs["tier"], status="active",
            current_period_end=payload.get("current_period_end"))
        sub_row = self.repos.subscriptions.add(sub)
        # settle on the existing exactly-once ledger (keyed on the event id)
        self._settle(org_id, cs["price_id"], payload["id"], cs["tier"])
        self.entitlements.refresh(org_id)
        self.audit.record(action="billing.subscription.settled",
                          actor_user_id=None, organization_id=org_id,
                          resource_type="subscription", resource_id=sub_row["id"],
                          correlation_id=payload.get("correlation_id"),
                          after_meta={"tier": cs["tier"], "price_id": cs["price_id"],
                                      "test_mode": True})

    def _settle(self, org_id: str, price_id: str, event_id: str, tier: str) -> None:
        """Exactly-once ledger settlement keyed on the processor event id."""
        key = f"billing:{event_id}"
        existing = self.repos.usage.find({"idempotency_key": key})
        if existing:
            return
        price = tiers_mod.PRICES.get(price_id, {})
        amount = Decimal(str(price.get("amount", "0.00")))
        conn = self.repos.db.conn
        try:
            conn.execute(
                "UPDATE org_balances SET granted = granted + ?, updated_at = ? "
                "WHERE organization_id = ?",
                (float(amount), utcnow().isoformat(), org_id))
            conn.execute(
                "INSERT INTO org_balances (organization_id, granted, reserved, consumed, updated_at) "
                "SELECT ?, ?, 0, 0, ? WHERE NOT EXISTS (SELECT 1 FROM org_balances WHERE organization_id = ?)",
                (org_id, float(amount), utcnow().isoformat(), org_id))
            ev = UsageEvent(
                organization_id=org_id, service="billing:subscription",
                provider="test", provider_reported_cost=float(amount),
                credits_debited_shadow=float(amount),
                cost_kind=CostKind.REPORTED.value,
                status=UsageEventStatus.FINALIZED.value,
                idempotency_key=key, reversal_ref=event_id,
                environment="production",
                provenance={"kind": "billing_settlement", "event_id": event_id,
                            "tier": tier, "test_mode": True})
            self.repos.db.insert_no_commit("usage_events",
                                           {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                                            for k, v in __import__("dataclasses").asdict(ev).items()})
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            existing = self.repos.usage.find({"idempotency_key": key})
            if existing:
                return
            raise

    def _on_subscription_updated(self, payload: dict) -> None:
        sub = self.repos.subscriptions.by_processor_id(payload.get("subscription_id"))
        if sub is None:
            return
        status = payload.get("status") or sub["status"]
        self.repos.db.conn.execute(
            "UPDATE subscriptions SET status=?, current_period_end=?, updated_at=? "
            "WHERE id=?", (status, payload.get("current_period_end"),
                           utcnow().isoformat(), sub["id"]))
        self.repos.db.conn.commit()
        self.entitlements.refresh(sub["organization_id"])

    def _on_payment_failed(self, payload: dict) -> None:
        sub = self.repos.subscriptions.by_processor_id(payload.get("subscription_id"))
        if sub is None:
            return
        status = "canceled" if payload.get("type") == "customer.subscription.deleted" \
            else "unpaid"
        self.repos.db.conn.execute(
            "UPDATE subscriptions SET status=?, updated_at=? WHERE id=?",
            (status, utcnow().isoformat(), sub["id"]))
        self.repos.db.conn.commit()
        # revoke gated features on the next entitlement check
        self.entitlements.refresh(sub["organization_id"])
        self.audit.record(action="billing.subscription.revoked",
                          organization_id=sub["organization_id"],
                          resource_type="subscription", resource_id=sub["id"],
                          after_meta={"status": status, "test_mode": True})

    # -- Phase B: cancellation (owner) -----------------------------------------

    def cancel(self, ctx: RequestContext, *, reason: str = "operator cancelled") -> dict:
        org_id = ctx.effective_organization_id
        if not org_id:
            raise BillingError("no_organization")
        sub = self.repos.subscriptions.active_for_org(org_id)
        if sub is None:
            raise BillingError("no_subscription")
        self.repos.db.conn.execute(
            "UPDATE subscriptions SET status='canceled', updated_at=? WHERE id=?",
            (utcnow().isoformat(), sub["id"]))
        self.repos.db.conn.commit()
        self.entitlements.refresh(org_id)
        self.audit.record(action="billing.subscription.cancel",
                          actor_user_id=ctx.user_id, organization_id=org_id,
                          resource_type="subscription", resource_id=sub["id"],
                          after_meta={"reason": reason, "test_mode": True})
        return {"status": "canceled", "tier": sub["tier"]}

    def status(self, org_id: str) -> dict:
        sub = self.repos.subscriptions.active_for_org(org_id)
        ent = self.entitlements.entitlements_for_org(org_id)
        return {
            "subscription": {"status": sub["status"] if sub else "none",
                             "tier": sub["tier"] if sub else ent["tier"],
                             "price_id": sub["price_id"] if sub else None},
            "entitlements": ent,
            "test_mode": True,
        }