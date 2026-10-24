# Skills plane

Markdown skills the agent reads before generating listings, ads or packaging copy.

**Pattern provenance:** the "one foundation skill that every other skill reads first" structure is
ported from `coreyhaines31/marketingskills` (MIT, 56k★, verified 2026-10-23). No text was copied —
the content here is Northstar-specific, and it is deliberately narrower (Amazon FBA + retail
arbitrage, not SaaS growth).

## Why it exists

Listings, ads and packaging copy were generated with no shared brand context, so each task
re-derived (or invented) the product's facts. The failure mode is visible in the operator review:
the model "didn't see" an attachment and asked for a re-send. A single base skill that states the
fact contract fixes the class of bug, not one instance.

## Layout

```
skills/
  product-marketing/SKILL.md      always loaded; fact contract + claims discipline
  listing-copy/SKILL.md           title / bullets / description / backend terms
  ad-creative/SKILL.md            headlines / body / CTA / compliance
  competitor-profiling/SKILL.md   evidence ladder + what to extract
  operator-setup/SKILL.md         checkpoint-verified onboarding (AgentConnect pattern)
```

Frontmatter keys the loader understands:

| Key | Meaning |
|---|---|
| `name` | stable id; must match the directory name |
| `description` | one line, used for routing and for the catalog |
| `triggers` | comma-separated keywords that route a query to this skill |
| `always` | `true` = included in every block (only `product-marketing` today) |

## Loader

`Northstar_backend/skills_plane.py` — stdlib only, no network, fails closed (returns `""`).

```python
import skills_plane
skills_plane.catalog()                       # [{id, name, description, triggers, always}]
skills_plane.context_block("amazon title")   # base skill + listing-copy, budgeted
skills_plane.context_block(ids=["ad-creative"])
```

## Where it is injected

| Path | Injection |
|---|---|
| `chat_adapter.build_chat_messages` | appended to the system prompt when a query is present |
| `listing_forge._build_*_prompt` | prepended to every listing prompt |
| `reasoning_tasks.listing_proposal` | appended to `LISTING_PROMPT` |
| `reasoning_tasks.ad_copy_proposal` | appended to `AD_COPY_PROMPT` |

No-skill behaviour is unchanged: with no query and no explicit ids, `context_block` returns `""`
and the legacy prompt stays byte-identical (pinned by `test_shell_modes` and `test_cie`).

## Adding a skill

1. Create `skills/<id>/SKILL.md` with frontmatter (`name` = `<id>`, `description`, `triggers`).
2. Keep it under ~120 lines. It is prompt budget, not documentation.
3. Add a case to `test_skills_plane.py` if it changes routing.
