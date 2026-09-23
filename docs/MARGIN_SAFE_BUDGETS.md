# MARGIN-SAFE BUDGETS — Northstar OS (Phase A / A1)

> Single-page economics reference. Source of truth for the numbers is
> `shared/usage-caps.json` (caps + unit costs) and `Northstar_backend/cost_model.py`
> (the invariant). Both are asserted by tests. Recalibrated 2026-09-22 to **real
> provider prices** (Sept 2026 media/AI stack).

## 1. The margin band

Target: **60–80% ROI margin**, i.e. worst-case cost must sit between **20% and 40% of price**.
Design anchor = **30% of price (≈70% margin)**. Every tier carries **$8 fixed infra**.

| Tier | Price | Cost ceiling (40%) | Target (30%) | AI+media budget | Worst-case cost | Margin |
|---|---|---|---|---|---|---|
| Whetstone | $39 | $15.60 | $11.70 | $7.60 | $11.52 | **70.5%** |
| Mainstay | $79 | $31.60 | $23.70 | $23.60 | $23.68 | **70.0%** |
| Keystone | $129 | $51.60 | $38.70 | $43.60 | $37.84 | **70.7%** |
| AutothinK | $179 | $71.60 | $53.70 | $63.60 | $52.91 | **70.4%** |

All tiers land mid-band. Worst case slides toward 61% only if every cap is hit at
the most expensive unit — still above the 60% floor.

## 2. Usage per service per tier (recalibrated caps)

| Action | Whetstone | Mainstay | Keystone | AutothinK |
|---|---|---|---|---|
| `chat_t1` (Prospector + Auctioneer + Watch narratives) | 4,153 | 14,635 | 20,591 | 25,134 |
| `listing` (OfferChisel copy) | 906 | 3,193 | 4,492 | 5,483 |
| `post` (Town Crier drafts) | 226 | 798 | 1,123 | 1,370 |
| `gg_scan` (Golden Goose scans) | 3 | 13 | 18 | 22 |
| ↳ `gg_items_per_scan` | 12 | 12 | 12 | 12 |
| `rank_snapshot` (Watch / RankLedger / Rival Board) | — | 2,128 | 2,995 | 3,655 |
| `alert` (Rival Board alerts) | — | 532 | 748 | 913 |
| `autothink_t2` (AutothinK workspace, core) | — | — | — | 9,871 |
| `autothink_t3` (AutothinK, seam/escalation) | — | — | — | 1,645 |
| Images `V1` (drafts) | 40 | 141 | 199 | 243 |
| Images `V2` (finals) | — | — | 112 | 137 |
| Images `V3` (text-heavy ads / A+) | — | — | 28 | 34 |
| Video `Wan15s` (capped) | — | — | 3 | 4 |

## 3. Real unit costs (calibration basis)

| Unit | Cost | Real stack |
|---|---|---|
| `chat_t1` | $0.0002 | DeepSeek V4 Flash (`:free`/T1), ~2k-token task |
| `listing` | $0.001 | DeepSeek T2 copy |
| `post` | $0.002 | DeepSeek T2 draft + hashtags |
| `autothink_t2` | $0.0005 | DeepSeek V4 Flash (T2) workspace task |
| `autothink_t3` | $0.002 | DeepSeek V4.1 Flash (T3) escalation |
| `gg_scan` + 12 items | $0.005 + 12×$0.02 | scan orchestration + per-item enrich |
| `image_v1` | $0.015 | FLUX.2 klein 9B draft |
| `image_v2` | $0.03 | FLUX.2 pro final |
| `image_v3` | $0.08 | Nano Banana 2 (flat) / GPT Image 2 low |
| `video_wan_15s` | $0.75 | Wan 2.5, 15s |
| `rank_snapshot` / `alert` | $0.001 | deterministic reads |
| `fixed_infra` | $8.00 | per tier/month |

## 4. AutothinK service budget (dedicated)

| Line | Cap | Unit | $/mo |
|---|---|---|---|
| AutothinK T2 workspace | 9,871 | $0.0005 | $4.94 |
| AutothinK T3 escalations | 1,645 | $0.002 | $3.29 |
| **AutothinK service total** | | | **$8.23** |

That is ~13% of the AutothinK plan's $63.60 AI+media budget — the rest funds the
full service suite (Golden Goose 22 scans, 5,483 listings, images, video).

## 5. Video packaging

- **Wan 2.5 (15s, $0.75)** is the only video inside tier caps.
- **Kling 2.6 Pro ($2.10/15s, native audio)** and **Veo 3.1 ($1.50/15s)** are
  **usage-metered add-ons** — outside subscription caps. One Kling short is 28% of
  Whetstone's entire AI budget, so it cannot be a capped inclusion without breaking
  margin; it is billed per render instead.
- Voiceover is noise in the budget ($0.03 ElevenLabs / $0.007 Deepgram on a $2 video).

## 6. Coupled subsystems (display meter — unchanged)

`credit_weight` and `credit_ledger.PLAN_CREDIT_ALLOTMENT` are the **display meter**
(credits), decoupled from the real-USD cost model by design. Enforcement is by ACTION
CAPS above; credits are cosmetic. A future coherence pass may rescale credit weights
to real unit costs and re-derive allotments (tracked in the build backlog).

## 7. Invariant (enforced by tests)

`cost_model.test_all_tiers_keep_margin_floor` and `test_all_tiers_within_target_band`
assert `0.20 ≤ worst_case_cost / price ≤ 0.40` (hence `0.60 ≤ margin ≤ 0.80`) on every
tier. Pricing can never silently drift into a loss or an over-margin tier.
