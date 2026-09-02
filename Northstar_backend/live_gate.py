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

from env_flags import env_flag

GATE_ENV = "SCANNER_LIVE_ALLOWED"


def live_enabled() -> bool:
    """True only when SCANNER_LIVE_ALLOWED is an explicit opt-in."""
    return env_flag(GATE_ENV)


def live_disabled_note() -> str:
    """Honest user-facing reason when live data is unavailable by policy."""
    return (
        f"Live providers are disabled ({GATE_ENV} not set to an explicit "
        "opt-in like 1). Returning cached/offline data only."
    )