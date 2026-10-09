"""Default-off gate for every live provider call reachable from the web app.

SCANNER_LIVE_ALLOWED (strict boolean via env_flags.env_flag) must be an
explicit opt-in (1/true/yes/on, case-insensitive). Unset or anything else
means live providers are DISABLED: every app-facing entry point returns
cached/offline data only, so GET routes, static assets, UI page loads,
imports, and startup hooks can never trigger outbound provider traffic.

Enforcement points (each checks live_enabled() before touching a provider):
  - amazon_search.search_kirkland_products   (Bright Data / Chocodata / Scavio)
  - offer_enrichment._enrichment_mode()       (forces "OFF" -> cache-only scan)
  - offer_enrichment.get_seller_offer_contract (Easyparser OFFER roster)
  - canopy_client.get_canopy_product          (Canopy product detail)

Provider client modules (bright_data_client, brightdata_client,
scavio_client, easyparser_client) are only reachable through those entry
points from the app; the explicit CLI refresh commands (npm pipeline,
costco_api_client.py refresh, enrich_cached_asins.py --live) are the
intentional opt-in paths and are documented as such.
"""

import os
from typing import List, Optional

from env_flags import env_flag

GATE_ENV = "SCANNER_LIVE_ALLOWED"


def live_enabled() -> bool:
    """True only when SCANNER_LIVE_ALLOWED is an explicit opt-in."""
    return env_flag(GATE_ENV)


# --- Per-run live arming (Phase 1 safety hardening) -------------------------
# Arming live providers for the web app is never a boot-time default: it
# requires BOTH an explicit per-run arm flag AND a positive per-run cost cap
# (in integer cents), so an accidental `SCANNER_LIVE_ALLOWED=1` in a shared
# environment cannot silently turn a plain GET into metered provider spend.
# The live test runner sets both for the duration of one bounded run and
# disarms them afterwards.

PER_RUN_ARM_ENV = "NS_LIVE_PER_RUN_ARMED"
PER_RUN_CAP_ENV = "NS_LIVE_PER_RUN_CAP_CENTS"


def per_run_armed() -> bool:
    """True only when NS_LIVE_PER_RUN_ARMED is an explicit opt-in."""
    return env_flag(PER_RUN_ARM_ENV)


def per_run_cap_cents() -> Optional[int]:
    """Positive per-run cost cap in integer cents, else None."""
    raw = (os.environ.get(PER_RUN_CAP_ENV) or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def live_posture_problems() -> List[str]:
    """Every reason live mode must be refused, empty when posture is safe."""
    if not live_enabled():
        return []
    problems: List[str] = []
    if not per_run_armed():
        problems.append(
            f"{PER_RUN_ARM_ENV} is not an explicit opt-in like 1"
        )
    cap = per_run_cap_cents()
    if cap is None:
        problems.append(
            f"{PER_RUN_CAP_ENV} is not a positive integer number of cents"
        )
    return problems


def assert_live_posture() -> None:
    """Refuse to boot the web app when live providers are armed without a
    per-run arm flag and a positive per-run cost cap.

    Call at app startup (mirrors ``rate_limiter.assert_prod_posture``). A
    cached/offline deployment is ALWAYS allowed to boot; only an armed live
    mode is refused, and only because it is not auditably bounded.
    """
    problems = live_posture_problems()
    if problems:
        raise RuntimeError(
            "LIVE POSTURE VIOLATION: "
            f"{GATE_ENV} is armed, so a plain GET could make metered "
            "provider calls, but the per-run bounds are missing ("
            + "; ".join(problems)
            + "). Set "
            f"{GATE_ENV}=0 for a cache-only deployment, or arm one bounded "
            f"live run with {PER_RUN_ARM_ENV}=1 and a positive "
            f"{PER_RUN_CAP_ENV}. See INCIDENT_NOTE_live_calls_2026-10-08.md."
        )


def live_disabled_note() -> str:
    """Honest user-facing reason when live data is unavailable by policy."""
    return (
        f"Live providers are disabled ({GATE_ENV} not set to an explicit "
        "opt-in like 1). Returning cached/offline data only."
    )