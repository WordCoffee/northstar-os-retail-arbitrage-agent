"""NO-AMAZON-LINKAGE guard (file-only architecture, 2026-10-11).

Two halves, both required:

  A. STATIC SCAN — the file-only surfaces (the Design Studio UI, the new
     file-integration modules, the Design Studio API) contain NO Amazon
     linkage: no SP-API / Ads API hosts, no OAuth/LWA flow, no Amazon
     credential env names. Amazon HELP URLs (citations in the spec registry)
     are allowed; API hosts are not.

  B. POSTURE + REFUSAL — the linkage gate is off by default; it refuses to
     boot in staging/production when enabled; and the four linkage points
     (SP-API importer, Ads API importer, the unified Amazon adapter, the
     blacklist re-check) refuse even WITH credentials unless the gate is
     explicitly enabled.

Run:  python tools/test_no_amazon_linkage.py
Exit: 0 = clean, 1 = a violation, 2 = harness error.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "Northstar_backend"
UI = ROOT / "northstar-os-ui" / "src"

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"PASS  {msg}")


def no(msg: str) -> None:
    global FAIL
    FAIL += 1
    FAILURES.append(msg)
    print(f"FAIL  {msg}")


# ── A. Static scan ─────────────────────────────────────────────────────────
# The gated modules are the ONLY places allowed to name Amazon API hosts or
# read Amazon credential env vars; every one of them consults the gate.
# data_refresh.py is a CLI status registry: it lists provider config names but
# calls no Amazon endpoint (and is part of the live-pull family behind
# live_gate).
GATED_MODULES = {
    "importers/sp_api_importer.py",
    "importers/ads_api_importer.py",
    "adapters/amazon_api.py",
    "tasks/brand_blacklist_updater.py",
    "amazon_linkage_gate.py",
    "data_refresh.py",
}

API_HOST_PATTERNS = [
    re.compile(r"sellingpartnerapi", re.I),
    re.compile(r"advertising-api\.amazon\.com", re.I),
    re.compile(r"api\.amazon\.com/auth", re.I),
    re.compile(r"/auth/o2", re.I),
]
CREDENTIAL_ENV_PATTERNS = [
    re.compile(r"SP_API_CLIENT_ID|SP_API_CLIENT_SECRET|SP_API_REFRESH_TOKEN"),
    re.compile(r"ADS_CLIENT_ID|ADS_CLIENT_SECRET|ADS_REFRESH_TOKEN"),
]

# The file-only backend modules: parsers/writers must be network-free.
# OOXML/XML NAMESPACE identifiers (schemas.openxmlformats.org, www.w3.org) are
# inert strings ElementTree matches on - they are never fetched, so they are
# allowlisted; every OTHER http(s) URL is forbidden.
FILE_ONLY_MODULES = [
    BACKEND / "amazon_file_parsers.py",
    BACKEND / "amazon_file_writers.py",
    BACKEND / "amazon_change_files.py",
]
NETWORK_PATTERNS = [
    re.compile(r"^\s*import\s+(httpx|requests|aiohttp|urllib|socket)\b", re.M),
    re.compile(r"^\s*from\s+(httpx|requests|aiohttp|urllib|socket)\b", re.M),
    re.compile(r"https?://(?!(?:schemas\.openxmlformats\.org|www\.w3\.org|purl\.org|schemas\.microsoft\.com))", re.I),
]


def scan_file(path: Path, patterns, what: str, allow_gated: bool) -> None:
    rel = path.relative_to(ROOT).as_posix()
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    hits = []
    for i, line in enumerate(src.splitlines(), 1):
        for pat in patterns:
            if pat.search(line):
                hits.append(f"{rel}:{i}: {line.strip()[:100]}")
    if not hits:
        ok(f"{what}: {rel} is clean")
    elif allow_gated and rel.replace("Northstar_backend/", "") in GATED_MODULES:
        ok(f"{what}: {rel} names linkage internals and is on the GATED list")
    else:
        no(f"{what}: {rel} contains linkage code:\n      " + "\n      ".join(hits[:4]))


def main() -> int:
    # A1. Backend python files OUTSIDE the gated modules must not name Amazon
    #     API hosts or credential env vars (comments included - deliberate).
    scanned = 0
    for path in sorted(BACKEND.rglob("*.py")):
        rel = path.relative_to(BACKEND).as_posix()
        if rel in GATED_MODULES or rel.startswith("tests/") or rel.startswith("test_"):
            continue
        # The inventory report names them by design; skip nothing else.
        scan_file(path, API_HOST_PATTERNS + CREDENTIAL_ENV_PATTERNS, "backend", allow_gated=False)
        scanned += 1
    print(f"      (scanned {scanned} backend modules outside the gated list)")

    # A2. The UI must not name Amazon API hosts or OAuth paths. Help/citation
    #     URLs (advertising.amazon.com/help, sellercentral help) are allowed.
    ui_scanned = 0
    for path in sorted(UI.rglob("*")):
        if path.suffix not in (".js", ".jsx", ".cjs", ".mjs"):
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        hits = [f"{path.relative_to(ROOT).as_posix()}: {pat.pattern}" for pat in API_HOST_PATTERNS if pat.search(src)]
        if hits:
            no(f"UI linkage: {path.relative_to(ROOT).as_posix()} matches {hits}")
        ui_scanned += 1
    ok(f"UI scan: {ui_scanned} source files contain no Amazon API host or OAuth path")

    # A3. The file-only modules must be network-free (no http(s) URL at all).
    for path in FILE_ONLY_MODULES:
        if not path.exists():
            no(f"file-only module missing: {path.name} (the scan cannot pass vacuously)")
            continue
        scan_file(path, NETWORK_PATTERNS, "file-only", allow_gated=False)

    # ── B. Posture + refusal ───────────────────────────────────────────────
    sys.path.insert(0, str(BACKEND))
    os.environ.pop("NS_AMAZON_LINKAGE_ENABLED", None)
    os.environ["ENVIRONMENT"] = "development"

    from amazon_linkage_gate import (assert_linkage_posture, linkage_enabled,
                                     linkage_posture_problems, linkage_refusal_reason)

    if linkage_enabled() is False:
        ok("the linkage gate is OFF by default")
    else:
        no("the linkage gate defaults to ON - it must default OFF")

    if linkage_posture_problems("production") == [] and linkage_posture_problems("staging") == []:
        ok("with the flag off, staging/production posture is clean")
    else:
        no("posture problems with the flag off")

    os.environ["NS_AMAZON_LINKAGE_ENABLED"] = "1"
    try:
        assert_linkage_posture("production")
        no("production did NOT refuse linkage with the flag on")
    except RuntimeError:
        ok("production REFUSES to boot with Amazon linkage enabled")
    try:
        assert_linkage_posture("staging")
        no("staging did NOT refuse linkage with the flag on")
    except RuntimeError:
        ok("staging REFUSES to boot with Amazon linkage enabled")
    try:
        assert_linkage_posture("development")
        ok("development allows the explicit opt-in (no refusal)")
    except RuntimeError:
        no("development refused the explicit opt-in")
    os.environ.pop("NS_AMAZON_LINKAGE_ENABLED", None)

    # Refusal-with-credentials: set FAKE credentials, keep the gate off.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="ns_linkage_")
    tmp.close()
    import data_layer
    data_layer._SQLITE_PATH = Path(tmp.name)

    os.environ.update({
        "SP_API_CLIENT_ID": "fake", "SP_API_CLIENT_SECRET": "fake", "SP_API_REFRESH_TOKEN": "fake",
        "ADS_CLIENT_ID": "fake", "ADS_CLIENT_SECRET": "fake", "ADS_REFRESH_TOKEN": "fake",
    })

    from importers.sp_api_importer import SPAPIImporter
    from importers.ads_api_importer import AdsAPIImporter

    sp = SPAPIImporter()
    if sp.is_configured is False and "file-only" in (sp.refusal_reason or ""):
        ok("SP-API importer refuses WITH credentials while the gate is off (file-only reason stated)")
    else:
        no(f"SP-API importer did not refuse: configured={sp.is_configured} reason={sp.refusal_reason}")

    ads = AdsAPIImporter()
    if ads.is_configured is False and "file-only" in (ads.refusal_reason or ""):
        ok("Ads API importer refuses WITH credentials while the gate is off")
    else:
        no(f"Ads API importer did not refuse: configured={ads.is_configured} reason={ads.refusal_reason}")

    from adapters.amazon_api import AmazonAPIAdapter
    if AmazonAPIAdapter().is_configured() is False:
        ok("the unified Amazon adapter refuses while the gate is off")
    else:
        no("the unified Amazon adapter is configured while the gate is off")

    from tasks.brand_blacklist_updater import BrandBlacklistUpdater
    upd = BrandBlacklistUpdater.__new__(BrandBlacklistUpdater)
    os.environ["BRAND_RECHECK_LIVE_OPERATOR_APPROVED"] = "1"
    if upd.live_armed() is False:
        ok("the blacklist re-check refuses to arm with the operator gate alone (linkage gate still required)")
    else:
        no("the blacklist re-check armed without the linkage gate")

    # With the gate explicitly ON, the credential-gated importers configure -
    # proving the gate (not the credentials) is the switch.
    os.environ["NS_AMAZON_LINKAGE_ENABLED"] = "1"
    sp2 = SPAPIImporter()
    if sp2.is_configured is True:
        ok("with the gate explicitly ON, the SP-API importer configures (the gate is the switch)")
    else:
        no("with the gate ON the SP-API importer still refused")
    if upd.live_armed() is True:
        ok("with the gate ON the blacklist re-check arms (both conditions satisfied)")
    else:
        no("with the gate ON the blacklist re-check still refused")
    os.environ.pop("NS_AMAZON_LINKAGE_ENABLED", None)
    os.environ.pop("BRAND_RECHECK_LIVE_OPERATOR_APPROVED", None)
    for k in ("SP_API_CLIENT_ID", "SP_API_CLIENT_SECRET", "SP_API_REFRESH_TOKEN",
              "ADS_CLIENT_ID", "ADS_CLIENT_SECRET", "ADS_REFRESH_TOKEN"):
        os.environ.pop(k, None)

    try:
        data_layer._db_instance.close()
    except Exception:
        pass
    try:
        os.unlink(tmp.name)
    except OSError:
        pass

    print(f"\nNO-AMAZON-LINKAGE GUARD: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:\n  " + "\n  ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
