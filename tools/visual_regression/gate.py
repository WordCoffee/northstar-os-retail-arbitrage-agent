"""Visual regression gate CLI.

    python -m tools.visual_regression.gate --self-test
    python -m tools.visual_regression.gate --base-url http://127.0.0.1:8101
    python -m tools.visual_regression.gate --base-url http://127.0.0.1:8101 \
        --update-baseline --scorecard-passed

Exit codes
----------
0   every compared view passed
1   at least one view regressed (or a capture was untrustworthy)
2   REFUSED — cannot run: unreachable app, non-loopback URL, malformed
    registry, browser missing, or ``--update-baseline`` without
    ``--scorecard-passed``
3   captured fine, but at least one (view, viewport) has no baseline yet

A refusal never writes a verdict. Nothing is ever reported as a pass because the
page was blank, absent, or never rendered.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from . import SCHEMA_VERSION
from .baseline import (
    BASELINES_ROOT,
    BaselineRefused,
    baseline_path,
    update_baselines,
    utc_now,
)
from .capture import CaptureError, capture_views, ensure_loopback, probe_base_url
from .diff import DEFAULT_CONFIG, DiffConfig, compare_files
from .views import (
    REGISTRY_PATH,
    Registry,
    RegistryError,
    filter_views,
    load_registry,
    validate,
)

EXIT_PASS = 0
EXIT_REGRESSION = 1
EXIT_REFUSED = 2
EXIT_NO_BASELINE = 3

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ARTIFACTS_ROOT = Path(__file__).resolve().parent / "artifacts"


@dataclass
class ViewResult:
    view: str
    viewport: str
    verdict: str  # pass | fail | no_baseline | error
    reason: str
    image: str = ""
    baseline: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "view": self.view,
            "viewport": self.viewport,
            "verdict": self.verdict,
            "reason": self.reason,
            "artifact": self.image,
            "baseline": self.baseline,
            "metrics": self.metrics,
            "detail": self.detail,
        }


def git_commit(root: str | Path | None = None) -> str:
    cwd = str(root or Path(__file__).resolve().parents[2])
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# --- self test ------------------------------------------------------------

def run_self_test(
    fixtures_dir: str | Path = FIXTURES_DIR,
    config: DiffConfig = DEFAULT_CONFIG,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Classify every synthetic fixture pair. No server, no browser."""
    root = Path(fixtures_dir)
    manifest_path = root / "expected.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing fixture manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: List[Dict[str, Any]] = []
    ok = True
    for item in manifest["fixtures"]:
        result = compare_files(root / item["baseline"], root / item["candidate"], config)
        matched = result.verdict == item["expected"]
        ok = ok and matched
        rows.append(
            {
                "pair": item["pair"],
                "case": item["case"],
                "expected": item["expected"],
                "actual": result.verdict,
                "matched": matched,
                "reason": result.reason,
                "metrics": result.as_dict(),
                "why": item["why"],
            }
        )
    return ok, rows


def print_self_test(ok: bool, rows: Sequence[Mapping[str, Any]]) -> None:
    width = max(len(r["pair"]) for r in rows) if rows else 4
    print(f"{'pair'.ljust(width)}  expected  actual  ratio      cluster  verdict")
    for row in rows:
        metrics = row["metrics"]
        mark = "OK" if row["matched"] else "MISMATCH"
        print(
            f"{row['pair'].ljust(width)}  {row['expected']:<8}  {row['actual']:<6}  "
            f"{metrics['pixel_diff_ratio']:<9.4f}  {metrics['cluster_pixels']:<7}  {mark}"
        )
    print(
        f"{sum(1 for r in rows if r['matched'])}/{len(rows)} fixture pairs classified as expected"
    )


# --- evaluation -----------------------------------------------------------

def evaluate_artifacts(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    baselines_root: str | Path = BASELINES_ROOT,
    config: DiffConfig = DEFAULT_CONFIG,
) -> List[ViewResult]:
    """Compare captured artifacts against baselines. Pure file work."""
    results: List[ViewResult] = []
    for artifact in artifacts:
        view_id = str(artifact["view"])
        viewport_id = str(artifact["viewport"])
        image = Path(str(artifact["path"]))
        base = baseline_path(view_id, viewport_id, baselines_root)
        if not image.is_file():
            results.append(
                ViewResult(view_id, viewport_id, "error", "artifact_missing", str(image))
            )
            continue
        if not base.is_file():
            results.append(
                ViewResult(
                    view_id,
                    viewport_id,
                    "no_baseline",
                    "no_baseline",
                    image=str(image),
                    baseline=str(base),
                )
            )
            continue
        diff = compare_files(base, image, config)
        results.append(
            ViewResult(
                view_id,
                viewport_id,
                diff.verdict,
                diff.reason,
                image=str(image),
                baseline=str(base),
                metrics=diff.as_dict(),
            )
        )
    return results


def summarise(results: Sequence[ViewResult]) -> Dict[str, Any]:
    counts = {"pass": 0, "fail": 0, "no_baseline": 0, "error": 0}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    if counts["fail"] or counts["error"]:
        verdict = "fail"
    elif counts["no_baseline"]:
        verdict = "no_baseline"
    else:
        verdict = "pass"
    return {"total": len(results), **counts, "verdict": verdict}


def build_report(
    *,
    results: Sequence[ViewResult],
    base_url: str,
    commit: str,
    registry_path: str | Path,
    artifacts_dir: str | Path,
    config: DiffConfig,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    report = {
        "schema": SCHEMA_VERSION,
        "generated": utc_now(),
        "base_url": base_url,
        "commit": commit,
        "registry": str(registry_path),
        "artifacts_dir": str(artifacts_dir),
        "diff_config": dict(config.__dict__),
        "still": {"param": "still=1", "seed": "per-view from ty/visual_views.json",
                  "init_script": "tools/visual_regression/freeze.py"},
        "results": [r.as_dict() for r in results],
        "summary": summarise(results),
    }
    if extra:
        report.update(dict(extra))
    return report


def write_report(report: Mapping[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


def print_results(results: Sequence[ViewResult]) -> None:
    if not results:
        print("no results")
        return
    width = max(len(f"{r.view}/{r.viewport}") for r in results)
    print(f"{'view/viewport'.ljust(width)}  verdict      ratio      cluster  reason")
    for result in results:
        ratio = result.metrics.get("pixel_diff_ratio")
        cluster = result.metrics.get("cluster_pixels")
        ratio_text = f"{ratio:<9.4f}" if isinstance(ratio, (int, float)) else f"{'-':<9}"
        cluster_text = f"{cluster:<7}" if isinstance(cluster, int) else f"{'-':<7}"
        print(
            f"{f'{result.view}/{result.viewport}'.ljust(width)}  {result.verdict:<11}  "
            f"{ratio_text}  {cluster_text}  {result.reason}"
        )


# --- CLI ------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.visual_regression.gate",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", help="loopback app URL, e.g. http://127.0.0.1:8101")
    parser.add_argument("--views", help="comma-separated view ids (default: all)")
    parser.add_argument("--viewports", help="comma-separated viewport ids (default: from registry)")
    parser.add_argument("--out", help="artifact directory (default: artifacts/<utc stamp>)")
    parser.add_argument("--report", help="report json path (default: <out>/report.json)")
    parser.add_argument("--self-test", action="store_true", help="classify fixtures only; no server")
    parser.add_argument("--update-baseline", action="store_true", help="promote artifacts to baselines")
    parser.add_argument(
        "--scorecard-passed",
        action="store_true",
        help="required with --update-baseline: the scorecard for this build passed",
    )
    parser.add_argument("--scorecard-file", help="optional scorecard json recorded in the changelog")
    parser.add_argument("--baselines", default=str(BASELINES_ROOT), help="baselines root (tests use a tmp dir)")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--max-pixel-ratio", type=float, default=DEFAULT_CONFIG.max_pixel_ratio)
    parser.add_argument("--min-region-px", type=int, default=DEFAULT_CONFIG.min_region_px)
    parser.add_argument("--tolerance", type=int, default=DEFAULT_CONFIG.tolerance)
    return parser


def _config(args: argparse.Namespace) -> DiffConfig:
    return DiffConfig(
        max_pixel_ratio=args.max_pixel_ratio,
        min_region_px=args.min_region_px,
        tolerance=args.tolerance,
    )


def run(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    config = _config(args)

    if args.self_test:
        ok, rows = run_self_test(config=config)
        print_self_test(ok, rows)
        return EXIT_PASS if ok else EXIT_REGRESSION

    if not args.base_url:
        print("REFUSED: --base-url is required (the gate never starts a server)", file=sys.stderr)
        return EXIT_REFUSED

    try:
        ensure_loopback(args.base_url)
    except CaptureError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    reachable, why = probe_base_url(args.base_url)
    if not reachable:
        print(
            f"REFUSED: app not reachable at {args.base_url} ({why}). "
            "No capture taken; a blank page is never a pass.",
            file=sys.stderr,
        )
        return EXIT_REFUSED

    try:
        registry = load_registry()
        problems = validate(registry)
        if problems:
            print("REFUSED: registry is not coherent:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return EXIT_REFUSED
        selected = filter_views(
            registry,
            [v.strip() for v in args.views.split(",")] if args.views else None,
            [v.strip() for v in args.viewports.split(",")] if args.viewports else None,
        )
    except RegistryError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    out_dir = Path(args.out) if args.out else ARTIFACTS_ROOT / timestamp_slug()
    report_path = Path(args.report) if args.report else out_dir / "report.json"
    commit = git_commit()

    try:
        records = capture_views(
            selected,
            base_url=args.base_url,
            out_dir=out_dir,
            timeout_ms=args.timeout_ms,
            registry=registry,
        )
    except CaptureError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        failed_report = build_report(
            results=[],
            base_url=args.base_url,
            commit=commit,
            registry_path=REGISTRY_PATH,
            artifacts_dir=out_dir,
            config=config,
            extra={"refused": str(exc), "summary": {"total": 0, "verdict": "refused"}},
        )
        write_report(failed_report, report_path)
        return EXIT_REFUSED

    artifacts = [record.as_dict() for record in records]
    results = evaluate_artifacts(artifacts, baselines_root=args.baselines, config=config)
    print_results(results)
    summary = summarise(results)
    print(
        f"\n{summary['pass']} passed, {summary['fail']} failed, "
        f"{summary['no_baseline']} missing baseline, {summary['error']} errors "
        f"-> {summary['verdict'].upper()}"
    )

    report = build_report(
        results=results,
        base_url=args.base_url,
        commit=commit,
        registry_path=REGISTRY_PATH,
        artifacts_dir=out_dir,
        config=config,
        extra={"captures": artifacts},
    )
    write_report(report, report_path)
    print(f"report: {report_path}")

    if args.update_baseline:
        scorecard = None
        if args.scorecard_file:
            scorecard = json.loads(Path(args.scorecard_file).read_text(encoding="utf-8"))
        try:
            entries = update_baselines(
                artifacts,
                scorecard_passed=args.scorecard_passed,
                scorecard=scorecard,
                commit=commit,
                root=args.baselines,
                prior_verdicts={(r.view, r.viewport): r.verdict for r in results},
            )
        except BaselineRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return EXIT_REFUSED
        print(f"baseline updated: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")
        for entry in entries:
            previous = entry["previous_baseline_sha256"] or "none"
            print(f"  {entry['view']}/{entry['viewport']}  prior={entry['prior_verdict']}  was={previous[:12]}")
        return EXIT_PASS

    if summary["verdict"] == "fail":
        return EXIT_REGRESSION
    if summary["verdict"] == "no_baseline":
        print(
            "no baseline yet for some views: re-run with --update-baseline --scorecard-passed "
            "once the scorecard passes",
            file=sys.stderr,
        )
        return EXIT_NO_BASELINE
    return EXIT_PASS


def main(argv: Optional[Sequence[str]] = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
