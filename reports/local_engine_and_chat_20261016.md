# Local engine + chat units — 2026-10-16

Operator asks handled this session: (1) "Local engine is not connected" in the
Design Studio, (2) "the video piece is not mapped/connected", (3) "the chatbotx
and boxes aren't typical AI chatboxes — chat should be saved and scrollable
like Perplexity", (4) areas labelled PARTIAL should be fully done.

## 1 + 2. Local media engine — image AND video, end-to-end

The old boundary was a placeholder ("No local video pipeline exists in this
build" — stale). What exists now, all free/local:

| Piece | What was added |
|---|---|
| `Northstar_backend/studio_generation.py` | Real ComfyUI runner: FLUX.2 klein 4B Q8 for images (PNG), Wan 2.2 TI2V-5B for clips (MP4). Armed only when `MEDIA_GEN_LIVE=1` AND ComfyUI answers at `COMFYUI_URL`. Releases models after every render. |
| `design_studio_api.py` | `GET /engine`, `POST /generate` (account-scoped; records a job at 0 credits; saves the file; returns the asset), `GET /assets/{id}/file` (streams the render, basename-guarded). |
| `main.py` readiness | `/api/v1/foundation/creative/readiness` now reports `media_live_armed` + full local engine state (the field the studio's arming logic reads). |
| `scripts/launch_alpha.ps1` | Sets `MEDIA_GEN_LIVE=1`, `COMFYUI_URL=http://127.0.0.1:8199`, `VIDEO_GEN_LIVE=1`; **starts ComfyUI automatically** (skip: `-NoComfy`). |
| Studio UI (`CreativeStudio.jsx`, `Chrome.jsx`, `engineApi.js`, `presets.js`) | Green "LOCAL ENGINE ARMED" banner when live; Generate button renders (spinner → result card with the image); Video tab renders clips (player card); queue rows link to results; boundary copy now states the truth for both kinds. |

**GPU handshake (one 16 GB card):** the runner evicts the local brain from VRAM
before a render and frees ComfyUI's models after it. The brain auto-reloads on
the next chat (measured 8–17 s warm-ish). Both services stay up; only one heavy
model is resident at a time. This is automatic — no operator steps.

Verified live this session:
- Image render via API: **33.3 s → 766 KB PNG → 200 on the file route (PNG magic)**.
- Video render via API: **91.1 s → 512×736, 2.0 s MP4 → 200 (ftyp magic)**.
- Full cycle: chat (ok, 8.3 s) → render (33.3 s) → chat again (ok, 17.3 s).

## 3. AutothinK chat — saved, scrollable, bubble UI

`autothink/ui/index.html` rebuilt into a proper transcript: user bubbles right,
assistant bubbles left with model/task/time meta, typing indicator, smooth
autoscroll, Enter-to-send. **Answers are now persisted** — `server.py` stores
the reply (capped 8 KB) in the per-tenant session history, so reopening the
page replays the whole conversation from `GET /api/autothink/history`
(previously only your command was stored, never the answer). AutothinK suite:
44/44 tests pass.

## 4. Readiness labels — flipped where it is genuinely true now

- `design-studio`: concept → **Local** (real local image + video rendering).
- `autothink`: LLM-gated → **Local** (runs on the local brain; saved transcript).
- Everything else stays honest as-is.

## Still PARTIAL — what each one actually needs (the completion map)

The rule in `readiness.js` is that a green label means "genuinely works
locally now" — flipping the rest without building would be exactly the
dishonesty the file exists to prevent. What remains, per room:

| Room | Real gap | Completion step |
|---|---|---|
| ListingForge | Publish path intentionally disabled; variants/templates live | Wire the publish step only when Amazon credentials + operator approval exist (guardrail) |
| AdPilot | Creative exists; campaign actions not connected | Needs Amazon Ads API access decision |
| SocialPulse | Local workspace real; no channel connected | Channel connectors (Meta/TikTok) = external accounts decision |
| Competitor Monitor | Local observations real; competitor rows sample | Needs a live scan provider + spend approval |
| Profitability Dashboard | Economics engine real; portfolio context sample | Import real portfolio data (files work today) |
| Listing Guardian | Local records real; triage sample | Needs live listing-quality provider |
| Spreadsheet Lab | CSV ingest/export real; analysis gated | Route the analysis to the local brain (doable next session — no external dependency) |

Everything in this list is additive work, not a blocker: each row's real-data
half already functions; the missing half is either an external account
decision (Amazon/social/providers — operator calls) or a local-brain wiring
job (Spreadsheet Lab → recommended next).

## Ops notes

- The tunnel and URL are unchanged; hard-refresh the browser to pick up the
  new UI bundle (asset hash changed).
- ComfyUI is started by the launcher and safe to leave running: it loads models
  only for a render and releases them right after.
- Docs: the boundary copy in the studio and this report supersede the old
  "no local video pipeline" line in `studio/engine/presets.js`.
