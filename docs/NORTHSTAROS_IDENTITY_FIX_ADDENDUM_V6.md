# NorthstarOS — v6: Keepa escalation update + Report Discipline fix

Supersedes NORTHSTAROS_IDENTITY_FIX_ADDENDUM_V5.md for the escalation clause. Adds a new protocol-level fix (Part A of this file) that amends Part 1.2 of the master plan directly — apply this regardless of which identity-fix version is active, it's unrelated to the Amazon-access exclusions.

---

## Part A — Report Discipline (amends Part 1.2 of the master plan)

**Problem observed:** OpenCode's visible output is filling with step-by-step narration ("Let me check...", "Hmm, but...", "Given time, maybe...") before reaching the mandated closing REPORT FORMAT block. On at least one run, real completed work (P2-T4, verified DONE — 45/45 postgres tests passed against a self-spun disposable PG, torn down cleanly) never got a closing report at all because narration consumed the output budget first.

**Fix — add to Part 1.2, as a hard rule, not a style preference:**

> **Report Discipline.** Tool calls, shell commands, and their raw output may appear in the visible transcript — that's expected working evidence. Prose narration explaining *why* a step is being taken, restating options already decided, or thinking aloud about implementation choices must not appear in the visible transcript. Decide silently; show only the command and its result.
>
> **Budget checkpoint.** Before starting any new exploration, edit, or additional tool call within a card, check remaining output budget. If it is constrained, stop immediately and print the REPORT FORMAT block for the current state — mark STATUS: PARTIAL if the card isn't finished, and say exactly what's left in NEXT. A partial-but-reported card is correct behavior. A finished-but-unreported card is a protocol violation, even if the underlying work was done right.
>
> **No silent trailing-off.** A session must never end without a REPORT FORMAT block being the last thing printed. If a session is at risk of ending mid-work, the last visible action must be printing that block with whatever is true at that moment.

**Accept for this fix:** Next session's transcript closes with a REPORT FORMAT block as its final output, regardless of whether the underlying card finished. Narration lines describing internal deliberation ("let me," "hmm," "given time") do not appear in the visible transcript.

---

## Part B — Escalation clause update (supersedes v5's P4-T4b)

Replace the escalation step in **P4-T4b** with:

> **Escalation path (not default):** if refresh volume becomes steady and exceeds a few hundred ASINs/month, `ASK OWNER` whether to switch to **Keepa** (Starter tier, ~€49/mo) as the preferred upgrade over ASINSpotlight. Rationale: SellerSprite — which supplied the existing 31,992-ASIN local snapshot — is itself a reseller of Keepa's underlying data with a markup on top; the owner has decided not to renew SellerSprite. Going directly to Keepa when a real refresh/history need arises skips that reseller layer, and Keepa's actual price/BSR history (not just a point-in-time value) is what upgrades the BSR-stability component in `resale_score` — something a per-request refresh API like Canopy or ASINSpotlight can't provide regardless of price. ASINSpotlight remains a fallback only if Keepa's token-rate model doesn't fit the actual refresh cadence once real volume is known.

Everything else in v5 (Amazon-access exclusions, P4-T0/T0b/T2b/T2c/T2d, the scoped-not-blanket refresh rule) is unchanged.

---

## Resume note

Send Part A to OpenCode immediately — it's a standing protocol fix, apply it before the next card regardless of what else is in flight. Part B only matters once a real Keepa-vs-ASINSpotlight decision point is reached; no immediate action needed on it.
