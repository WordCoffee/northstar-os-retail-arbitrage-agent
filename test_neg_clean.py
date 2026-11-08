"""Offline test of the negation cleaner on real-world phrases."""
import lions_mane_sb as L

cases = [
    # (input, must_keep, must_not_remain)
    ("made in the US with pure non-GMO fruiting body & mycelium in a cGMP facility", "mycelium", None),
    ("contains no fillers, grains, or mycelium, ensuring the purest", None, "mycelium"),
    ("No Mycelium, No Fillers", None, "mycelium"),
    ("this is not a blend and never an extract", None, "blend"),
    ("mycelium-free and extract-free", None, "mycelium"),
    ("our powder contains no fillers, grains, or mycelium", None, "mycelium"),
    ("100% fruiting body, no grain, no starch, just real mushrooms", None, "grain"),
    ("fruiting body and mycelial biomass cultured on organic sorghum", "mycelial", None),
    ("no other mushrooms, no fillers or additives", None, None),
]
ok = True
for text, keep, drop in cases:
    c = L.clean(text)
    status = "OK "
    if keep and keep not in c:
        status = "FAIL(keep)"; ok = False
    if drop and drop in c:
        status = "FAIL(drop)"; ok = False
    print(f"{status} | in={text[:60]!r} -> {c[:90]!r}")
print("ALL NEGATION TESTS PASS" if ok else "SOME TESTS FAILED")
