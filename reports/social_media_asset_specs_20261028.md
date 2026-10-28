# 1.4 — SOCIAL MEDIA ASSET SPECS
## Phase 2 research deliverable — REA program

**Date:** 2026-10-28
**Scope:** establish the authoritative, dated spec set per platform; diff it
against what the UI actually renders; separate documented rules from folklore;
specify the local pre-upload validator.
**Spend:** 0. **Amazon contact:** 0.

---

## 1. The finding that matters most

The repo already does this properly for **Amazon**: `specRegistry.js` carries a
`SPEC_SOURCES` table where every entry has `url`, `pulled`, `quality` and
`confidence: VERIFIED | REPORTED`, plus a `POLICY_FRESHNESS` recheck register
(`specRegistry.js:27-120`).

**Social has no equivalent.** `presets.js:11-92` defines every social canvas as a
bare `{ id, label, w, h, group, channel }` — no source, no date, no confidence,
no file-size cap, no caption limit. Read the file: the word `source` does not
appear in it.

Consequence: a social asset can be "correct" by the UI and wrong by the
platform, and nothing in the codebase would notice. That is the asymmetry this
report closes.

---

## 2. Repo vs official — staleness table

"Official" = page fetched 2026-10-28 from the platform itself (see §6 for URLs).

| Repo id | Repo value | Official value | Verdict |
|---|---|---|---|
| `ig-post` | 1080×1350 (4:5) | **4:5, recommended 1440×1800**, max 30 MB, min width 500 px | **ratio correct, resolution soft** — renders at 75 % of recommended linear size |
| `ig-carousel` | 1080×1080 (1:1) | 1:1 is a supported feed ratio; the ads guide documents the *placement*, not a carousel-specific canvas | **partial** — usable, unsourced |
| `pin` | 1000×1500 (2:3) | **2:3, 1000×1500**, PNG/JPEG, 20 MB desktop / 32 MB in-app, title 100 chars, description 800 chars | **exact match** — the only repo social value that matches the official recommendation outright |
| `meta-story` | 1080×1920 (9:16) | **9:16, recommended 1440×2560**, max 30 MB; safe area ≈ **14 % top / 35 % bottom / 6 % each side** | **ratio correct, resolution soft, safe area missing** |
| `tiktok` | 1080×1920 (9:16) | 9:16 **≥ 540×960** (vertical recommended); also 16:9 ≥ 960×540 and 1:1 ≥ 640×640; **≤ 500 MB**; mp4/mov/mpeg/3gp/avi; **≥ 516 kbps**; up to 10 min | **ratio correct; missing file cap, bitrate floor, duration cap, format list** |
| `x-post` | 1600×900 (16:9) | Image ads: **max 5 MB**, PNG/JPEG (no BMP/TIFF); standalone image ad recommended **1200×628 (1.91:1)** or 1200×1200 (1:1); 16:9 is supported for app-button placements (1920×1080) | **off-recommendation** — 16:9 is a real placement ratio but not the documented default for an image ad |
| `linkedin` | 1200×627 | **1200×628 (1.91:1)**, JPG/PNG/GIF (non-animated), **max 5 MB**, min 640×360, max 7680×4320 | **matches within 1 px** — reported, not verified (official page not retrieved, see §7) |
| `yt-thumb` | 1280×720 (16:9) | 16:9; **recommended 3840×2160**, min width 640; JPG/PNG; **desktop 50 MB**, mobile 2 MB; Shorts thumbnails are 9:16 (2160×3840) | **ratio correct, 1/3 of recommended resolution, size cap missing** |

Staleness count: **7 social entries reviewed, 1 exact (Pinterest), 4
ratio-correct-but-incomplete, 1 off-recommendation, 1 partial.**

### Formats that have no canvas at all

| Missing placement | Official spec | Why it matters |
|---|---|---|
| IG / FB Reels + Stories **vertical at full resolution** | 9:16, 1440×2560, ≤ 30 MB | `meta-story` is 1080×1920 — every story render is upscaled by the platform |
| Pinterest **standard-width video** | mp4/mov/m4v, H.264/265, ≤ 2 GB, 4 s–15 min, shorter than 1:2 and taller than 1.91:1 | the repo has no Pinterest video canvas |
| Pinterest **Idea ad** | 9:16, recommend 1080×1920, safe zone top 270 / left 65 / right 195 / bottom 440 px | the only platform that publishes exact pixel safe zones |
| X **carousel** | 2–6 slides; 800×800 (1:1) or 800×418 (1.91:1) image; 800×800 / 800×450 video; one ratio per carousel | a very common product format |
| X **vertical video** | 720×1280 min – 1080×1920 max, ≤ 60 fps, target 5–10 Mbps, AAC-LC | absent |
| YouTube **Shorts thumbnail** | 9:16, 2160×3840 recommended, min height 640 | absent |
| Any platform **caption / alt-text caps** | Pinterest title 100 / description 800; Meta primary 125 / headline 40 / ≤ 30 hashtags; X 280 chars per post | absent — the studio cannot warn about copy length at all |

---

## 3. Documented vs folklore

Kept separate on purpose: a build requirement may only come from the left column.

| Documented (build on it) | Folklore (never a requirement) |
|---|---|
| IG Feed is 4:5 @ 1440×1800, max 30 MB, min width 500 | "carousels always beat single images" |
| IG Stories safe area ≈ 14 % top / 35 % bottom / 6 % sides | "post at 6 pm for reach" |
| Meta primary text 125 chars, headline 40 chars, **≤ 30 hashtags** | "30 hashtags gets you reach" — the cap is documented, the *benefit* is not |
| Pinterest 2:3 @ 1000×1500; 20 MB desktop / 32 MB in-app; title 100, description 800 | "fresh pins get a boost every 3 days" |
| Pinterest Idea ad safe zones in exact px | "Pinterest users ignore text overlay" |
| TikTok in-feed ≥ 540×960, ≤ 500 MB, ≥ 516 kbps, ≤ 10 min | "TikTok punishes watermarks" (policy-adjacent, unverified) |
| X image ads ≤ 5 MB, PNG/JPEG only, 1.91:1 or 1:1 | "links in the first post kill reach" |
| YouTube 16:9, 3840×2160 recommended, ≤ 50 MB desktop | "thumbnail text under 4 words wins" |
| "Trending style" is not a spec on any platform page | any claim that a visual style is *required* |

Note the honest consequence: **no platform publishes an engagement rule**, so
"optimise for engagement" cannot be a build requirement. What *can* be built is
compliance + legibility + safe-area.

---

## 4. What "optimising for the platform" can actually mean here

Three defensible levers, all local, all measurable:

1. **Canvas correctness** — render at the documented pixel size, not a scaled
   approximation (fixes the 1080→1440 upscale on IG/Stories).
2. **Safe-area occupancy** — the asset must not place text/logo inside a
   documented keep-out. Only Pinterest publishes exact px (Idea/Showcase); Meta
   publishes percentages for Stories; TikTok publishes downloadable safe-zone
   packages (not numerically stated on the page — `UNVERIFIED` values, so do not
   hard-code them).
3. **Compression headroom** — every platform re-encodes; uploading at the max
   allowed bytes defeats the purpose. Convert to sRGB 8-bit (Pinterest states it
   re-encodes everything to 8-bit RGB JPEG) and stay under the cap.

Anything beyond that is creative judgement, not optimisation.

---

## 5. Variant matrix (one master → every platform)

Master is rendered once at the largest documented canvas; every target is a
crop of it, never a re-render (re-rendering text at a new size changes type
metrics and breaks the type scale).

| Target | Ratio | Canvas | Crop anchor |
|---|---|---|---|
| IG Feed | 4:5 | 1440×1800 | centre, product-safe band kept |
| IG / FB Stories & Reels | 9:16 | 1440×2560 | centre, safe area ≥ 14 %/35 %/6 % |
| Pinterest standard | 2:3 | 1000×1500 | centre |
| Pinterest Idea | 9:16 | 1080×1920 | top 270 / left 65 / right 195 / bottom 440 px keep-out |
| TikTok in-feed | 9:16 | 1080×1920 | centre |
| X image ad | 1.91:1 | 1200×628 | product-safe band; 1:1 1200×1200 variant |
| X carousel | 1:1 | 800×800 | centre |
| LinkedIn | 1.91:1 | 1200×628 | centre |
| YouTube thumbnail | 16:9 | 3840×2160 | centre |

Rule: the **logo and the product centroid must both fall inside the intersection
of all target safe boxes**. That intersection is computed once from the matrix
and stored with the master, so a new platform is a data change, not a re-render.

---

## 6. Local validator spec (pre-upload, no network)

Runs on the existing `image_prep.py`/PIL path; every check returns
`pass | warn | block` with the measured value.

| Check | Rule | Source of the number |
|---|---|---|
| Format | allowlist per platform (e.g. X: PNG/JPEG only) | official |
| Aspect ratio | within **1 % tolerance** of the target ratio | Meta states a 1 % aspect-ratio tolerance |
| Min/max dimensions | per platform (Meta min width 500; LinkedIn max 7680×4320) | official |
| File size | ≤ documented cap, warn above 80 % of cap | official |
| Colour | sRGB 8-bit; warn on CMYK or embedded non-sRGB profile | Pinterest states re-encode to 8-bit RGB JPEG |
| Text/logo in keep-out | occupancy of the documented safe area | official where stated; `UNVERIFIED` otherwise |
| Contrast | WCAG 2.2 AA 4.5:1 for overlaid text | WCAG |
| Caption length | chars vs platform cap | official |

`UNVERIFIED` listed explicitly: TikTok numeric safe-zone values (only .zip
packages are published), YouTube Shorts thumbnail size cap, Instagram carousel
per-slide minimums.

---

## 7. Sources (all pulled 2026-10-28)

| Platform | URL | Status |
|---|---|---|
| Meta — Instagram Feed image ad specs | https://www.facebook.com/business/ads-guide/update/image/instagram-feed | retrieved |
| Meta — Instagram Stories image ad specs | https://www.facebook.com/business/ads-guide/update/image/instagram-story | retrieved |
| Pinterest — ad spec guide | https://help.pinterest.com/en/business/article/pinterest-product-specs | retrieved |
| TikTok — auction in-feed ads (last updated June 2026 on the page) | https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads | retrieved |
| X — ads creative specs | https://help.x.com/en/business-and-advertising/creative-ad-specifications | retrieved |
| YouTube — custom thumbnails | https://support.google.com/youtube/answer/72431 | retrieved |
| LinkedIn | official ad-spec page returned 404 at two known URLs; values taken from two independent third-party spec documents | **REPORTED only** |

---

## 8. BUILD CANDIDATES

| id | component | change | evidence (report §) | effort | risk | gate |
|---|---|---|---|---|---|---|
| S1 | `studio/engine/specRegistry.js` | add a `SOCIAL_SOURCES` table + social spec rows carrying `url`, `pulled`, `confidence` — mirror the Amazon pattern | §1: social entries have no source field at all | 2 h | low | none |
| S2 | `presets.js` | correct `x-post` to 1200×628 (1.91:1) + 1200×1200 variant; raise `ig-post` to 1440×1800, `meta-story` to 1440×2560, `yt-thumb` to 3840×2160 | §2 table | 1 h | low; changes default canvas sizes, so regenerate presets/fixtures | none |
| S3 | new `socialSpecs` data | add the 7 missing canvases (Pinterest video/Idea, X carousel/vertical, YT Shorts, story full-res) | §2 "missing placements" | 3 h | low | none |
| S4 | `image_prep.py` / new `social_validate.py` | local validator: format, ratio ±1 %, dims, bytes, sRGB, safe-area occupancy, caption length | §6 | 4 h | medium; needs the safe-area model | none |
| S5 | `socialDoc.js` / `outputPacks.buildSocialAssetPack` | emit the variant matrix + keep-out intersection with the asset pack | §5 | 2 h | low | none |
| S6 | docs | record the folklore ledger so no one encodes an engagement claim as a rule | §3 | 30 min | none | none |

**Rejected:** any social scheduling/posting API in this phase (credentials +
platform review, and it is not what the diff above needs).

## 9. UNVERIFIED

- LinkedIn official specs (page 404 at two URLs) — treated as REPORTED.
- TikTok safe-zone pixel values (published as .zip packages only).
- Instagram carousel per-card minima (the ads guide documents the placement, not
  the carousel card grid).
- Whether any platform *requires* a specific colour profile — only Pinterest
  states it re-encodes, which is a behaviour, not a requirement.
