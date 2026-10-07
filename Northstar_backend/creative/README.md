# creative — Northstar image / text generation lane

Two lanes, one rule: **the AI makes the scene, the compositor makes the text.**

* `comfy_client.py` — local ComfyUI lane (Qwen-Image-2512 t2i, Qwen-Image-Edit-2511,
  FLUX fallback) + workflow builders + model resolution + `blank_panel` panel prep.
* `exact_text.py` — deterministic exact-text compositor (rectangle / quad /
  barrel curvature) with a brand-content guard and bundled brand fonts.
* `label_zone.py` — deterministic blank-label-zone detection for `align="auto"`.
* `presets.py` — reusable brand, container, product, surface-zone and style presets.
* `mogra_mockup.py` — one-call pipeline (`build_mockup`, `align`, `panel_prep`) + CLI.
* `routes.py` — `/api/creative/*` FastAPI routes + the `/mogra-mockup` UI page.
* `static/mockup.html` — beginner-friendly standalone UI.
* `assets/fonts/` — bundled brand fonts (Libre Baskerville + DM Sans, OFL 1.1).

React surface: **Creative Studio → Exact-Text Mockups** (`?view=mockups`),
component `northstar-os-ui/src/components/MockupStudio.jsx`.

Standard and run instructions: `docs/NORTHSTAR_IMAGE_TEXT_WORKFLOW.md`.

Tests: `Northstar_backend/test_creative_mockup.py`,
`Northstar_backend/test_creative_routes.py`.

CLI:

```powershell
python -m creative.mogra_mockup --list
python -m creative.mogra_mockup --product organic_turmeric_powder `
  --container mogra_5lb_clear_handled_pet_jar --generate --out out.png
```

---

## Lane map (all local-first)

| Lane | Routes | Module |
|------|--------|--------|
| Exact-text mockups + scene gen/edit | `/api/creative/*`, `/mogra-mockup` | `comfy_client`, `exact_text`, `label_zone`, `mogra_mockup`, `presets` |
| Listing copy/score/compliance | `/api/listing-forge/*` | `service_routes` → `listing_forge.py` |
| Social captions/calendar/brand voice | `/api/social/*` | `service_routes` → `social_pulse.py` |
| Ad planning (bids/target ACoS) | `/api/ad-pilot/*` | `service_routes` → `ad_pilot.py` |
| Asset registry + variant sets + bundles | `/api/creative/assets*`, `/api/creative/bundles` | `assets.py`, `bundles.py` |
| Cloud media (gated) | `/api/creative/cloud/generate` | `cloud.py` |
| Video (gated) | `/api/creative/video/*` | `video.py` |
| Write-action approvals | `/api/creative/approvals*` | `approvals.py` |
| Capabilities / provider + storage posture | `/api/creative/capabilities` | `providers.py`, `storage.py`, `moderation.py` |

### Arming (all default OFF)

| Capability | Env flag |
|------------|----------|
| Cloud image/video generation | provider key + `MEDIA_GEN_LIVE=1` |
| Social publishing write action | `NORTHSTAR_SOCIAL_PUBLISH_ARMED=1` (+ approved request) |
| Ads write (real money) | `NORTHSTAR_ADS_WRITE_ARMED=1` (+ approved request) |
| S3-compatible media backend | `NORTHSTAR_MEDIA_STORAGE=s3` + `NORTHSTAR_S3_BUCKET` |
| Exempt creative lanes from the edge rate limiter | `NORTHSTAR_RATE_LIMIT_EXEMPT_CREATIVE=1` |
| Disable the local LLM (instant template drafts) | `NORTHSTAR_CREATIVE_LLM=0` or per-request `use_llm=false` |

Real spend and the first public post additionally require a recorded approval and a
fresh operator go-ahead — the lanes report `write_actions_disarmed` / `not_approved`
rather than faking success.
