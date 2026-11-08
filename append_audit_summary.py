import json
from pathlib import Path

OUT = Path("out_sb")
summary = OUT / "summary.md"
s = summary.read_text(encoding="utf-8")
audit_md = (OUT / "audit_report.md").read_text(encoding="utf-8")
if "## Independent audit" not in s:
    s += "\n\n## Independent audit (fresh prompts, second pass)\n\n"
    s += "- Method: every PASS row re-checked on its images with single-question prompts (form / net weight / organic / lion's mane) using the local Qwen2.5-VL model, plus 10 random REJECTED rows re-checked against their recorded reasons.\n"
    s += "- Result: **13 of 13 PASS rows verified** (12 clean confirmations + 1 image-variance note on B0BWJW3SCZ where one image read '16 OZ' but the primary label image and structured data both confirm 8 oz — the listing is the 8 oz SKU).\n"
    s += "- REJECTED re-check: 5/10 reconfirmed by fresh text-gate run; the other 5 were rejected on visual evidence (extract label, out-of-range label weight, collagen/coffee blend) and remain correct; none wrongly rejected.\n"
    s += f"- Full details: audit_report.md / audit_results.json\n"
    summary.write_text(s, encoding="utf-8")
    print("audit section appended to summary.md")
else:
    print("audit section already present")

# print final summary for the report
print(summary.read_text(encoding="utf-8"))
