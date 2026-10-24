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

Operator signs off on the Package Designer output after P1–P7 are shown with evidence.
