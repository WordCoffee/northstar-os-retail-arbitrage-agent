"""Offline unit tests for text_gate (no credits, no network)."""
import lions_mane_pull as L

base = {
    "title": "Organic Lion's Mane Mushroom Powder, 100% Fruiting Body, 8 oz",
    "feature_bullets": ["100% fruiting body lion's mane powder, USDA organic"],
    "specifications": [{"name": "Item Weight", "value": "8 ounces"}],
    "ingredients": ["Organic lion's mane mushroom"],
    "weight": "8 oz", "dimensions": "",
}

why, rev, size = L.text_gate(base)
print("case1 extract-with-exception: why=", why, "review=", rev, "size=", size)
assert size == 8.0 and not why, case1_failed

rec2 = dict(base)
rec2["title"] = "Organic Lion's Mane 8:1 Extract Powder 8 oz"
rec2["feature_bullets"] = []
why2, rev2, _ = L.text_gate(rec2)
print("case2 extract-no-exception: why=", why2, "review=", rev2)
assert not why2 and any("extract" in r for r in rev2)

rec3 = dict(base)
rec3["title"] = "Organic Lion's Mane Mushroom Powder 16 oz - Certified Organic, Non-GMO"
why3, rev3, size3 = L.text_gate(rec3)
print("case3 false-positive check (surface/certified must NOT trip): why=", why3, "review=", rev3, "size=", size3)
assert not why3 and size3 == 16.0

for t, expect in [("Organic Lion's Mane Powder 4 oz", 4.0), ("Organic Lion's Mane Powder 32 oz", 32.0),
                  ("1 lb Organic Lions Mane Powder", 16.0), ("Organic Lions Mane Powder 227 g", 8.007)]:
    r = dict(base); r["title"] = t; r["weight"] = ""
    w, rr, s = L.text_gate(r)
    print(f"case4 {t!r}: size={s} why={w}")
    assert s == expect and not w, (t, s, w)

# blend must hard-fail
r5 = dict(base); r5["title"] = "Organic Lion's Mane Reishi Mushroom Blend Powder 8 oz"
w5, _, _ = L.text_gate(r5)
print("case5 blend:", w5)
assert any("reishi" in x for x in w5)

# fl oz must hard-fail
r6 = dict(base); r6["title"] = "Organic Lion's Mane Liquid Drops 4 fl oz"
w6, _, _ = L.text_gate(r6)
print("case6 fluid:", w6)
assert any("fluid" in x for x in w6)

# multi-pack flag
r7 = dict(base); r7["title"] = "Organic Lion's Mane Powder 8 oz (Pack of 2)"
_, rr7, _ = L.text_gate(r7)
print("case7 multipack:", rr7)
assert any("multi-pack" in x for x in rr7)

# extra 8->10 sanity: no extraction from body text needed
print("case8 monthly_sales parse:", L.monthly_sales("2K+ bought in past month"), L.monthly_sales("500+ bought in past week"), L.monthly_sales("90 bought in past day"))
assert L.monthly_sales("2K+ bought in past month") == 2000
assert L.monthly_sales("500+ bought in past week") == 2165

# BSR estimator calibration: BSR 1000 ~ 2500/mo, 10000 ~ 500/mo, 100000 ~ 100/mo
for bsr, expect in [(1000, 2512), (10000, 501), (100000, 100), (32, 27951)]:
    est, rank, cat, note = L.bsr_monthly_sales([{"rank": bsr, "category": "Health & Household"}])
    print(f"case9 BSR {bsr} -> est {est}/mo ({cat})")
    assert abs(est - expect) / expect < 0.05, (bsr, est, expect)
est, _, _, _ = L.bsr_monthly_sales(None)
assert est is None
print("ALL EXTRA TESTS PASS")
