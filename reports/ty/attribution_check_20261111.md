# Attribution check — who actually owns the seller output (2026-11-11)

Read-only. After lane F moved `listingforge`, `goldengoose` and `golden-goose` off a 0.0,
three services stayed at 0 with the reason *"no Seller-Tester output scored for this
service"*. This asks whether that is a measurement gap or a real one, by reading what each
service declares in `ty/service_registry.json`.

| service | declared tool | its own backend actions | who produces the artefact | verdict |
|---|---|---|---|---|
| `listings` | `optimize_listing` | `GET /api/v1/noncreative/listings/health` only | `listingforge` owns `compose_listing` and `POST /api/v1/reasoning/listing-proposal` | **real 0.** `listings` is a health/monitoring surface; giving it listingforge's score would be borrowing |
| `product-finder` | `scan_products` | **none** | the research path (`research_graph`) is not its endpoint | **real 0, and worse:** it declares a tool with no action at all |
| `adpilot` | `plan_campaign` | ad-copy-proposal, amazon-files reads, terms | the PPC path writes bulksheets; `adpilot` reads them | **real 0 at the seller dimension.** Its own output is ad copy, which nobody scores yet |
| `towncrier` | *(none)* | `POST /api/autothink/run` only | — | **real 0**, and it declares no tool |

**Conclusion: lane F's attribution was right, and the remaining zeros are honest.** The fix is
a scorer per service, not a bigger share of someone else's output.

Two new findings, both `complete`-class:

1. **`product-finder` declares `scan_products` and has zero backend actions.** The registry's
   own rule (from 2026-11-09) is that a declared tool must have a callable handler; this is the
   same defect class as the four beta services, with an empty action list on top.
2. **`towncrier` declares no tool at all** — a service with a view and no action.

Queued as `fix-product-finder-wiring`, with `fix-seller-offer-caption` for the three services
whose output is copy (offerchisel, socialpulse, towncrier) and needs a scorer before it can be
measured.
