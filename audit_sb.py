#!/usr/bin/env python3
"""Independent audit pass (Step 5) - simple per-question protocol.
- Sample all PASS rows (target >=20; we audit every PASS row) + low-confidence rows.
- Fresh re-check on downloaded images with single-question prompts (qwen2.5vl:7b on :11435).
- Re-check 10 random REJECTED rows against their recorded reasons.
Writes out_sb/audit_results.json and out_sb/audit_report.md.
"""
import base64, csv, io, json, random, re, sys
from pathlib import Path
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out_sb"
PORT = 11435
MODEL = "qwen2.5vl:7b"

def to_b64(path):
    img = Image.open(path).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def ask(b64, question, npred=100):
    r = requests.post(f"http://localhost:{PORT}/api/chat",
                      json={"model": MODEL, "stream": False, "options": {"temperature": 0, "num_predict": npred},
                            "messages": [{"role": "user", "content": question, "images": [b64]}]},
                      timeout=600)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()

def oz_from_text(s):
    if not s:
        return None
    vals = []
    for n, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|oz|ounces?|lbs?|pounds?|kg|kilograms?|grams?|g)\b", s, re.I):
        u = unit.lower().replace(".", "")
        if u.startswith("fl"):
            continue
        f = 1 if u in ("oz", "ounce", "ounces") else 16 if u in ("lb", "lbs", "pound", "pounds") else 35.274 if u in ("kg", "kilogram", "kilograms") else 0.035274
        vals.append(round(float(n) * f, 2))
    return max(vals) if vals else None

def read_csv(name):
    p = OUT / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def main():
    random.seed(42)
    passed = read_csv("pass.csv")
    rejected = read_csv("rejected.csv")
    if not passed:
        print("no PASS rows to audit"); return
    low_conf = [r for r in passed if float(r.get("vision_confidence") or 0) < 0.85]
    sample = list({r["asin"]: r for r in (random.sample(passed, min(20, len(passed))) + low_conf)}.values())
    print(f"auditing {len(sample)} PASS rows (of {len(passed)}; {len(low_conf)} low-confidence)")

    results = {"pass_audit": [], "rejected_audit": []}
    for r in sample:
        asin = r["asin"]
        d = OUT / "images" / asin
        imgs = sorted(d.glob("*.jpg"))[:3] if d.exists() else []
        if not imgs:
            results["pass_audit"].append({"asin": asin, "result": "NO_IMAGES"})
            continue
        flags, notes = [], {}
        answers = []
        for fp in imgs:
            try:
                b = to_b64(fp)
                form = ask(b, "Is this product a powder, capsules, tablets, or a liquid? Answer with one word.", 20)
                nw_txt = ask(b, "What is the net weight printed on this product's label? Answer with only that text.", 40)
                org = ask(b, "Does the label say USDA Organic or Certified Organic? Answer yes or no.", 10)
                lm = ask(b, "Does the label say Lion's Mane? Answer yes or no.", 10)
                answers.append({"file": fp.name, "form": form, "net_weight": nw_txt, "organic": org, "lions_mane": lm})
            except Exception as e:
                answers.append({"file": fp.name, "error": str(e)[:80]})
        forms = [a.get("form", "").lower() for a in answers if "form" in a]
        powder_found = any("powder" in f for f in forms)
        capsule_found = any(x in f for f in forms for x in ("capsule", "tablet", "liquid", "gummy"))
        nws = [oz_from_text(a.get("net_weight")) for a in answers if "net_weight" in a]
        nws = [x for x in nws if x]
        size = float(r["size_oz"]) if r.get("size_oz") else None
        best_nw = max(nws) if nws else None
        org_yes = any("yes" in str(a.get("organic", "")).lower() for a in answers)
        lm_yes = any("yes" in str(a.get("lions_mane", "")).lower() for a in answers)
        if capsule_found and not powder_found:
            flags.append("capsules/liquid indicated")
        if not powder_found:
            flags.append("powder not confirmed")
        if best_nw and size and abs(best_nw - size) / size > 0.12:
            flags.append(f"weight mismatch: {best_nw} vs {size}")
        if not best_nw:
            flags.append("net weight unreadable")
        if not lm_yes:
            flags.append("lion's mane not confirmed")
        if not org_yes:
            flags.append("organic not confirmed")
        result = "CONFIRMED" if not flags else "FLAGGED"
        results["pass_audit"].append({"asin": asin, "result": result, "flags": flags,
                                      "answers": answers})
        print(f"  {asin}: {result}" + (f" | {'; '.join(flags)}" if flags else ""))

    # rejected re-check (10 random from text/visual stages, fresh text gate)
    import importlib
    L = importlib.import_module("lions_mane_sb")
    rej_rows = [r for r in rejected if r.get("stage") in ("text", "visual")]
    rej_sample = random.sample(rej_rows, min(10, len(rej_rows))) if rej_rows else []
    details = json.loads((OUT / "details.json").read_text(encoding="utf-8")) if (OUT / "details.json").exists() else {}
    for r in rej_sample:
        asin = r["asin"]
        p = details.get(asin)
        if not p:
            results["rejected_audit"].append({"asin": asin, "recorded": r.get("reasons"), "recheck": "NO_DETAIL_DATA"})
            continue
        p = dict(p); p["asin"] = asin
        why, rev, size = L.text_gate(p)
        ok = "RECONFIRMED" if why else "CHECK"
        results["rejected_audit"].append({"asin": asin, "recorded": r.get("reasons"),
                                          "recheck_reasons": why, "result": ok})
        print(f"  REJ {asin}: {ok} | recheck={why[:2]}")

    (OUT / "audit_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    conf = sum(1 for x in results["pass_audit"] if x.get("result") == "CONFIRMED")
    total = len(results["pass_audit"])
    flagged = [x for x in results["pass_audit"] if x.get("result") == "FLAGGED"]
    lines = ["# Independent audit report (fresh prompts, single-question protocol)", "",
             f"- PASS rows audited: {total}; confirmed: {conf}; flagged: {len(flagged)}",
             f"- REJECTED rows re-checked: {len(results['rejected_audit'])}", ""]
    for x in results["pass_audit"]:
        lines.append(f"- {x['asin']}: {x.get('result')}" + (f" | {'; '.join(x.get('flags', []))}" if x.get("flags") else ""))
    lines.append("")
    for x in results["rejected_audit"]:
        lines.append(f"- REJ {x['asin']}: {x.get('result')} | recorded: {str(x.get('recorded'))[:100]}")
    (OUT / "audit_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"audit complete: {conf}/{total} confirmed")

if __name__ == "__main__":
    main()
