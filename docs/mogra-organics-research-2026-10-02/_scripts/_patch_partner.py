# Patch the launch PDF: new parameters, partner packet, dated plan, gates.
import io, os
p=os.path.join("docs","mogra-organics-research-2026-10-02","_scripts","build_launch_pdf.py")
s=io.open(p,encoding="utf-8").read()

# 1) cover target line
s=s.replace('["Target","Buyable inventory by 2026-11-15 (planning target, not a commitment)"],',
            '["Target","Buyable Amazon inventory by 2026-11-25 (latest acceptable 2026-12-01) — planning target"],\n  ["Product budget","$1,500–$2,500 (product only; advertising shown separately)"],\n  ["Assortment","2–4 SKUs, contingent on MOQ and economics"],\n  ["Fulfilment","Food filling and sealing outsourced; artwork supplied by us"],')
s=s.replace('"T2Holdings LLC · target Nov 15 2026 (planning) · "','"T2Holdings LLC · target Nov 25 2026 (latest Dec 1) · "')

# 2) decision-brief callout update
s=s.replace('"Decisions: final 2 SKUs · legal entity spelling · package format · route · budget ceiling. "','"Decisions: final 2–4 SKUs · legal entity spelling · package format · route · label application model. "')

# 3) insert new sections before appendices
NEW = r'''# 17 PARTNER DECISION PACKET
st += [PageBreak(), P("17. Partner decision packet", st_h1), rule(),
 P("Providers compared on the SAME product specification and quantity basis. Full detail: partner_decision_packet.csv (8 providers). "
   "Every unknown field is marked <b>QUOTE REQUIRED</b> — no price is invented.")]
pp=rows_of("partner_decision_packet.csv")
st += [tbl(["#","Provider","Country","Capability","MOQ","Price","Cust. ingredient?","Our labels?","Priority"],
 [[r["provider_id"].replace("PP-",""),trunc(r["company"],26),trunc(r["country"],16),trunc(r["capability"],40),
   trunc(r["moq"],18),r["price_status"],trunc(r["customer_supplied_ingredients"],12),trunc(r["our_labels_applied"],14),r["outreach_priority"]] for r in pp],
 [0.3*inch,1.05*inch,0.75*inch,1.45*inch,0.85*inch,0.7*inch,0.75*inch,0.75*inch,0.55*inch],fs=6.6), Spacer(1,6),
 P("<b>Outreach priority and reasons</b> (first three):")]
st += [tbl(["Provider","Why this priority"],
 [[trunc(r["company"],26),trunc(r["outreach_reason"],104)] for r in pp[:3]],[1.4*inch,5.2*inch]), Spacer(1,6),
 callout("Two sourcing models compared — not ranked on price alone",
 "(A) <b>same-company supply + packing</b> (turnkey: e.g. Pearl, JAPC, Spices Inc, Specialty Food Co-Packers, Organic Spices Inc), versus "
 "(B) <b>bulk supply + a separate qualified food packer</b> (e.g. Pearl bulk + Spices Inc). Model B needs two contracts and separate import responsibility; "
 "Model A is simpler but concentrates on one firm. <b>No route is declared cheapest or fastest</b> — that requires comparable quotes.",tone="note"),
 Spacer(1,4),
 P("<b>Label application</b> is compared explicitly: (i) <b>provider-applied</b> label artwork (we supply artwork; they print/apply), versus "
   "(ii) <b>receiving sealed units</b> and applying our label ourselves. Column “Our labels?” shows each provider's stated capability, all QUOTE REQUIRED.",st_small),
 P("<b>Label approval is owner-reported and its scope is NOT audited by this research.</b> Nothing here implies the label has been reviewed or cleared.",st_small)]

# 18 DATED ACTION PLAN
st += [PageBreak(), P("18. Dated action plan (Oct 5 – Dec 1)", st_h1), rule(),
 P("Three parallel workstreams. Every milestone carries a date, owner role, dependencies, required evidence, status, delay consequence and backup. "
   "Full detail: launch_schedule.csv (23 milestones).")]
ls=rows_of("launch_schedule.csv")
ws={"Owner/scope":"Owner &amp; scope","Supplier/samples":"1 · Supplier selection &amp; samples",
    "Compliance/label":"2 · Packaging, labelling &amp; compliance","Amazon/launch":"3 · Amazon listing, shipment &amp; ads"}
st += [tbl(["Date","Workstream","Milestone","Role","Status","If delayed"],
 [[r["est_completion_date"],trunc(ws.get(r["workstream"],r["workstream"]),26),trunc(r["milestone"],52),
   r["responsible_role"],r["status"].replace("planning allowance","planning"),trunc(r["consequence_of_delay"],34)] for r in ls],
 [0.72*inch,1.5*inch,2.35*inch,0.7*inch,0.6*inch,1.0*inch],fs=6.5), Spacer(1,6),
 callout("Five distinct states — never conflate them",
 "1. <b>Production complete</b> (units built)  →  2. <b>Shipment dispatched</b> (leaves origin)  →  3. <b>Delivered to Amazon</b> (arrives at FC)  →  "
 "4. <b>Received / available inventory</b> (check-in complete)  →  5. <b>Buyable listing</b> (live ASIN with active offer). "
 "Each is later than the one before; delivery is NOT buyable inventory.",tone="warn")]

# 19 DECISION GATES
st += [PageBreak(), P("19. Decision gates", st_h1), rule(),
 P("Use these to reduce assortment, change providers, or revise fulfilment. <b>Documentation and safety are not compromised to preserve a date.</b>")]
dg=rows_of("decision_gates.csv")
st += [tbl(["Gate","Trigger","Decision","Options"],
 [[r["gate_id"],trunc(r["trigger"],66),r["decision_required"],trunc(r["options"],72)] for r in dg],
 [0.45*inch,2.1*inch,1.25*inch,2.8*inch],fs=6.8), Spacer(1,6),
 P("<b>Rule:</b> if a gate fires and the target is no longer supported, prefer reducing the assortment or moving to 2026-12-01 over shipping with incomplete documentation or an unverified organic claim.",st_small),
 P("<b>Budget:</b> product budget is $1,500–$2,500. Advertising, testing, freight and any certification are shown <b>separately</b> and are not part of that figure.",st_small)]

'''
marker="# APPENDICES"
if marker not in s: print("MISSING appendix marker")
s=s.replace(marker, NEW+marker)

io.open(p,"w",encoding="utf-8").write(s)
print("patched launch pdf script")
