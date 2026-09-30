"""Data-rights register + enforcement (Master Plan P4-T3).

Authoritative machine-readable register of the data sources actually present or
integrated, with per-use rights labels:

    ALLOWED | PROHIBITED | UNKNOWN

These are RIGHTS-STATUS labels — not card statuses and not data truth labels.
Rules enforced here:
  * Permission is NEVER inferred from possession, a free trial, a public page, or
    the ability to download.
  * Internal-use rights do NOT imply redistribution rights.
  * UNKNOWN or PROHIBITED external uses are BLOCKED, including customer display,
    exports, cross-tenant aggregates, and external-AI transmission.
  * Owner Test Mode does NOT bypass data rights (it grants permissions only).
  * Derived scores/summaries do not escape restrictions.

The register records evidence locations and unresolved questions; it does not
assert legal clearance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ALLOWED = "ALLOWED"
PROHIBITED = "PROHIBITED"
UNKNOWN = "UNKNOWN"

INTERNAL_ONLY = "INTERNAL_ONLY"
CUSTOMER_OK = "CUSTOMER_OK"
NOT_INTEGRATED = "NOT_INTEGRATED"

# Use keys
USE_INTERNAL = "internal_analysis"
USE_CUSTOMER = "customer_display"
USE_EXPORT = "export_download"
USE_REDISTRIBUTE = "redistribution_sublicense"
USE_DERIVED = "derived_analytics"
USE_EXTERNAL_AI = "external_ai"


@dataclass(frozen=True)
class DataSource:
    key: str
    provider: str
    dataset: str
    status: str                       # INTERNAL_ONLY | CUSTOMER_OK | NOT_INTEGRATED
    acquisition: str = ""
    acquired_at: str = "UNKNOWN"
    account_tier: str = "UNKNOWN"
    terms_url: str = "UNKNOWN"
    terms_version: str = "UNKNOWN"
    evidence_location: str = ""
    reviewed_at: str = "2026-09-29"
    retention_after_termination: str = "UNKNOWN"
    rights: dict = field(default_factory=dict)
    attribution: str = "UNKNOWN"
    deletion_requirements: str = "UNKNOWN"
    restrictions: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)


def _u(*uses):
    return {u: UNKNOWN for u in uses}


def _reg() -> dict:
    r = {}
    r["sellersprite_historical_export"] = DataSource(
        key="sellersprite_historical_export", provider="SellerSprite",
        dataset="ss_product_observations (one-time historical export)",
        status=INTERNAL_ONLY,
        acquisition="commercial export (historical); used via pipeline reader",
        acquired_at="UNKNOWN (historical)",
        account_tier="UNKNOWN (historical; NOT renewed)",
        terms_url="vendor terms not captured in-repo",
        evidence_location="companion fba-product-screener/data/products.db",
        retention_after_termination="UNKNOWN",
        rights={USE_INTERNAL: ALLOWED, USE_CUSTOMER: UNKNOWN, USE_EXPORT: UNKNOWN,
                USE_REDISTRIBUTE: UNKNOWN, USE_DERIVED: UNKNOWN, USE_EXTERNAL_AI: UNKNOWN},
        restrictions=["historical-only; no renewal/trial/live integration authorized"],
        unresolved=["customer display/export/redistribution/AI not reviewed",
                    "do not infer redistribution from internal use"])
    r["amazon_catalog_records"] = DataSource(
        key="amazon_catalog_records", provider="Amazon-derived (provenance unverified)",
        dataset="amazon_catalog_records (identity/catalog)",
        status=INTERNAL_ONLY,
        acquisition="derived crosswalk/catalog; source provenance not verified",
        acquired_at="UNKNOWN",
        terms_url="UNKNOWN",
        evidence_location="companion data/northstar.db (amazon_catalog_records)",
        rights=_u(USE_INTERNAL, USE_CUSTOMER, USE_EXPORT, USE_REDISTRIBUTE,
                  USE_DERIVED, USE_EXTERNAL_AI),
        restrictions=["Amazon-derived/INTERNAL_ONLY until counsel clears (no SP-API/Amazon automation)"],
        unresolved=["do not declare vendor resale chains without evidence",
                    "no automated Amazon or Seller Central access authorized"])
    r["costco_discovery"] = DataSource(
        key="costco_discovery", provider="Costco (public catalog/discovery data)",
        dataset="Costco catalog/prices/discovery candidates",
        status=INTERNAL_ONLY,
        acquisition="local discovery/catalog capture (historical)",
        acquired_at="UNKNOWN",
        terms_url="site terms not captured in-repo",
        evidence_location="repo data/ + Northstar_backend/data/ (Costco artifacts)",
        rights={USE_INTERNAL: ALLOWED, USE_CUSTOMER: UNKNOWN, USE_EXPORT: UNKNOWN,
                USE_REDISTRIBUTE: UNKNOWN, USE_DERIVED: UNKNOWN, USE_EXTERNAL_AI: UNKNOWN},
        restrictions=["no automated Amazon-domain scanning; no Seller Central"],
        unresolved=["customer display/redistribution not reviewed"])
    r["palletfly_historical"] = DataSource(
        key="palletfly_historical", provider="PalletFly (historical)",
        dataset="source listing/ASIN references",
        status=INTERNAL_ONLY,
        acquisition="historical list (present in companion artifacts)",
        acquired_at="UNKNOWN",
        terms_url="UNKNOWN",
        evidence_location="companion fba-product-screener data/",
        rights=_u(USE_INTERNAL, USE_CUSTOMER, USE_EXPORT, USE_REDISTRIBUTE,
                  USE_DERIVED, USE_EXTERNAL_AI),
        unresolved=["customer/export/redistribution not reviewed"])
    r["manual_observed_capture"] = DataSource(
        key="manual_observed_capture", provider="Owner (first-party observation)",
        dataset="manually observed pack price/dimension evidence",
        status=CUSTOMER_OK,
        acquisition="owner/manual capture recorded via provenance model",
        acquired_at="runtime",
        rights={USE_INTERNAL: ALLOWED, USE_CUSTOMER: ALLOWED, USE_EXPORT: ALLOWED,
                USE_REDISTRIBUTE: ALLOWED, USE_DERIVED: ALLOWED, USE_EXTERNAL_AI: UNKNOWN},
        unresolved=["external AI transmission requires separate provider approval"])

    # Planned providers — NOT integrated, rights UNKNOWN. Listed so no one
    # mistakes a plan for an operational source.
    for key, prov, ds in [
        ("dataforseo", "DataForSEO", "market data (planned)"),
        ("brightdata", "Bright Data", "web data (planned; frozen files exist)"),
        ("keepa", "Keepa", "Amazon price history (planned)"),
        ("amazon_sp_api", "Amazon SP-API", "seller data (planned; NOT authorized)"),
        ("amazon_ads", "Amazon Ads API", "ads data (planned; NOT authorized)"),
        ("image_generation", "image provider (planned)", "creative assets (planned)"),
        ("email", "transactional email (planned)", "invites (planned)"),
        ("stripe", "Stripe (planned)", "billing (planned; test mode only, not integrated)"),
    ]:
        r[key] = DataSource(key=key, provider=prov, dataset=ds, status=NOT_INTEGRATED,
                            acquisition="not integrated", evidence_location="",
                            rights=_u(USE_INTERNAL, USE_CUSTOMER, USE_EXPORT,
                                      USE_REDISTRIBUTE, USE_DERIVED, USE_EXTERNAL_AI),
                            unresolved=["not integrated; no rights implied"])
    return r


SOURCES = _reg()


def rights(source_key: str, use: str) -> str:
    src = SOURCES.get(source_key)
    if src is None:
        return UNKNOWN
    return src.rights.get(use, UNKNOWN)


def external_use_allowed(source_key: str, use: str) -> bool:
    """External uses require an explicit ALLOWED; UNKNOWN/PROHIBITED are blocked."""
    if use == USE_INTERNAL:
        return rights(source_key, use) == ALLOWED
    return rights(source_key, use) == ALLOWED


def customer_display_allowed(source_key: str) -> bool:
    return external_use_allowed(source_key, USE_CUSTOMER)


def export_allowed(source_key: str) -> bool:
    return external_use_allowed(source_key, USE_EXPORT)


class DataRightsError(RuntimeError):
    def __init__(self, code: str, message: str = "", *, source: str = "", use: str = ""):
        super().__init__(message or code)
        self.code = code
        self.source = source
        self.use = use


def assert_customer_display(source_key: str) -> None:
    if not customer_display_allowed(source_key):
        raise DataRightsError("customer_display_blocked",
                              f"customer display not permitted for {source_key}",
                              source=source_key, use=USE_CUSTOMER)


def assert_export(source_key: str) -> None:
    if not export_allowed(source_key):
        raise DataRightsError("export_blocked",
                              f"export not permitted for {source_key}",
                              source=source_key, use=USE_EXPORT)


def assert_external_ai(source_key: str) -> None:
    if not external_use_allowed(source_key, USE_EXTERNAL_AI):
        raise DataRightsError("external_ai_blocked",
                              f"external-AI transmission not permitted for {source_key}",
                              source=source_key, use=USE_EXTERNAL_AI)


def customer_safe_rows(rows: list, *, source_key_of=None, default_source: Optional[str] = None) -> list:
    """Filter rows to those whose source permits customer display.

    ``source_key_of`` maps a row -> source key; if omitted, ``default_source``
    (or each row's ``source`` field) is used. Rows from UNKNOWN/PROHIBITED
    sources are EXCLUDED. Independent of Owner Test Mode.
    """
    out = []
    for r in rows:
        key = None
        if source_key_of is not None:
            key = source_key_of(r)
        elif isinstance(r, dict):
            key = r.get("source") or default_source
        else:
            key = default_source
        if key and customer_display_allowed(key):
            out.append(r)
    return out


def export_safe_rows(rows: list, *, source_key_of=None, default_source: Optional[str] = None) -> list:
    out = []
    for r in rows:
        key = source_key_of(r) if source_key_of is not None else (
            r.get("source") if isinstance(r, dict) else default_source) or default_source
        if key and export_allowed(key):
            out.append(r)
    return out