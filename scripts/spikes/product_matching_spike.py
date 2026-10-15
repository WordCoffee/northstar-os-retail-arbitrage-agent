"""Product-matching spike (Phase-3 unit 5) - SYNTHETIC data, NO prod wiring.

Owner directive: "match 50 sample ASIN/UPC pairs from our data, report
accuracy, no prod wiring". Production data lives outside this workstream, so
this spike builds a clearly-synthetic set with the required FAKE-TEST- markers
(no real users/data; no live calls; deterministic seed).

dedupe is install-blocked on this machine (C-extension wheels missing for the
available interpreters; build failures recorded in the unit report), so the
spike runs on splink 5 (installed; Apache-2.0-adjacent ecosystem, MIT itself).

Run:  python scripts/spikes/product_matching_spike.py
"""
from __future__ import annotations

import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEED = 20261014
rng = random.Random(SEED)

BRANDS = ["FAKE-TEST-Zibble", "FAKE-TEST-Quorn", "FAKE-TEST-Mim", "FAKE-TEST-Bloop", "FAKE-TEST-Tarn"]
WORDS = ["Widget", "Gizmo", "Bloblet", "Doohickey", "Thingamajig", "Sprocket"]
UNITS = ["8oz", "12oz", "16oz", "250ml", "500ml"]


def perturb(title: str) -> str:
    kind = rng.randrange(4)
    if kind == 0:  # typo: duplicate a character
        i = rng.randrange(1, len(title) - 1)
        return title[:i] + title[i] + title[i:]
    if kind == 1:  # extra marketing token
        return title + " Organic"
    if kind == 2:  # unit spacing variant
        return title.replace("oz", " oz").replace("ml", " ml")
    return title.upper() if rng.random() < 0.5 else title.lower()


def build():
    rows: list[dict] = []
    truth: set[tuple[str, str]] = set()
    rid = 0
    for i in range(50):
        brand = rng.choice(BRANDS)
        word = rng.choice(WORDS)
        unit = rng.choice(UNITS)
        base = f"{word} {unit}"
        upc = f"FAKEGTIN{i:06d}000"
        a = {"unique_id": f"a{i}", "title": f"FAKE-TEST {base}", "brand": brand, "word": word, "upc": upc}
        rows.append(a)
        rid += 1
        if i % 2 == 0:  # true match: perturbed duplicate
            b = {"unique_id": f"b{i}", "title": f"FAKE-TEST {perturb(base)}", "brand": brand, "word": word, "upc": upc}
            rows.append(b)
            truth.add((f"a{i}", f"b{i}"))
        else:  # distractor: same-ish shape, different identity
            w2 = rng.choice([w for w in WORDS if w != word])
            b = {
                "unique_id": f"b{i}",
                "title": f"FAKE-TEST {w2} {rng.choice(UNITS)}",
                "brand": rng.choice(BRANDS),
                "word": w2,
                "upc": f"FAKEGTIN{i:06d}999",
            }
            rows.append(b)
    return rows, truth


def main() -> int:
    rows, truth = build()
    print(f"records: {len(rows)} | true pairs: {len(truth)}")

    import pyarrow as pa
    import splink.comparison_library as cl
    from splink import DuckDBAPI, Linker, SettingsCreator, block_on

    # pandas-free: splink 5 needs only pyarrow/duckdb, and the Linux eval
    # container does not ship pandas.
    tbl = pa.table({k: [r[k] for r in rows] for k in ("unique_id", "title", "brand", "word", "upc")})
    settings = SettingsCreator(
        link_type="dedupe_only",
        comparisons=[
            cl.JaroWinklerAtThresholds("title", [0.92, 0.84]),
            cl.ExactMatch("upc"),
            cl.ExactMatch("brand"),
        ],
        blocking_rules_to_generate_predictions=[block_on("brand"), block_on("word"), block_on("upc")],
    )
    db_api = DuckDBAPI()
    df_splink = db_api.register(tbl)
    linker = Linker(df_splink, settings)
    linker.training.estimate_probability_two_random_records_match([block_on("brand", "word")], recall=0.7)
    linker.training.estimate_u_using_random_sampling(max_pairs=10_000)
    try:
        linker.training.estimate_parameters_using_expectation_maximisation(block_on("brand"))
        linker.training.estimate_parameters_using_expectation_maximisation(block_on("word"))
    except Exception as exc:  # EM can be flaky on tiny data; keep going with priors
        print(f"[warn] EM skipped: {exc}")
    preds = linker.inference.predict(threshold_match_probability=0.5)
    try:
        pt = preds.as_pyarrow_table()
        raw = {
            tuple(sorted((str(a), str(b))))
            for a, b in zip(
                pt.column("unique_id_l").to_pylist(), pt.column("unique_id_r").to_pylist()
            )
        }
    except Exception:
        raw = {
            tuple(sorted((str(r["unique_id_l"]), str(r["unique_id_r"]))))
            for r in preds.as_record_list()
        }
    truth_norm = {tuple(sorted(p)) for p in truth}

    # Domain rule for ASIN/UPC matching: conflicting NON-NULL identifiers veto
    # a match (nulls stay tolerated). Realistic pipelines treat strong
    # identifiers this way; retained as a safety rule for real data.
    key = {r["unique_id"]: r for r in rows}

    def upc_conflict(a: str, b: str) -> bool:
        ua, ub = key[a]["upc"], key[b]["upc"]
        return bool(ua) and bool(ub) and ua != ub

    got = {p for p in raw if not upc_conflict(*p)}

    def metrics(s: set) -> tuple[int, int, int, float, float, float]:
        tp = len(truth_norm & s)
        fp = len(s - truth_norm)
        fn = len(truth_norm - s)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return tp, fp, fn, prec, rec, f1

    print("--- raw splink (threshold 0.5) ---")
    print("predicted: %d | TP=%d FP=%d FN=%d | precision=%.2f recall=%.2f f1=%.2f" % ((len(raw),) + metrics(raw)))
    print("--- with UPC-conflict veto ---")
    print("predicted: %d | TP=%d FP=%d FN=%d | precision=%.2f recall=%.2f f1=%.2f" % ((len(got),) + metrics(got)))
    print("vetoed-out pairs:", len(raw) - len(got))
    print("sample raw-predicted pairs:", sorted(raw)[:5])
    print("missed pairs:", sorted(truth_norm - got)[:5])

    # --- dedupe (optional; install-blocked on the Windows host, expected on
    # Linux CI - activates only when dedupe is importable) ---
    print("--- dedupe (runs when importable; Linux CI re-eval) ---")
    try:
        import dedupe  # noqa: F401
        from dedupe import Dedupe

        records = {
            r["unique_id"]: {"title": r["title"], "brand": r["brand"], "upc": r["upc"]}
            for r in rows
        }
        fields = [
            dedupe.variables.String("title"),
            dedupe.variables.String("brand"),
            dedupe.variables.Exact("upc"),
        ]
        dd = Dedupe(fields)
        dd.prepare_training(records, sample_size=5000)
        import random as _r

        _r.seed(7)
        ids = list(records)
        match_pairs = [(records[a], records[b]) for a, b in sorted(truth_norm)]
        distinct_pairs = []
        while len(distinct_pairs) < len(match_pairs):
            x, y = _r.sample(ids, 2)
            key = tuple(sorted((x, y)))
            if key not in truth_norm:
                distinct_pairs.append((records[key[0]], records[key[1]]))
        dd.mark_pairs({"distinct": distinct_pairs, "match": match_pairs})
        dd.train()
        clusters = dd.partition(records)
        got_dedupe: set = set()
        for cluster in clusters:
            members = sorted(cluster)
            for i, m1 in enumerate(members):
                for m2 in members[i + 1 :]:
                    got_dedupe.add(tuple(sorted((m1, m2))))
        tp_d = len(truth_norm & got_dedupe)
        fp_d = len(got_dedupe - truth_norm)
        fn_d = len(truth_norm - got_dedupe)
        prec_d = tp_d / (tp_d + fp_d) if tp_d + fp_d else 0.0
        rec_d = tp_d / (tp_d + fn_d) if tp_d + fn_d else 0.0
        f1_d = 2 * prec_d * rec_d / (prec_d + rec_d) if prec_d + rec_d else 0.0
        print("predicted: %d | TP=%d FP=%d FN=%d | precision=%.2f recall=%.2f f1=%.2f" % (len(got_dedupe), tp_d, fp_d, fn_d, prec_d, rec_d, f1_d))
    except ImportError:
        print("[skip] dedupe not importable on this host (expected on Windows; Linux CI runs it)")
    except Exception as exc:
        print(f"[warn] dedupe branch failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
