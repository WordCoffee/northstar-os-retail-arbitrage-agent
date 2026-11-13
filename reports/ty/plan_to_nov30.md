# Plan to Nov 30 — the core six, gate by gate

Today is **2026-11-13**. Freeze is **Nov 25** (fixes only after that), final report **Nov 30**.
Days left: **17**.

The five launch gates, unchanged:

| gate | what has to be true |
|---|---|
| **G1** | a click path that generates/produces the deliverable, **persists** it, and **reads it back** |
| **G2** | the service's own `seller` score exists on **its own surface** (not borrowed from another service) |
| **G3** | the workspace renders and its click path works (desktop + iPhone 12 WebKit) |
| **G4** | the primary action is callable with no missing credential or armed gate |
| **G5** | the independent verifier reproduces the result |

## Where each service stands, and the honest verdict

| service | gates now | verdict by Nov 30 | what would change it |
|---|---|---|---|
| **Golden Goose** | **4 / 5** (G1 G2 G3 G4) | **passes all five** — G5 is a verification run, not a build | nothing external; needs one verifier session |
| **Research** | **3 / 5** (G1 G2* G3) | **passes** if G2* is built (its own seller score, not design-studio's) and G5 runs | ~2 days of work; no owner action |
| **PPC** | **2 / 5** (G1 G3) | **passes** if G2 (adpilot's own ad copy scored) and G4 (probe-derived badges) land, then G5 | ~3 days; no owner action |
| **Design Studio** | **2 / 5** (G2 G3), G1 persistence proven | **passes only if the composer key exists**; G1 generation depends on the quiet window | owner: `OPENCODE_GO_API_KEY` (needs_you LIST-1) + RAM at render time |
| **Product pictures** | **2 / 5** (G2 G3) | same as Design Studio — it is the same surface | same |
| **Listings** | **1 / 5** (G3) | **will not pass** without the composer key; its whole deliverable is the composer | owner key + a seller score on its own surface |

**Prediction, stated plainly:** 3 of 6 pass all five gates (Golden Goose, Research, PPC), 3 do not
(Design Studio, Product pictures, Listings) unless the composer key arrives. Those three are one
owner action away from being buildable, and nothing else about them is blocked.

## Day by day (gap = gate-slots still missing, of 30)

| date | work | gate-slots gained | gap after |
|---|---|---|---|
| Nov 13 (today) | scoping fix, quiet-window cap, rotation runbook, plan, fix units 1–2 | 0 | 30 → **17** confirmed (see note) |
| Nov 14 | quiet window render lands → Design Studio **G1 generation**; Golden Goose G5 verifier | +1 or +2 | 15–16 |
| Nov 15 | Research G2*: seller briefs + scored outputs on the research surface | +1 | 14–15 |
| Nov 16 | Research G5 verifier run; Golden Goose final G5 confirmation | 0–1 | 13–15 |
| Nov 17 | PPC G2: score adpilot's own ad copy (5 outputs, deterministic checks + claims lint) | +1 | 12–14 |
| Nov 18 | PPC G4: probe-derived badges on the primary action; PPC G5 | +2 | 10–12 |
| Nov 19 | Design Studio G4 **if the key lands**: compose path end to end | +1 | 9–11 |
| Nov 20 | Product pictures G1 read-back through the same surface (shared with DS) | 0–1 | 9–11 |
| Nov 21 | Listings G1 **if the key lands**; otherwise Listings is parked and the day goes to G5s | +1 or 0 | 8–11 |
| Nov 22 | G5 sweep: independent verifier reproduces every headline number | +1–3 | 5–10 |
| Nov 23 | visual regression gate on the final shell, scenes frozen | 0 | 5–10 |
| Nov 24 | staging review packs (5–10 images per service), owner review | 0 | 5–10 |
| **Nov 25** | **FREEZE** — bug fixes and hardening only | — | 5–10 |
| Nov 26–29 | fix-only: close the smallest failing gates, no new features | +1–3 | 2–9 |
| **Nov 30** | **final report**: measured state per service, including "not production-ready" | — | final |

Note on today: the gap is **17 of 30** gate-slots — Golden Goose 1, Research 2, PPC 3, Design Studio
3, Product pictures 3, Listings 4, plus the G5s already counted. Today's work added no new gates but
closed the scoping and safety debt that would have blocked a verifier from trusting any of them.

## Private beta — invite-only, passing services only

**Runs from Nov 25, alongside the freeze.** Scope is decided by the gate table, not by enthusiasm:

| in the beta | why |
|---|---|
| **Golden Goose** | 4/5 now, 5/5 by Nov 16 |
| **Research (product-finder)** | 3/5, earning 4–5 by Nov 16 |
| **PPC (adpilot)** | 2/5, earning 3–5 by Nov 18–22 |

| held back | why |
|---|---|
| Design Studio, Product pictures | G4 depends on the composer key; a beta that cannot complete its own primary action is not a beta |
| Listings | its deliverable *is* the composer; same key |

Beta rules, non-negotiable: invite-only (no public sign-up), each invitee sees only services that
have **all five gates ticked on the day they are invited**, no payments, and a one-click "report a
problem" that files a gap. If a service regresses, it leaves the beta the same day and the digest
says so.

## What would move the three held-back services fastest

One action: the composer key (`needs_you` LIST-1). It converts three "will not pass" rows into
"passes on Nov 19–21" and takes the predicted beta from three services to six. Nothing else on the
critical path is owner-gated except the quiet window's RAM (a machine state, not a decision).
