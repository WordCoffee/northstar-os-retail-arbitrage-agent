"""Canonical product identity resolution (owner decision 2).

Providers submit candidate identifiers/observations; the Catalog module resolves
them. Ambiguous identities are NEVER silently merged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .enums import IdentifierKind, IdentityResolution
from .models import (
    CatalogProduct, ProductIdentifier, PackConfig, UnresolvedCandidate,
    IdentityConflict, Marketplace,
)
from .repositories import Repositories

_ASIN_RE = re.compile(r"^[0-9A-Z]{10}$")
_DIGITS_RE = re.compile(r"\D")


def normalize_asin(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    v = raw.strip().upper()
    return v or None


def valid_asin(raw: Optional[str]) -> bool:
    v = normalize_asin(raw)
    return bool(v and _ASIN_RE.match(v))


def normalize_digit_identifier(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = _DIGITS_RE.sub("", raw)
    return digits or None


def normalize_identifier(kind: str, raw: Optional[str]) -> Optional[str]:
    if kind == IdentifierKind.ASIN.value:
        return normalize_asin(raw)
    return normalize_digit_identifier(raw)


@dataclass
class IdentitySubmission:
    """A provider/job submission requesting identity resolution."""
    marketplace_id: str
    asin: Optional[str] = None
    identifiers: list[tuple[str, str]] = field(default_factory=list)  # (kind, raw)
    title: Optional[str] = None
    brand: Optional[str] = None
    source: str = "provider"
    source_identifier: Optional[str] = None
    pack_count: Optional[int] = None
    pack_unit: Optional[str] = None
    pack_ambiguous: bool = False
    variation_family_ref: Optional[str] = None


@dataclass
class ResolutionResult:
    resolution: str
    product_id: Optional[str] = None
    candidate_id: Optional[str] = None
    conflict_id: Optional[str] = None
    detail: str = ""


class IdentityResolver:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    def submit(self, sub: IdentitySubmission) -> ResolutionResult:
        # 1. Validate/normalize ASIN.
        asin = normalize_asin(sub.asin)
        if sub.asin and not valid_asin(sub.asin):
            cand = UnresolvedCandidate(
                raw_asin=sub.asin, raw_title=sub.title,
                reason="invalid_asin_format", source=sub.source,
                source_identifier=sub.source_identifier,
            )
            self.repos.candidates.add(cand)
            return ResolutionResult(
                resolution=IdentityResolution.UNRESOLVED_CANDIDATE.value,
                candidate_id=cand.id,
                detail="ASIN failed format validation (expected 10 chars [0-9A-Z])",
            )

        # 2. Ambiguous pack / variation -> review, do not merge.
        if sub.pack_ambiguous:
            cand = UnresolvedCandidate(
                raw_asin=asin, raw_title=sub.title,
                reason="pack_ambiguity", source=sub.source,
                source_identifier=sub.source_identifier,
            )
            self.repos.candidates.add(cand)
            return ResolutionResult(
                resolution=IdentityResolution.PACK_REVIEW_REQUIRED.value,
                candidate_id=cand.id,
                detail="pack configuration ambiguous; queued for review",
            )

        # 3. Exact Amazon identity lookup.
        if asin:
            matches = self.repos.products.by_marketplace_asin(sub.marketplace_id, asin)
            if len(matches) == 1:
                return ResolutionResult(
                    resolution=IdentityResolution.EXISTING_PRODUCT.value,
                    product_id=matches[0]["id"],
                    detail="matched existing (marketplace_id, asin)",
                )
            if len(matches) > 1:
                conflict = IdentityConflict(
                    conflict_type="duplicate_amazon_identity",
                    product_id=matches[0]["id"],
                    detail=f"{len(matches)} products share (marketplace_id, asin)",
                )
                self.repos.conflicts.add(conflict)
                return ResolutionResult(
                    resolution=IdentityResolution.IDENTITY_CONFLICT.value,
                    product_id=matches[0]["id"],
                    conflict_id=conflict.id,
                    detail="multiple canonical products share the same identity",
                )

        # 4. Cross-identifier duplicate detection (UPC/EAN/GTIN).
        for kind, raw in sub.identifiers:
            if kind == IdentifierKind.ASIN.value:
                continue
            norm = normalize_identifier(kind, raw)
            if not norm:
                continue
            hits = self.repos.identifiers.by_normalized(kind, norm)
            if hits:
                # Possible duplicate — do NOT silently merge.
                conflict = IdentityConflict(
                    conflict_type="cross_identifier_match",
                    product_id=hits[0]["product_id"],
                    detail=f"{kind}:{norm} already maps to product {hits[0]['product_id']}",
                )
                self.repos.conflicts.add(conflict)
                return ResolutionResult(
                    resolution=IdentityResolution.POSSIBLE_DUPLICATE.value,
                    product_id=hits[0]["product_id"],
                    conflict_id=conflict.id,
                    detail="new ASIN shares a UPC/EAN/GTIN with an existing product",
                )

        # 5. Variation family review.
        if sub.variation_family_ref:
            cand = UnresolvedCandidate(
                raw_asin=asin, raw_title=sub.title, reason="variation_review",
                source=sub.source, source_identifier=sub.source_identifier,
            )
            self.repos.candidates.add(cand)
            return ResolutionResult(
                resolution=IdentityResolution.VARIATION_REVIEW_REQUIRED.value,
                candidate_id=cand.id,
                detail="variation family relationship requires review",
            )

        # 6. No match and no ambiguity -> create new canonical product.
        if not asin:
            cand = UnresolvedCandidate(
                raw_title=sub.title, reason="no_asin_provided",
                source=sub.source, source_identifier=sub.source_identifier,
            )
            self.repos.candidates.add(cand)
            return ResolutionResult(
                resolution=IdentityResolution.UNRESOLVED_CANDIDATE.value,
                candidate_id=cand.id,
                detail="no ASIN provided; cannot create canonical Amazon identity",
            )

        product = CatalogProduct(
            marketplace_id=sub.marketplace_id, asin=asin,
            brand=sub.brand, canonical_title=sub.title,
        )
        self.repos.products.add(product)

        # Persist the ASIN identifier with provenance-ish state.
        self.repos.identifiers.add(ProductIdentifier(
            product_id=product.id, kind=IdentifierKind.ASIN.value,
            raw_value=sub.asin, normalized_value=asin,
            marketplace_id=sub.marketplace_id,
        ))
        # Persist other identifiers.
        for kind, raw in sub.identifiers:
            norm = normalize_identifier(kind, raw)
            if norm:
                self.repos.identifiers.add(ProductIdentifier(
                    product_id=product.id, kind=kind, raw_value=raw,
                    normalized_value=norm, marketplace_id=sub.marketplace_id,
                ))
        # Pack config (only when unambiguous).
        if sub.pack_count is not None or sub.pack_unit:
            pc = PackConfig(product_id=product.id, count=sub.pack_count,
                            unit=sub.pack_unit)
            self.repos.pack_configs.add(pc)
            self.repos.db.conn.execute(
                "UPDATE catalog_products SET pack_config_id=? WHERE id=?",
                (pc.id, product.id),
            )
            self.repos.db.conn.commit()

        return ResolutionResult(
            resolution=IdentityResolution.NEW_PRODUCT.value,
            product_id=product.id,
            detail="created new canonical product",
        )