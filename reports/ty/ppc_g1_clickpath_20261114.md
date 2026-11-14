# PPC G1 — the browser clickpath, not just the API (2026-11-14)

**Outcome: closed.** `tests/e2e/ppc_primary_action.spec.ts` no longer proves only that the
panel mounts; it drives AdPilot's real primary action end to end on the live stack:

**upload → propose → approve → write → download**

## What the spec does now

1. Opens `/ui/adpilot` and the `ap-bulk-action` panel (the previous assertions are kept).
2. Fetches the app's **own sample** `sp_bulksheet.xlsx` from `/ui/samples/amazon-files/` and
   uploads it through the real file input (`af-file`) — no fixture duplication, no Amazon.
3. Edits the **K300 Keyword row's bid to 1.10** in the rows table.
4. Clicks **Propose** (`af-propose`); the proposal list shows `K300` and `1.10`.
5. Clicks **Approve** on the proposal; the write button enables only from an approved row.
6. Clicks **Write change file**; `af-write-result` reports **Round-trip: PASS — only the
   approved change(s) differ** and "The original upload was not modified".
7. Clicks **Download change file**; Playwright captures the download, asserts the filename is
   `.xlsx`/`.csv` and the file is **> 1,000 bytes** on disk.
8. Closes the panel and asserts it unmounts.

## Measured

| run | result |
|---|---|
| `npx playwright test tests/e2e/ppc_primary_action.spec.ts --project=chromium-desktop` | **1 passed (4.2 s)** |
| `--project=chromium-mobile` (iPhone 12 / WebKit) | **1 passed (6.4 s)** |
| both projects after the backend restart | **2 passed (8.5 s)** |

The G1 caveat recorded in `digest_2026-11-14.md` — "proved at the API, not by a browser round
trip" — is removed. G1 now has both proofs: the API test
(`test_amazon_files_primary_action.py`, sha256 round trip) and this browser path.

## Honest limits

The sample is the app's own fake-ID bulksheet, so this proves the workflow, not a live Amazon
account. Nothing is uploaded to Amazon; the file stays local. The run persists one upload and
one change file per browser project into the dev store — that is the persistence under test,
disclosed rather than hidden.
