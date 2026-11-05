# Self-assessment — what Ty is, ranked by what actually blocks the program

Written 2026-11-05 after the Phase A probes, not before them. Every claim here
maps to a row in `capability_probe.md`.

## What Ty can do now (with evidence)

| Capability | Evidence |
|---|---|
| Read, search and measure its own machine and repo | `_a1_snapshot.txt`, 893-file working tree enumerated, 6,196-test suite parsed |
| Plan on disk and resume from disk alone | queue/plan/handoff files; fresh-process resume printed the next unfinished item |
| Write and run real code, then verify it | 4 commits this session, each with tests: 20 (research/MCP), 7 (context), 10 (scorecard), 10 (reference library) |
| Research the web and code hosts with a hard Amazon refusal | `web_research.py` GitHub/HF/README/LICENSE + `REFUSED: amazon_refused` |
| Consume MCP servers | 2 tools listed, `add(2,3)=5` |
| Vet a package before installing it | OSV clear/refuse, transport failure = refusal |
| Generate a product image locally on demand | FLUX 3 Klein, 1024², 36.3 s, peak 11.7 GB VRAM |
| Judge an image against a brief | gemma3:4b rubric JSON in ~17 s, valid, and it caught a real defect |
| Generate from a stored or uploaded reference | 48.7 s / 75.8 s, reference-conditioned |
| Drive the UI and prove what it saw | Playwright Chromium + iPhone 12 WebKit, screenshots |
| Roll back | tag -> change -> restore, `git diff` empty |
| Score a workstream numerically | 8-dimension product-picture scorecard + 60-case fixed bench |
| Run unattended until the queue empties | supervisor `completed=34 failed=0`, stops at `queue_blocked` |

## What Ty cannot do yet, ranked by cost to the program

1. **Author its own task cards from a failure.** A failing test becomes a
   `needs-author` proposal, not work. This is the single biggest brake: the
   supervisor is idle by construction whenever the queue drains, which it is
   right now (`remaining=0`). Everything else on this list can be worked around;
   this one cannot.
2. **Measure a workstream without hand-built instruments.** Only Product
   Pictures has a scorecard as of today. The other thirteen workstreams have no
   number, so "improved" cannot be proven for them.
3. **Keep a reference library wired into the product.** The library exists and
   is live-seeded, but `/api/design-studio/*` does not yet accept "use reference
   #id". A seller cannot reach it.
4. **Guarantee text fidelity on a reference render.** The stored-reference
   probe produced `KERT& SLATE / D4/1z 250%` — the model drew text even though
   the rule says only the vector layer may. The text-safe guard is on the
   `product_picture.produce` path, not on raw `generate_reference`.
5. **Render when the desktop is fully resident.** 2.3-3.1 GB free is normal with
   Chrome + Claude Desktop + ComfyUI; the render floor is 4 GB. The lane is
   correct to refuse, but it means renders must be scheduled, not assumed.
6. **Use the cloud lane at all.** Not a defect — a gate. `CLOUD_MODEL_LIVE` is
   not armed and no spend is authorized.
7. **Compact a session that is not the coding agent.** The harness's own context
   is not something Ty controls; the in-repo fix only covers `CodingAgent`.

## What Ty needs, in the order that unblocks the most

1. **An author/evaluator for backlog proposals** (best-of-N patches scored
   against the failing test, the regression suite, the semantic validators and a
   separate reviewer). Without it the loop is a queue-runner.
2. **One scorecard per workstream**, each with a held-out set fixed before work.
   Copy the Product Pictures pattern.
3. **A scheduler that hands the GPU back and forth** between brain and render,
   so a cycle does not stall on a RAM refusal.
4. **The reference id in the API contract**, so the library is a product feature
   rather than a tool.
5. **A production-safe VL model** (see `replace_later.md`); gemma3:4b works but
   is not OSI-licensed.

## Honest limits of this assessment

- One session, one box. Throughput numbers (36 s/render, 17 s/vision) are for
  1024 px draft on an RTX 5080 Laptop with 16 GB RAM, not a production host.
- The 27B text model named in the work order (`northstaros-qwen3.8:27b`) is not
  installed on this machine any more; the local text tier resolves to `bojo`.
  So "the 27B came back healthy" could not be tested — the brain that was
  verified healthy after the render is `bojo`.
- Two probe areas (A3, A10) are recorded PARTIAL rather than massaged into
  PRESENT. That is deliberate: a probe whose answer is "yes" because the
  question was softened is worse than no probe.
