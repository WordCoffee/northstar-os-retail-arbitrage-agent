"""dedupe Linux probe (Phase-3 open item 1) - SYNTHETIC data, dedicated venv.

dedupe 3.0.3 needs its own environment on Linux:
    python -m venv /dv
    /dv/bin/pip install 'dedupe==3.0.3' 'BTrees<6' 'numpy<2'
numpy<2 conflicts with splink 5's pyarrow (needs numpy>=2), so this probe is
kept separate from product_matching_spike.py and CI runs it in its own venv.

No real data, no network calls at runtime, no writes: a tiny synthetic
train() smoke test answering "is dedupe runnable on Linux at all?".
"""
from __future__ import annotations

import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    import dedupe
    from dedupe import Dedupe

    rng = random.Random(20261014)
    recs = {
        f"a{i}": {
            "title": f"FAKE-TEST Widget {i}",
            "brand": f"FAKE-TEST-{'Zibble' if i % 2 else 'Quorn'}",
            "upc": f"FAKEGTIN{i:06d}000",
        }
        for i in range(50)
    }
    fields = [
        dedupe.variables.String("title"),
        dedupe.variables.String("brand"),
        dedupe.variables.Exact("upc"),
    ]
    dd = Dedupe(fields)
    dd.prepare_training(recs, sample_size=500)
    ids = list(recs)
    match, distinct = [], []
    for i in range(20):
        a, b = rng.sample(ids, 2)
        (match if i % 2 == 0 else distinct).append((recs[a], recs[b]))
    dd.mark_pairs({"distinct": distinct, "match": match})
    dd.train()
    print("dedupe train OK (Linux dedicated env)")
    clusters = dd.partition(recs)
    print("dedupe partition OK - clusters:", len(clusters))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
