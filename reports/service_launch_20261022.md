# Service launch — 2026-10-22

Everything is running for hands-on testing.

## URLs

| service | URL | state |
|---|---|---|
| **UI** | `http://127.0.0.1:8101/ui/` | 200 |
| Improvement room | `http://127.0.0.1:8101/ui/improvement` | 200 (SPA) |
| **API** | `http://127.0.0.1:8000` | 200 |
| API docs | `http://127.0.0.1:8000/docs` | 200 |
| API detailed health | `http://127.0.0.1:8000/health/detailed` | 200 |
| Improvement health (public) | `http://127.0.0.1:8000/api/v1/improvement/health` | 200 |
| **Voice engine** | `http://127.0.0.1:8321/health` | 200 |
| Voice list | `http://127.0.0.1:8321/api/voices` | 200 |
| **Ollama** | `http://127.0.0.1:11434/api/version` | 0.40.4 |
| ComfyUI | `:8188` | **off on purpose** (see below) |

Auth is enforced: `/api/chat/*` and `/api/v1/improvement/status` return 401
without a session, as designed. Log in through the UI.

## Fixes made in this pass

1. **Frontend gate** — the route invariant still expected 52 routes; `/improvement`
   is the deliberate 53rd. Updated with a dated comment (the test's own rule is
   "update only when a route is deliberately added or removed").
2. **Flaky scale test** — `test_500_asin_5000_offer_fixture_performance` failed
   under the full-suite load and passes alone in 45.6 s. Not a regression.
3. **GPU visibility** — `/api/v1/improvement/status` now reports `gpu` (free MB,
   loaded models), `live_ready` and the reason. The Improvement room shows a
   "Live grading: ready / GPU busy" tile so a skipped live run is never a mystery.

## Full test suite

```
4154 passed, 82 skipped, 2 xpassed, 0 failed
```
(excluding three **untracked** `costco_non_kirkland/tests/test_brightdata_*.py`
files from the parallel session that import functions which do not exist in the
current module — they are that session's work in progress, not deleted here).

## Why ComfyUI is off

The 27B brain needs ~13 GB; a Wan render peaks at ~11 GB. They cannot share the
16 GB card. Starting ComfyUI evicts the brain (and an interrupted load can leave
an untracked `llama-server` holding the card, which shows up as a connection
reset). The video lane is proven; start ComfyUI only when you are rendering, and
expect chat to pause while it holds the GPU.

## Test checklist

**Chat**
1. Open `/ui/` and sign in.
2. Send: `What is required before publishing A+ content on a listing?` — expect
   an answer that names Brand Registry, with no "Sure!" preamble.
3. Switch **Mode** to *Creative*, ask for three listing concepts — expect three
   options with one-line rationales.
4. Switch **Mode** to *Thinking*, ask an ACOS/margin question — expect the
   arithmetic and a named source.
5. Click **Wrong** on an answer, type one line, send — it becomes a gap.

**Improvement room**
6. Open `/ui/improvement` — coverage 100 %, 118 questions, ~41 atoms, 0 open gaps.
7. **Dry run** — completes without writing.
8. **Stop**, then **Resume** — the badge flips; a stopped loop refuses to run.

**Voice**
9. In the composer, pick a voice and press the microphone — the transcript should
   appear; the speaker button reads the last answer.
10. If the voice engine is down, the picker says so instead of failing silently.

**Improvement engine (CLI)**
11. `cd Northstar_backend; python -m cie_loop --status`
12. `python -m cie_loop --cycle --dry-run`
13. `python -m cie_loop --cycle --dry-run --live --live-limit 2` — reports a real
    score (baseline measured: 0.65) or an explicit "not measured" with a reason.

## Known non-blockers

- `--live` grading is slow (~30–60 s per question) and serial.
- Seed atoms are `needs_verification: true` until checked against Seller Central.
- The nightly task `NorthstarOS-Improvement` runs at 02:00 and respects
  `state/improvement/STOP`.
