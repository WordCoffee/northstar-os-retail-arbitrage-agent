# Northstar OS — Disclaimer Embed Contract v1 (B6)

**Contract id:** `disclaimer-embed/v1`
**Status:** FROZEN for Phase C implementation (designed in Phase B, B6).
**Parent:** [`BFF_CONTRACT_v1.md`](BFF_CONTRACT_v1.md) · Legal basis:
[`docs/legal/TERMS_OF_SERVICE.md`](../legal/TERMS_OF_SERVICE.md) (esp. §7
Disclaimers), [`docs/legal/README.md`](../legal/README.md).
**Phase alignment:** Alpha Build Blueprint Phase B / B6 ("Per-tool contextual
disclaimer placement spec in UI and API; each paid/live/export surface has a
named disclaimer slot; no reliance on footnotes; content requirements aligned
with FTC guidance").

---

## 1. Principles

1. **Every money/decision surface carries a disclaimer in-flow** — never a
   footnote link as the only exposure. The disclaimer must be visible without
   interaction on the surface where a user could make or act on a decision.
2. **No earnings claims.** Copy never promises earnings, ROI, ACoS, or
   guaranteed results (§18 / D11 copy rules; this contract bans "unlimited"
   anywhere).
3. **Per-tool and contextual.** A Sourcescout/GG/Calculator result view, a
   live/paid action, an export, and onboarding each have distinct named slots
   with the required copy (below).
4. **Consistency with the legal docs.** Nothing here contradicts
   `docs/legal/TERMS_OF_SERVICE.md`; the footer/onboarding copy points ("See
   Terms of Service") at the legal terms.
5. **Named slots.** Every slot has a `data-slot` attribute and a canonical id
   so the D1 no-leak audit and a UI sweep can verify placement mechanically.

---

## 2. Canonical copy (required text)

**Standard block (footers / auth / onboarding):**

> Dashboards show estimates from available data — not guarantees, not a
> recommendation to buy, and not an approval to resell. Plans never flip live
> gates; live actions require a fresh named operator approval. See Terms of
> Service.

**Result-view copy (per-service result surfaces; already adopted):**

- Golden Goose workspace: *"Golden Goose Finder workspace (v2). Reads the
  finder's real opportunity output… Not a purchase authorization, and live
  scanning stays 403-gated."* plus the table legend *"Figures are per-unit
  estimates on fixture/report data, never live provider data here."* (built in
  B2 — unchanged by this contract; the contract now declares it a named slot).
- Scout / calculators: the existing `calc-callout`, `result-note`, and
  `table-note` honesty strings remain the operative copy (declared slots
  below).

**Export copy (machine-readable, matches the manifest schema in
`GOLDEN_GOOSE_SEAM_v1.md` §4):**

> Estimates only. Not a recommendation to buy or an approval to resell.

## 3. Slot registry

| Slot id (`data-slot`) | Surface | Location | Wired in B6? | Notes |
|---|---|---|---|---|
| `landing-footer` | Root landing `index.html` | `.footer-bottom` | ✅ added | visible footer line |
| `auth-login` | `static/auth/login.html` | footer under the form | ✅ added | no-footnote rule: inline + visible |
| `auth-register` | `static/auth/register.html` | footer under the form | ✅ added | same |
| `spa-footer` | `static/index.html` (SPA shell) | `#nsFooterDisclaimer` before `</body>` | ✅ added | v1 + v2 themes; token-styled |
| `hub-footer` | `static/northstar-os/index.html` | footer before `</body>` | ✅ added | zero-network hub |
| `hub-onboarding` | hub onboarding modal | under `modal-actions` | ✅ added | first-run surface |
| `gg-workspace` | SPA Golden Goose workspace | seam callout + legend | ✅ existing (B2) | never alter/remove |
| `scout-results` | SPA scout view | `table-note`/`calc-callout`/`result-note` | ✅ existing | honesty strings kept |
| `gg-export` | GG export manifests | manifest `disclaimer` JSON field | ✅ existing (B7) | `export_manifest.DEFAULT_DISCLAIMER` |
| `onboarding-spa` | SPA first-run (if a dedicated surface is added in Phase C) | reserved | not yet wired | define copy at build time; standard block |

**Aliases:** any new paid/live/export surface added in Phase C MUST register a
new row here and carry `data-slot` plus the standard block — this is the
acceptance test for C6/C8/C9 (auth/footer/onboarding embed, AutoThink approval
UI, export surfaces).

## 4. Placement rules

1. **Above/beside the decision.** Result views: the disclaimer or the honesty
   note is within the visible result area; footers use the standard block.
2. **No footnotes-only.** A link to the ToS is supplementary; the disclaimer
   text itself is present.
3. **Do not duplicate silently.** Multi-surface footers may share the standard
   block text (copy is identical by design).
4. **Honesty over brevity.** Missing values render "Unavailable"/"—", never
   fabricated zeros; disclaimers state estimates are not guarantees.
5. **Never remove existing slots.** B2's GG callout/legend and the existing
   result-note strings are contract slots; edits require update+test, never
   silent removal.

## 5. FTC-alignment notes

- Claims are limited to what data supports; no earnings/ROI/ACoS promises; no
  "unlimited"; disclaimers appear near claims that could be read as
  performance/guarantee statements (estimates, scores, tiers).
- Statutory/refund wording stays in the legal docs (`[LEGAL REVIEW REQUIRED]`
  markers), not duplicated into UI copy.
- `[LEGAL REVIEW REQUIRED]` — the final compliance review of the exact copy
  belongs with counsel at the paid-launch gate; this contract freezes
  placement/behavior, not legally-binding language.

## 6. Conformance checklist (Phase C/C6, C8, C9)

- [ ] Every listed slot present with `data-slot` + standard block (or noted honesty string).
- [ ] No footnote-only disclaimer; no "unlimited"; no earnings/ROI/ACoS claims in UI copy.
- [ ] New paid/live/export surfaces register a slot here before shipping.
- [ ] B2 GG callout/legend present and unmodified.

---

*Designed Phase B (B6), 2026-09-19. FROZEN for Phase C. Copy cross-references
`docs/legal/TERMS_OF_SERVICE.md`; nothing here overrides legal review.*