"""Manual provider export importers (SellerAmp).

OFFLINE-ONLY. Importers parse locally-provided CSV/JSON export files and map
them into the canonical provider market-snapshot contract with full provenance.
No network access; no provider authentication; no scraping. SellerSprite was
retired 2026-09-27 (trial expired) and has no importer.

Rows are reported as: imported | duplicate | rejected | needs_mapping | stale |
missing_required_fields | identity_ambiguous.
"""
from __future__ import annotations

from .common import (
    sha256_file,
    detect_provider,
    parse_provider_file,
    row_status_counts,
    ImportErrorKind,
)
from .selleramp_importer import SellerAmpImporter
from .import_report import build_import_report
from .validators import validate_row_required_fields

__all__ = [
    "sha256_file",
    "detect_provider",
    "parse_provider_file",
    "row_status_counts",
    "ImportErrorKind",
    "SellerAmpImporter",
    "build_import_report",
    "validate_row_required_fields",
]

PACKAGE_VERSION = "1.0.0"
OFFLINE_ONLY = True