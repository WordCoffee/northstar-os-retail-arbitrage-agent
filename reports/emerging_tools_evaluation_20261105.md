# Emerging tooling evaluation — 2026-11-05

Scope: the four candidates named in the Ty's Assistant continuous-improvement work
order — Crawl4AI, Scrapling, LlamaParse, Docling — assessed against Northstar's own
adoption gate (`Northstar_backend/provider_suite.py`, registry `shared/provider-suite.json`).

Nothing was installed, armed or called. No spend, no Amazon, no credentials.

## Method

1. Upstream licence read from the repository's own `LICENSE` file (not a blog or a
   summary), so the licence column is evidence, not recall.
2. The repo gate was asked directly:
   `python Northstar_backend/provider_suite.py --check <id> --provider local`.
3. A verdict is only ever ADOPT / CANDIDATE / REFUSED. A refusal states which rule
   refused it. No licence is reclassified to make a lane work.

## Licence evidence (fetched from upstream `LICENSE`, HTTP 200)

| tool | upstream licence file says | commercial use |
|---|---|---|
| Crawl4AI (`unclecode/crawl4ai`) | Apache License 2.0 | permitted |
| Scrapling (`D4Vinci/Scrapling`) | BSD 3-Clause | permitted |
| Docling (`docling-project/docling`) | MIT | permitted |
| LlamaParse | hosted service, no source licence | commercial API, metered |

## Gate result

```
$ python Northstar_backend/provider_suite.py --check crawl4ai  --provider local
  NOT available on local - unknown_tool
$ python Northstar_backend/provider_suite.py --check docling   --provider local
  NOT available on local - unknown_tool
```

`unknown_tool` is a refusal, not a warning. None of the four is in the registry, so
none may be used by any lane until an entry is added and verified. That is the
correct default.

## Verdicts

### Crawl4AI — REFUSED (policy, not licence)

The licence (Apache-2.0) is fine for both lanes. The refusal is structural:
Crawl4AI is a headless-browser crawler with its own Playwright driver. Northstar's
standing rule is that **Chrome Connect is the controller and Playwright is only its
tool** — no script, agent or manual call may drive a browser directly. A general
crawler wired into the pipeline would be a second, unguarded path to the web,
outside the host denylist, the Amazon blocklist, the profile lease and the audit
hash chain.

Verdict: **not adopted.** Any future use must run *through* Chrome Connect as its
execution tool, not beside it. There is no version of this that is a
`provider_suite` entry.

### Scrapling — REFUSED (policy, not licence)

Same reasoning: BSD-3-Clause is fine, but Scrapling ships its own stealth fetcher
and browser session layer. It would bypass the controller boundary in the same way.

Verdict: **not adopted.** The parsing half of Scrapling (its adaptive selector
engine) is interesting, but it is only separable by taking the browser half with
it. Not worth the boundary.

### Docling — CANDIDATE (local lane)

MIT, local, no network by default, and it fills a gap Northstar actually has:
turning supplier catalogues, spec sheets and PDF line-cards into structured data.
The repo already uses RapidOCR (Apache-2.0) for text-in-image checks and lists
Surya (Apache-2.0, not installed) for OCR; Docling adds layout + table extraction
on top, which is the part that is currently done by hand.

Verdict: **candidate, not adopted.** Next step is an operator decision to add a
registry entry with `lanes: ["local"]`, `license: MIT`, `network: false`, then
`--check docling --provider local` must pass before any import. Not done here: an
unverified entry is worse than a missing one, and `shared/` is outside this loop's
commit allowlist by design.

### LlamaParse — REFUSED (standing gate: spend)

It is a metered hosted API. Adopting it means spending money and sending supplier
documents to a third party, which is standing gate (a). It is not a licence
question and cannot be resolved by the agent.

Verdict: **refused pending explicit operator approval.** Docling covers the same
need locally and for free, so there is no reason to ask yet.

## What this changes in the pipeline

Nothing is wired. The only durable output is this verdict set:

- scraping: Chrome Connect stays the single web path; no new crawler.
- documents: Docling is the one candidate worth an operator decision.
- The gate's `unknown_tool` refusal is working as intended and was left alone.

## Gates held

No install, no download, no model pull, no spend, no Amazon, no credential read,
no policy or allowlist edit. Licence facts are from upstream `LICENSE` files.
