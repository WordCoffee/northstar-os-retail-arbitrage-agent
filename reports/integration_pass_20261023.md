# Integration pass — research findings → Northstar OS (2026-10-23)

Branch `feature/v4.1-mesh`. Scope: integrate what the Marco Kaz research actually justified,
prove or reject the rest, and leave nothing in a half-wired state.

## 1. Integrated (code, tested, committed)

### 1.1 Skills plane — `95dc8e30`

Pattern ported from `coreyhaines31/marketingskills` (MIT): one foundation skill every other
skill reads first. No text copied; the four skills are Northstar-specific.

```
skills/product-marketing/SKILL.md      fact contract, audience, claims discipline, voice
skills/listing-copy/SKILL.md           title / bullets / description / backend terms
skills/ad-creative/SKILL.md            headlines / body / CTA / compliance
skills/competitor-profiling/SKILL.md   evidence ladder (observed / derived / inferred / unknown)
skills/README.md                       layout, frontmatter contract, provenance
```

Loader: `Northstar_backend/skills_plane.py` — stdlib only, offline, fails closed to `""`.

| Injection point | Behaviour |
|---|---|
| `chat_adapter.build_chat_messages` | appended only when a query is present |
| `listing_forge._build_{title,bullets,description}_prompt` | prepended; base skill always first |
| `reasoning_tasks.listing_proposal` | appended to `LISTING_PROMPT` |
| `reasoning_tasks.ad_copy_proposal` | appended to `AD_COPY_PROMPT` |

Budget is 5,500 chars with line-boundary truncation, so a skill cannot crowd out history.

### 1.2 Decision layer — `b80ed1f`

`Northstar_backend/decision_layer.py` — one typed contract
(`kind, value, confidence, abstained, flags, backend, escalate`), closed label sets, and an
explicit abstain path. Rules backend today; `laya` is a presence check (`LAYA_ROOT`) that
reports `laya_not_configured` / `laya_not_installed` rather than silently substituting.

Wired into both proposal normalisers: every listing and ad proposal now carries a
`copy_audit`, and a `block` verdict appends a warning. This is additive — existing keys,
shapes and tests are unchanged.

### 1.3 Provider suite — `cf90e7f`

`shared/provider-suite.json` went from 20 to 33 tools. New entries: `skills_plane`,
`decision_layer`, `laya`, `headroom`, `skylos`, `surya`, `sana`, `text_to_cad`, `img2threejs`,
`turbovec`, `claude_mem`, `open_design`, `open_sandbox`, plus `lightpanda` recorded as rejected
so the lane check refuses it instead of someone rediscovering it.

`test_cloud_lane_is_all_gated_when_unarmed` was updated deliberately: in-repo prompt/decision
helpers are code, not providers, so the invariant is now "every *networked or metered* cloud
tool is blocked when unarmed", not "usable count is zero".

## 2. Installed and proven

### 2.1 Skylos 5.0.0 — usable

External venv `C:\Users\T2Hol\Desktop\Northstar External\integration-venv`. Scan of the new
modules ran and produced the behaviour the loop needs: with a small grep budget it reported
**`Coverage: INCOMPLETE` and abstained** instead of calling the code clean. Windows caveat:
needs `PYTHONIOENCODING=utf-8` or its rich console crashes on box-drawing characters.

### 2.2 Headroom 0.41.0 — installed, **not adopted**

Compression needs `transformers`; installing it failed on this box (`OpenBLAS error: Memory
allocation still failed after 10 retries`). The proof script is committed and ran, with a
finding that matters more than the install:

> With the model missing, Headroom logged one stderr line and returned the input **unchanged**
> (ratio 1.0). It fails open.

A loop using it would believe it was compressing when it was not. Gate stays closed until
`tools/headroom_evidence_proof.py` shows a real ratio with every `FAILED`/`ERROR` line and the
test counts preserved.

## 3. Parked, with the actual reason

| Item | Why it is not integrated |
|---|---|
| `laya` | WIRED (optional backend) | Weights + onnxruntime installed in the integration venv; decision_layer.decide(backend="laya") shells out to the local ONNX binary. Rules backend stays primary (12/12 vs laya 6/12 on the 12-sample labelled set). |
| `text-to-cad` | Needs an OpenCascade/OCP toolchain on Python 3.14; that install is the blocker, not the licence |
| `surya` | Multi-GB weights; RapidOCR already covers the text-fidelity gate, Surya is ingestion-only |
| `sana` | Multi-GB weights and would compete with FLUX.2 Klein for the same 16 GB card |
| `img2threejs` | Depends on a vision model plus a browser render check; behind text-to-cad in value |
| `turbovec` | The knowledge plane is still small enough that keyword scoring is not the bottleneck |
| `claude-mem` | Claude Code hook architecture; `memory_bank` + `knowledge_pack` already cover storage |
| `open-design` | A separate application; adopting it is a product decision, not an install |
| `open_sandbox` | Only relevant if the build loop is containerised; it runs on the bench by design |
| `lightpanda` | No graphical rendering engine (cannot verify a UI) **and** a second browser path around Chrome Connect |
| `Agent-Reach`, `osintsearch`, `pinchtab`, `UI-TARS`, `cloudflare-os`, `threeui` | Scraping / stealth / lock-in / no product gap — reasons recorded in the research reports |

## 4. Evidence

```
test_skills_plane.py            18 passed
test_decision_layer.py          12 passed
test_provider_suite.py          24 passed   (33 tools, lane + licence invariants hold)
broader prompt suite            123 passed  (shell modes, cie, turn contract, skills warehouse, reasoning)
```

Two tests were stale before this work and were corrected: `test_shell_modes` and `test_cie`
asserted the prompt equalled `CHAT_SYSTEM_PROMPT`, but `DELIVERABLE_ROUTING` has been appended
to every prompt since it was introduced. Both now assert the real contract and that skills are
absent without a query.

## 5. Next actions

1. ~~`LAYA_ROOT` + weights~~ **DONE** — laya 0.4.14 + onnxruntime 1.31.0 (CPU) wired as `backend="laya"`; rules stays primary (12/12 vs 6/12 on the labelled set). Next: a larger labelled set and domain fine-tuning if laya is ever to be promoted.
2. Run `skylos` as the per-card gate (`skylos done --base main`) on the next build card.
3. Retry Headroom only if `transformers` can load on this box; otherwise leave it un-adopted.
4. Packaging: try `text-to-cad` in a throwaway venv before promising dieline geometry.

## 6. Commits

```
95dc8e30  feat(skills): product-marketing skills plane wired into chat, listing and ad prompts
b80ed1fd  feat(decision): typed copy audit with abstention, wired into listing and ad proposals
cf90e7f   feat(suite): register 13 tools; evidence proof + skylos install
```
