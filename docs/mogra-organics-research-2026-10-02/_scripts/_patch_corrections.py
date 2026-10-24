# Renumber PDF sections and correct the route + economics sections.
import io, os
p = os.path.join("docs","mogra-organics-research-2026-10-02","_scripts","build_launch_pdf.py")
s = io.open(p, encoding="utf-8").read()

# --- renumber remaining section headings (avoid the new 5/6/7) ---
ren = [
 ('P("7. Package formats and positioning"','P("8. Package formats and positioning"'),
 ('P("8. Wholesale suppliers matched to products"','P("9. Wholesale suppliers matched to products"'),
 ('P("9. Initial-launch vs long-term sourcing routes"','P("10. Sourcing routes (corrected language)"'),
 ('P("10. Cost coverage and scenario economics"','P("11. Cost coverage and hypothetical economics"'),
 ('P("11. Amazon listing and advertising plan"','P("12. Amazon listing and advertising plan"'),
 ('P("12. Dated launch critical path"','P("13. Dated launch critical path"'),
 ('P("13. December sales and inventory scenarios"','P("14. December sales and inventory scenarios"'),
 ('P("14. Risks and contingency"','P("15. Risks and contingency"'),
 ('P("15. Owner decisions and immediate next actions"','P("16. Owner decisions and immediate next actions"'),
]
for a,b in ren:
    if a not in s: print("MISSING heading:", a)
    s = s.replace(a,b)

# --- correct route claims ---
old_routes = '''st += [P("10. Sourcing routes (corrected language)",st_h1), rule(),
 tbl(["Route","Initial launch","Long term"],
 [["A Overseas finished / private-label (Pearl)","Best if Pearl packing is certified and fast","Concentration risk; re-bid"],
  ["B Overseas bulk + US co-packer","Good control; import + organic-importer burden","Strong margin potential"],
  ["C US turnkey (McKinney TX cluster)","Fastest, no import","Likely higher ingredient cost"],
  ["D US ingredients + US packing","Fallback","Domestic simplicity"]],
 [2.2*inch,2.5*inch,1.9*inch]), Spacer(1,5),
 P("<b>No route is proven cheapest.</b> For a Nov 15 target, Route C or A is fastest; Route B is stronger long-term but adds import lead time and obligations.")]'''
new_routes = '''st += [P("10. Sourcing routes (corrected language)",st_h1), rule(),
 tbl(["Route","Launch role","Characterisation (corrected)"],
 [["A Overseas finished / private-label (Pearl)","candidate","<b>Potentially fastest</b> to a finished unit IF packing is certified and lead time is short — UNPROVEN"],
  ["B Overseas bulk + US co-packer","candidate","<b>Cost hypothesis</b>: bulk pricing may improve margin; import lead time and obligations are unquantified"],
  ["C US turnkey (McKinney TX cluster)","candidate","<b>Potentially fastest</b> (no import) — UNPROVEN"],
  ["D US ingredients + US packing","fallback","Domestic simplicity; cost unproven"]],
 [1.9*inch,0.85*inch,3.85*inch]), Spacer(1,5),
 callout("Withdrawn claims",
 "Prior statements that any route is “fastest” or has “best long-term margin” are WITHDRAWN as unsupported — no comparable lead times or sufficiently "
 "complete costs exist. No route is proven cheapest or fastest.",tone="warn")]'''
if old_routes not in s: print("MISSING routes block")
s = s.replace(old_routes, new_routes)

# --- correct economics section ---
old_cost = '''st += [P("11. Cost coverage and hypothetical economics",st_h1), rule(),
 P("<b>Known prices: three, all US domestic retail references — none a wholesale quote.</b>"),
 tbl(["Item","Price","Type"],
 [["Flavoric organic turmeric","$12.98–$111.98/lb","PUBLISHED_RETAIL_REFERENCE"],
  ["Flavoric organic black pepper","$49.98–$369.98/lb","PUBLISHED_RETAIL_REFERENCE"],
  ["Spices Inc chipotle salt","$6.55/unit","PUBLISHED_RETAIL_REFERENCE"]],
 [2.3*inch,2.1*inch,2.2*inch]), Spacer(1,5),
 P("<b>Unknown (left blank, never zero):</b> ingredient, processing, packaging, packing, setup, testing, freight, duty/AD-CVD/broker, storage, Amazon FBA fees, PPC."),
 P("<b>Formula (per unit):</b> contribution = price − (ingredient + packaging + packing + testing allocation + inbound) − (referral fee + FBA fee) − advertising. <b>Do not double-count freight.</b>"),
 P("<b>Scenario A (Ceylon cinnamon 2 oz) — illustrative only:</b> pilot 500 units (<b>PROPOSED</b>, not owner demand). Because ingredient, packing and fees are UNKNOWN, <b>no contribution figure is presented</b>. Maximum acceptable finished-unit cost and break-even ACOS cannot be computed until quotes exist.")]'''
new_cost = '''st += [P("11. Cost coverage and hypothetical economics",st_h1), rule(),
 P("<b>Known prices: three, all US domestic retail references — none a wholesale quote.</b>"),
 tbl(["Item","Price","Type"],
 [["Flavoric organic turmeric","$12.98–$111.98/lb","PUBLISHED_RETAIL_REFERENCE"],
  ["Flavoric organic black pepper","$49.98–$369.98/lb","PUBLISHED_RETAIL_REFERENCE"],
  ["Spices Inc chipotle salt","$6.55/unit","PUBLISHED_RETAIL_REFERENCE"]],
 [2.3*inch,2.1*inch,2.2*inch]), Spacer(1,5),
 P("<b>Preserved as null (never zero):</b> ingredient, processing, packaging, packing, setup, testing, freight, duty/AD-CVD/broker, storage, FBA fees, PPC."),
 P("<b>Formulas (shown without validated results):</b>"),
 tbl(["Metric","Formula"],
 [["Max acceptable finished-unit cost","price − referral − FBA fee − target contribution"],
  ["Contribution before advertising","price − referral − FBA fee − landed unit cost"],
  ["Break-even ACOS","contribution before advertising ÷ price"]],[1.9*inch,4.7*inch]),
 Spacer(1,5),
 callout("HYPOTHETICAL illustration — every input assumed, NOT a forecast, NOT validated",
 "Ceylon cinnamon 2 oz: 12.99 − (12.99×0.15) − 3.50 − 4.00 = <b>3.54/unit</b>; break-even ACOS = 3.54 ÷ 12.99 = <b>27.3%</b>. "
 "Whole black pepper 3 oz: 11.99 − 1.80 − 3.50 − 3.50 = <b>3.19/unit</b>; break-even ACOS = <b>26.6%</b>. "
 "Assumed: price, 15% referral, FBA fee $3.50, landed cost $3.50–$4.00. <b>No supplier quote, CPC or sales forecast is invented.</b>",tone="warn"),
 P("<b>Initial inventory (500 units) is PROPOSED illustrative only.</b> Cash exposure = 500 × landed unit cost, which cannot be computed. Full detail: hypothetical_economics.csv (26 lines)."),
 P("<b>Pricing-lines reconciliation (54 → 15):</b> the earlier 54 figure came from a malformed intermediate CSV whose unquoted commas split rows and inflated a naive count. "
   "The rebuilt table contains <b>15</b> genuine pricing lines, because most suppliers publish no price. The 54 figure is WITHDRAWN.",st_small),
 P("<b>Pricing lines (15) ≠ economics lines (17).</b> Pricing lines are one row per actual price or explicit quote-required position; economics lines are one row per cost/price component in a modelled SKU, many UNKNOWN or FORMULA_ONLY.",st_small)]'''
if old_cost not in s: print("MISSING cost block")
s = s.replace(old_cost, new_cost)

io.open(p,"w",encoding="utf-8").write(s)
print("patched and renumbered")
