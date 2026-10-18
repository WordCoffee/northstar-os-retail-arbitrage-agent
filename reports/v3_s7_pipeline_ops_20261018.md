# V3 S7 §5.3 — Cross-service pipeline ops (AdPilot · SourceScout)

**Date:** 2026-10-18 · **Branch:** `feature/v3-simple-view` · **Status:** BUILT, tests green, local commit.

## What this closes

§5.3 had a *scoring* hook for every surface (`seo_check`). Two services also need
to **act** on the profile: AdPilot turns search terms into negatives/harvest, and
SourceScout normalises a title toward the brand's head terms. Both are now real.

## Design rules honoured

- **Deterministic, from the operator's own profile.** Matching is plain substring
  logic over the profile's clusters and competitor list. No keyword is invented.
- **Writes nothing.** Both return a suggestion/card; the operator acts. Neither
  edits a listing nor a campaign.
- **No performance claims.** A *harvest* term is "a candidate to test", not "a
  winner"; a retitle is a "compliant starting point", not a ranking promise. The
  caveats on each result say so.
- **Honest absence.** No profile → a plain error (shared `_seo_profile_or_error`);
  no search terms → an empty result plus a caveat.

## Pieces

| Piece | Where | What |
|---|---|---|
| AdPilot op | `seo_ops.py` `classify_search_terms` | Split terms → **negatives** (negative cluster / competitor) · **harvest** (head, then body) · **ignored**. |
| SourceScout op | `seo_ops.py` `retitle` | Prepend missing head terms (cluster order) while they fit the budget; truncate honestly. |
| Tools | `chat_tools.py` `seo_negatives`, `seo_retitle` (Grow focus) | Each returns an AG-UI card; share one profile resolver. |
| SocialPulse | (existing) `seo_check` `surface=social` | Framing is the surface check — no new op needed. |

## Evidence

```
python -m py_compile seo_ops.py chat_tools.py shell_focus.py                          → PY OK
python -m pytest test_seo_ops.py                                                      → 15 passed
python -m pytest test_seo_ops test_seo_learning test_seo_listing test_seo_profiles \
                  test_shell_modes test_chat_plan test_chat_core test_chat_fork \
                  test_chat_tools test_tool_gateway test_voicestudio_adapter          → 168 passed
```

`test_seo_ops.py` (15) covers: negatives from the negative cluster + competitors;
head/body harvest tagging; ignored terms; split + dedupe; negatives beating
harvest; honest empty input; retitle prepend order, no-change when present,
budget truncation, and unfittable head terms; and both tools registered in the
Grow focus with happy-path cards and honest no-profile errors.

## Honest limits / next

- Remaining S7: **§5.4 embeddings drift** (`qwen3-embedding:0.6b` + sqlite-vec) —
  this needs the embedding model lane available; I will flag it when reached.
- Nothing was pushed; all work is local on `feature/v3-simple-view`.
