# Splice appendix + correct closing into build_pdf.py between known markers.
import io, os
p = os.path.join("docs","mogra-organics-research-2026-10-02","_scripts","build_pdf.py")
src = io.open(p, encoding="utf-8").read()

START = "story += [Spacer(1, 14), rule(PINE,1.2,4,4),"
END = "doc = Doc(PDF, pagesize=letter)"
i = src.index(START); j = src.index(END)

APPENDIX = r'''# ============ APPENDICES (rendered from canonical CSVs) ============
def csv_rows(fn):
    with open(os.path.join(ROOT, fn), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def trunc(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n-1] + "…"

story += [PageBreak(), P("Appendix A — Full commercial supplier inventory", st_h1), rule(),
 P("All %d commercial suppliers. Resources and directories are excluded and listed separately in Appendix C." % C["suppliers"], st_cap)]
sup = csv_rows("supplier_master.csv")
rowsA = [[s["supplier_id"], s["legal_name"], s["hq_country"], s["supplier_type"], trunc(s["notes"], 150)] for s in sup]
story += [tbl(["ID","Legal name","Country","Type","Evidence summary"],
 rowsA, [1.05*inch,1.55*inch,0.7*inch,1.0*inch,2.3*inch])]

story += [PageBreak(), P("Appendix B — Full evidence register", st_h1), rule(),
 P("All %d evidence entries with claim status and observation date." % C["evidence"], st_cap)]
ev = csv_rows("evidence_register.csv")
rowsB = [[e["evidence_id"], trunc(e["claim"], 170), e["claim_status"], e["observation_date"]] for e in ev]
story += [tbl(["ID","Claim","Status","Observed"],
 rowsB, [0.6*inch,4.0*inch,1.0*inch,1.0*inch])]

story += [PageBreak(), P("Appendix C — Full risk register", st_h1), rule(),
 P("All %d risks." % C["risk"], st_cap)]
rk = csv_rows("risk_register.csv")
rowsC = [[r["risk_id"], r["category"], trunc(r["description"], 200), r["likelihood"], r["impact"]] for r in rk]
story += [tbl(["ID","Category","Description","Likelihood","Impact"],
 rowsC, [0.5*inch,0.85*inch,3.65*inch,0.8*inch,0.8*inch])]

story += [PageBreak(), P("Appendix D — Full decision register", st_h1), rule(),
 P("All %d owner decisions, with the stage by which each is required." % C["decision"], st_cap)]
dc = csv_rows("decision_register.csv")
rowsD = [[d["decision_id"], d["decision"], d["needed_by_stage"], d["owner_input_required"]] for d in dc]
story += [tbl(["ID","Decision","Needed by stage","Owner input"],
 rowsD, [0.5*inch,3.3*inch,1.4*inch,1.4*inch])]

story += [P("Appendix E — Product and route readiness", st_h2), rule()]
pr = csv_rows("product_route_readiness.csv")
rowsE = [[x["readiness_id"], x["product"], x["form"], x["route"], x["best_supported"], x["purchase_ready"]] for x in pr]
story += [tbl(["ID","Product","Form","Route","Best-supported","Purchase-ready"],
 rowsE, [0.55*inch,1.5*inch,1.2*inch,0.6*inch,1.55*inch,1.2*inch])]

story += [PageBreak(), P("Appendix F — Priority verification queue status", st_h1), rule(),
 P("All %d checks, in commercial-priority order. Every entry is open." % C["checks"], st_cap)]
pq = csv_rows("priority_verification_queue.csv")
rowsF = [[x["priority"], x["legal_name"], x["country"], trunc(x["evidence_needed"], 150), x["status"]] for x in pq]
story += [tbl(["#","Legal name","Country","Evidence needed","Status"],
 rowsF, [0.35*inch,1.75*inch,0.85*inch,2.75*inch,0.9*inch])]

story += [PageBreak(), P("Appendix G — Resources and directories (not commercial suppliers)", st_h1), rule()]
rs = csv_rows("resources_and_directories.csv")
rowsG = [[x["name"], x["resource_type"], trunc(x["what_it_provides"], 170)] for x in rs]
story += [tbl(["Name","Type","Provides"],
 rowsG, [1.7*inch,1.5*inch,3.4*inch]), Spacer(1, 5),
 P("These are discovery and verification resources. They are excluded from every supplier count in this document.")]

story += [Spacer(1, 14), rule(PINE,1.2,4,4),
 Paragraph("WORKING BLUEPRINT — NOT PURCHASE OR LAUNCH AUTHORIZATION", S("end", fontName=HEAD_B, fontSize=10, leading=14, textColor=CLAY, alignment=TA_CENTER)),
 Paragraph("Prepared for owner review · T2Holdings LLC (entity spelling unverified) · "+TODAY, S("end2", fontName=BODY_I, fontSize=8.5, leading=12, textColor=MUTED, alignment=TA_CENTER))]

'''

src = src[:i] + APPENDIX + src[j:]
io.open(p, "w", encoding="utf-8").write(src)
print("patched build_pdf.py")
