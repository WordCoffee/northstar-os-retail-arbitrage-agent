"""Supplier pipeline — orchestrates discover → ingest → analyze → persist.

Wires together the supplier intelligence modules:
  1. discover     SupplierDiscoveryScraper (offline seed by default)
  2. ingest       SupplierCatalogIngestion (CSV / HTML / URL)
  3. analyze      SupplierCostBenefitAnalyzer (pre-account economics)
  4. persist      SuppliersDB (suppliers, supplier_products, analyses)

The pipeline is offline by default and never makes a live call without the
named approval gates for discovery (SUPPLIER_DISCOVERY_LIVE_OPERATOR_APPROVED)
and catalog fetch (SUPPLIER_CATALOG_LIVE_OPERATOR_APPROVED) plus injected
transports.

``PipelineResult`` carries everything the UI needs: persisted supplier ids,
product counts, and per-product analysis rows (viable/marginal/reject counts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from data_layer import SuppliersDB, get_db
from scrapers.supplier_discovery import SupplierDiscoveryScraper
from scrapers.supplier_catalog_ingestion import (
    CatalogIngestResult,
    SupplierCatalogIngestion,
    parse_csv_bytes,
    parse_html_catalog,
)
from analysis.supplier_cost_benefit import (
    MANUAL_REVIEW,
    MARGINAL,
    REJECT,
    VIABLE,
    CostBenefitResult,
    SupplierCostBenefitAnalyzer,
)


@dataclass
class PipelineResult:
    """Full pipeline output for one supplier."""

    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    discovered: bool = False
    ingest: Optional[CatalogIngestResult] = None
    analyses: List[Dict[str, Any]] = field(default_factory=list)
    product_count: int = 0
    viable_count: int = 0
    marginal_count: int = 0
    reject_count: int = 0
    review_count: int = 0
    errors: List[str] = field(default_factory=list)
    mode: str = "offline"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "discovered": self.discovered,
            "ingest": self.ingest.as_dict() if self.ingest else None,
            "analyses": self.analyses,
            "product_count": self.product_count,
            "viable_count": self.viable_count,
            "marginal_count": self.marginal_count,
            "reject_count": self.reject_count,
            "review_count": self.review_count,
            "errors": self.errors,
            "mode": self.mode,
        }


class SupplierPipeline:
    """End-to-end supplier intelligence pipeline."""

    def __init__(
        self,
        db: Optional[SuppliersDB] = None,
        discovery: Optional[SupplierDiscoveryScraper] = None,
        ingestion: Optional[SupplierCatalogIngestion] = None,
        analyzer: Optional[SupplierCostBenefitAnalyzer] = None,
    ) -> None:
        self.db = db or SuppliersDB(get_db())
        self.discovery = discovery or SupplierDiscoveryScraper()
        self.ingestion = ingestion or SupplierCatalogIngestion()
        self.analyzer = analyzer or SupplierCostBenefitAnalyzer()

    # -- persistence --------------------------------------------------------

    def save_discovered_supplier(self, profile_dict: Dict[str, Any]) -> Optional[str]:
        """Persist a discovered supplier profile; returns its id."""
        try:
            return self.db.upsert(profile_dict)
        except Exception as exc:
            self.last_error = f"Supplier persist failed: {exc}"  # type: ignore[attr-defined]
            return None

    # -- full flow ----------------------------------------------------------

    def run(
        self,
        category_slug: str,
        keywords: Optional[List[str]] = None,
        supplier_profile: Optional[Dict[str, Any]] = None,
        persist_supplier: bool = True,
        amazon_price_lookup: Optional[Callable[[str], Optional[float]]] = None,
    ) -> PipelineResult:
        """Run discover (or accept a supplied profile) → persist → analyze.

        ``amazon_price_lookup`` is an optional callable ``product_name ->
        amazon_price`` used to analyze every ingested product against a price;
        when omitted, analyses are persisted with a manual-review flag (the
        dashboard can backfill prices later).
        """
        self.last_error: Optional[str] = None  # type: ignore[attr-defined]
        result = PipelineResult(mode="offline")

        # --- discover / accept --------------------------------------------
        profile = supplier_profile
        if profile is None:
            discovered = self.discovery.discover(category_slug, keywords, mode="offline")
            if discovered:
                profile = discovered[0].as_dict()
                result.discovered = True
        if profile is None:
            result.errors.append(f"No supplier found for category '{category_slug}'.")
            return result

        result.supplier_name = profile.get("name")
        result.supplier_id = profile.get("id")
        if persist_supplier and result.supplier_id:
            self.db.upsert(profile)

        # --- ingest (products from the profile's catalog when available) ---
        # Offline path: no catalog bytes are available, so we seed the
        # supplier with zero products and the caller wires CSV/HTML via
        # ingest_products(). If the profile carries a public catalog URL and
        # the operator armed the live gate + injected a fetch_fn, attempt it.
        if self.ingestion.live_armed() and self.ingestion.fetch_fn and profile.get("public_catalog_url"):
            ingest = self.ingestion.ingest_url(result.supplier_id or "", profile["public_catalog_url"])
            result.mode = "live"
        else:
            ingest = CatalogIngestResult(supplier_id=result.supplier_id or "")
        result.ingest = ingest

        # --- analyze + persist products -----------------------------------
        for product in ingest.products:
            pid = self.db.add_product(result.supplier_id or "", product)
            amazon_price = None
            if amazon_price_lookup:
                try:
                    amazon_price = amazon_price_lookup(product.get("product_name") or "")
                except Exception:
                    amazon_price = None
            match = {"asin": None, "amazon_price": amazon_price} if amazon_price else None
            analysis = self.analyzer.analyze(product, match)
            self.db.add_cost_analysis(pid, analysis.as_dict())
            result.analyses.append(analysis.as_dict())
            result.product_count += 1
            flag = analysis.decision_flag
            if flag == VIABLE:
                result.viable_count += 1
            elif flag == MARGINAL:
                result.marginal_count += 1
            elif flag == REJECT:
                result.reject_count += 1
            else:
                result.review_count += 1

        return result

    def ingest_products(
        self,
        supplier_id: str,
        products: List[Dict[str, Any]],
        amazon_price_lookup: Optional[Callable[[str], Optional[float]]] = None,
    ) -> PipelineResult:
        """Persist a pre-parsed product list and analyze each one."""
        result = PipelineResult(supplier_id=supplier_id, mode="offline")
        for product in products:
            pid = self.db.add_product(supplier_id, product)
            amazon_price = None
            if amazon_price_lookup:
                try:
                    amazon_price = amazon_price_lookup(product.get("product_name") or "")
                except Exception:
                    amazon_price = None
            match = {"asin": None, "amazon_price": amazon_price} if amazon_price else None
            analysis = self.analyzer.analyze(product, match)
            self.db.add_cost_analysis(pid, analysis.as_dict())
            result.analyses.append(analysis.as_dict())
            result.product_count += 1
            flag = analysis.decision_flag
            if flag == VIABLE:
                result.viable_count += 1
            elif flag == MARGINAL:
                result.marginal_count += 1
            elif flag == REJECT:
                result.reject_count += 1
            else:
                result.review_count += 1
        return result


def run_supplier_pipeline(**kwargs: Any) -> PipelineResult:
    """Module-level convenience."""
    return SupplierPipeline().run(**kwargs)