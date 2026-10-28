# Kernel source triage

Generated: 2026-10-28T20:53:24.257231+00:00
Scored: **1500** (cap 1500) · read targets: **100** · deep: **12** (manual, see DEEP_12.md)

## Method

- GitHub search metadata (15 query families, 100/page, public API).
- Existing local corpus rows filtered to agent/kernel terms.
- Deterministic capability tags + stars; no model judgement at this scale.
- READMEs for the 100 read targets are stored under `readmes/`.
- No bundle analysis, no decompilation, no login, no paid source.

## Licence histogram

| licence | count |
|---|---|
| mit | 579 |
| none | 421 |
| apache-2.0 | 202 |
| noassertion | 152 |
| gpl-3.0 | 35 |
| cc0-1.0 | 34 |
| agpl-3.0 | 32 |
| unlicense | 11 |
| cc-by-sa-4.0 | 6 |
| bsd-3-clause | 6 |
| cc-by-4.0 | 6 |
| gpl-2.0 | 6 |
| mit-0 | 4 |
| mpl-2.0 | 2 |
| lgpl-3.0 | 2 |
| wtfpl | 1 |
| 0bsd | 1 |

## Capability coverage

| capability | sources |
|---|---|
| skills | 268 |
| commerce | 210 |
| artifact | 185 |
| verify | 130 |
| context | 120 |
| diff | 117 |
| memory | 102 |
| journal | 84 |
| dag | 79 |
| subagent | 69 |
| voice | 66 |
| plan | 62 |
| checkpoint | 32 |
| budget | 23 |
| policy | 20 |

## Honest limits

- Metadata scoring identifies *candidates*; it does not prove quality.
- The 100 read targets are README-level reads, not full source reviews.
- The 12 deep reads are the only sources whose behaviour is specified in `KERNEL_SPEC.md`.
