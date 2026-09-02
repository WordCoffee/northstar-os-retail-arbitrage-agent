"""Layer 11 - Benchmark drift comparison (reuses benchmark_validation engine).

Diffs live intel_schema snapshots against the benchmark reference. For ASINs
that do NOT overlap the benchmark, benchmark fields are reported as null (no
fabrication) and disposition is 'no_benchmark_reference'.
"""

import benchmark_validation as bv


def compare_snapshot(asin, snapshot, benchmark_canonical):
    bench = benchmark_canonical.get(asin) if isinstance(benchmark_canonical, dict) else None
    if bench is None:
        return {
            "asin": asin,
            "benchmark_overlap": False,
            "benchmark_fields": None,
            "disposition": "no_benchmark_reference",
            "note": "non-overlapping discovered ASIN; benchmark fields null, not fabricated",
        }
    report = bv.compare_benchmark_record(bench, snapshot)
    report["benchmark_overlap"] = True
    return report


def compare_batch(snapshots, benchmark_canonical):
    return {asin: compare_snapshot(asin, snap, benchmark_canonical)
            for asin, snap in snapshots.items()}
