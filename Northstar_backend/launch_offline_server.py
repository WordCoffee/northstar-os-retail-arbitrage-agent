#!/usr/bin/env python
"""Launch the Northstar backend in guaranteed-offline mode for SourceScout
testing. Zero outbound calls: forces the live gate closed and enrichment
to cache-only regardless of .env values, then starts uvicorn."""
import os

# Hard offline containment (parent-process env wins over .env because
# load_dotenv() defaults to override=False).
os.environ["SCANNER_LIVE_ALLOWED"] = "0"          # live_gate.live_enabled() -> False
os.environ["SCANNER_OFFER_ENRICHMENT"] = "OFF"    # cache-only, zero outbound
os.environ["SCANNER_LOCAL_SNAPSHOT_MERGE"] = "1"  # merge local snapshot store
os.environ["SCANNER_SEARCH_FALLBACK"] = "cache"   # no live search fallback

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)