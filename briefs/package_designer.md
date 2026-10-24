# Brief — Package Designer output (§11C)

**In the operator's words:** *"Bojo does not build a full package: no front label, back label, side
panels, or dieline logic… Packify-style tools work because they collect dimensions and panel content
first."* And: *"a product image for Mogra Organics Lion's Mane, 6 oz stand-up pouch."*

## Intended experience

You describe the product; Bojo asks for the legal facts it cannot invent, then returns a **complete
package**, not one picture: front, back, side, a flat sheet you can review, the dieline, and a
mockup of the real pack carrying the real logo and the real copy.

## Pass/fail checks (7)

| # | Check | Evidence |
|---|---|---|
| P1 | A vague request ("make my pouch") produces **questions**, not artwork | screenshot |
| P2 | The six required facts are enforced: product, net weight, dimensions, ingredients/facts, company, address, country of origin | tool output |
| P3 | Output contains **front + back + side + flat sheet + dieline (SVG and PDF) + mockup** | asset list |
| P4 | Back panel carries ingredients, warnings, company, origin, and a **reserved barcode zone** — never a fake barcode | screenshot of the back panel |
| P5 | Copy is **drawn, never generated** — spelling matches the input exactly | visual check vs input string |
| P6 | A missing fact is rendered as `[MISSING: field]`, never invented | screenshot |
| P7 | The mockup shows the **front panel plus gussets** with correct proportions (no clipped text, no seams) | screenshot |

## Non-goals

Not a die drawing. Geometry is planning-grade; the converter's die is the authority, and the output
says so.

## Sign-off

**Operator approved P1–P7 on 2026-10-24.** Evidence on disk, all seven:

| # | Evidence |
|---|---|
| P1 | `reports/northstar_acceptance_20261023/screenshots/05-scenarioA-chat-result.png` — questions before artwork |
| P2 | tool output enforcing the six facts (product, net weight, dimensions, ingredients, company, address, origin) |
| P3 | `screenshots/phase3-front.png`, `phase3-back.png`, `phase3-side.png`, `phase3-sheet.png`, `phase3-dieline.svg`, `phase3-dieline.pdf`, `scenarioA-labelled-v3-ui.png` |
| P4 | `screenshots/phase3-back.png` — ingredients, warnings, company, address, origin, and a boxed `BARCODE ZONE (RESERVED) / supply GTIN/UPC at print`, no fake barcode |
| P5 | copy drawn not generated; spelling matches the input string in the same capture |
| P6 | `LOT [MISSING: lot code]` rendered in the artwork itself |
| P7 | `scenarioA-labelled-v3-ui.png` — front panel plus gussets, no clipped text |

**Known cosmetic defect, accepted at sign-off:** the back panel prints the country twice (the address
line already ends `USA`, and the origin line adds `USA`). Both required fields are present and correct;
it is recorded rather than silently fixed because a fix would invalidate the capture above.
