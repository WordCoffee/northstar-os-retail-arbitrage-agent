# Marco Kaz shorts — repo extraction for Northstar OS

> **Superseded in part (2026-10-23):** the captions carry no URLs; the thumbnails do. See
> `reports/marco_kaz_thumb_scan_20261023.md` for the OCR pass over 265 thumbnails and the
> real shortlist. This file stays as the caption-pass record and the reject table.

**Date:** 2026-10-22 · **Branch:** feature/v4.1-mesh · **Trigger:** operator asked to scan the
creator's reels for repos worth adopting. Facebook was unreachable without a logged-in
browser, so the same clips were taken from his YouTube Shorts channel (`@MarcoKaz`), which
`yt-dlp` can read without a browser.

## 1. What was actually done

| Step | Result |
|---|---|
| Shorts enumerated | **263** (`yt-dlp --flat-playlist`) |
| Auto-captions downloaded | **526** VTT (en + en-orig), 1.7 MB |
| Transcripts parsed | **263** |
| GitHub URLs in captions/descriptions | **0** — he says "comment X for the repo"; descriptions are empty |
| Tool names recovered from speech | **38** (`extract_repos.py`, patterns `called` / `named` / `search for`) |
| Names resolved to real repos + metadata-verified via GitHub API | **12** |

His GitHub account (`Kazandjieff`) is empty: 0 repos, created 2026-03-16. He is a curator,
so the only durable output is the repo list, not his code.

**Not claimed:** the videos were not watched; runtime claims in them were not tested; nothing
was installed; star counts are a popularity signal, not a quality proof.

## 2. Verified shortlist

Metadata pulled from `api.github.com/repos/<owner>/<repo>` on 2026-10-22.

| Repo | ★ | Licence | Lang | Last push | Lane | Verdict for Northstar |
|---|---:|---|---|---|---|---|
| `headroomlabs-ai/headroom` | 77,582 | Apache-2.0 | Python | 2026-10-22 | cloud OK | **Trial first.** Compression layer for agent context; wraps `opencode` directly |
| `2akouwu/reverify` | 1,312 | MIT | Python | 2026-10-01 | cloud OK | **Trial second.** Deterministic claim checking + session rollover; names OpenCode support |
| `Graphify-Labs/graphify` | 133,165 | Apache-2.0 | Python | 2026-10-22 | cloud OK* | Pattern worth copying; needs Claude Code + Claude vision |
| `github/spec-kit` | 142,492 | MIT | Python | 2026-10-22 | cloud OK | Optional: formalise cards into specs |
| `opensandbox-group/OpenSandbox` | 16,075 | Apache-2.0 | Python | 2026-10-23 | cloud OK | Only if the builder is containerised later |
| `jchanvfx/NodeGraphQt` | 1,836 | MIT | Python | 2026-03-11 | cloud OK | Nice-to-have UI, no core gap |
| `bytedance/UI-TARS-desktop` | 39,369 | Apache-2.0 | TypeScript | 2026-10-09 | cloud OK | Reject: GUI/browser control conflicts with Chrome Connect |
| `onyx-dot-app/onyx` | 32,879 | NOASSERTION | Python | 2026-10-23 | blocked | Reject: licence unverified, 295 MB, overlaps knowledge plane |
| `Panniantong/Agent-Reach` | 101,083 | MIT | Python | 2026-10-20 | cloud OK | Reject: scrapes Twitter/Reddit/YouTube — ToS + guardrail conflict |
| `lightpanda-io/browser` | 36,878 | AGPL-3.0 | Zig | 2026-10-23 | local only | Reject: second browser path around Chrome Connect |
| `sandbox-quantum/switch` | 1,292 | NOASSERTION | Python | 2026-10-23 | blocked | Reject: chat-channel agent ops, not a build need |
| `duriantaco/ravage` | 54 | Apache-2.0 | Python | 2026-10-12 | cloud OK | Reject: offensive-security tooling, out of scope |

\* Apache-2.0 is commercially fine; the cloud caveat for graphify is data flow, not licence —
it is a Claude Code skill that sends files and images to Anthropic vision.

## 3. The three that matter

### 3.1 Headroom — the cost lever for continuous building

- Compresses tool outputs, logs, RAG chunks, files and conversation history **on the machine**
  ("no prompt or file content is sent anywhere to be compressed").
- Ships `headroom wrap opencode`, plus a proxy (`--port 8787`), a library, and an MCP server.
- Originals are cached and retrievable (`headroom_retrieve`) rather than discarded.

**Why it fits:** the loop's dominant cost is context, and our own test output is the fattest,
most repetitive input we have (3,400-test tree, long tracebacks). The protocol's evidence rule
is the risk: lossy compression must never eat a `FAILED` line or a count. That is testable in
one sitting against our own pytest output, with a hard pass/fail.

### 3.2 Reverify — evidence discipline as a tool

- Model proposes a claim; deterministic tools check it against the artifact; output is
  `VERIFIED` / `REFUTED` with evidence. The model never asserts a fact alone.
- `reverify rollover` hands a long session to a file and starts fresh — the drift/`/clear`
  problem the continuous protocol already has a stop rule for.
- README names Claude Code, Codex, Gemini CLI and **OpenCode** as supported.

**Why it fits:** "real test counts + real command output only" is currently enforced by prose.
Reverify makes it mechanical. Caveat: 1.3k stars, one-month-old project — trial on a throwaway
card before it touches a DONE claim.

### 3.3 Graphify — the context map, with a string attached

- 133k stars, turns a folder (code, PDFs, schemas, images) into a persistent `graph.json`,
  an HTML graph, an Obsidian vault and a wiki; SHA256 cache so re-runs only touch changed files.
- Claims 71.5× fewer tokens per query versus re-reading raw files.

**Why it is not first:** it is a **Claude Code skill** that uses Claude vision for multimodal
extraction, so it is a cloud dependency in disguise, and its skill format is not native to
OpenCode. The durable idea — a cached, queryable graph of this repo — is worth building
locally later; adopting the skill now would add a second agent runtime to the bench.

## 4. Explicit rejects and why

| Item | Reason |
|---|---|
| Lightpanda (Zig headless browser) | AGPL-3.0 network clause unreviewed → local only; and it is a second browser path, which the capsule forbids |
| "12 MB browser bridge with stealth injection" short | Bot-detection evasion. Excluded without identifying it further |
| Agent-Reach | Scrapes Twitter/Reddit/YouTube with zero paid APIs — platform ToS and the read-only Chrome Connect rule both point the other way |
| UI-TARS desktop | Browser + desktop GUI control outside the controller; would need a new policy class before it could be considered |
| Onyx / switch | Licence unverified (`NOASSERTION`) and both duplicate things we already own |
| Ravage | Authorised-testing security CLI; no Northstar gap |
| NodeGraphQt, spec-kit | Genuinely fine, but neither closes a gap the build loop is hitting today |

## 5. Recommendation

1. **Headroom trial (local, no spend):** wrap `opencode`, run a fixed pytest subset twice
   (wrapped vs not), and diff the transcripts for dropped `FAILED` / `passed` counts. Pass
   only at zero lost evidence lines; otherwise `headroom unwrap`.
2. **Reverify trial (local, no spend):** run `reverify verify` on one card's claims and one
   `rollover` across a long session. Judge it on whether it catches a claim we would have
   waved through.
3. **Everything else:** park. The channel is a trending firehose; 5 of 263 shorts map to a
   real gap or a cheap option, and two of those are the same gap seen from opposite ends
   (context cost, evidence integrity).

## 6. Artifacts

- `research/marco_kaz_20261022/extract_repos.py` — VTT cleaner + extractor, no network
- `research/marco_kaz_20261022/mentions.csv` — 38 named-tool mentions with video ids
- `research/marco_kaz_20261022/repos_found.jsonl` — per-video evidence lines
- `research/marco_kaz_20261022/README.md` — re-run instructions (`subs/` is git-ignored)
