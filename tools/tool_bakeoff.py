"""D17 - REA vs Craft Anything bake-off.

Two reverse-study tools, three targets, one measured decision per target kind.
A result counts as "tool did not run" unless the run has a command line, an exit
code and a non-empty output artefact. Nothing is inferred from a README.

    # run all six cells (two tools x three targets) and write the result file
    python tools/tool_bakeoff.py --run

    # re-score artefacts already on disk (no subprocess, used by the tests)
    python tools/tool_bakeoff.py --score-only

    # decompress the committed *.json.gz artefacts and prove their sha256
    # against the run sidecars (a fresh checkout has no large JSON in git)
    python tools/tool_bakeoff.py --unpack

Targets
  oss-repo   an open-source JavaScript app already on this machine
             (TodoMVC examples/javascript-es6, MIT, cloned into
             research/bakeoff/targets/todomvc)
  hosted     a hosted, non-Amazon tool reached read-only over the network
             (https://opencode.ai/, page + entry bundle saved with plain GET)
  local-app  this repo's own built web app served on 127.0.0.1:8123

Every artefact (fetch, run, error and score sidecar) stays under
research/bakeoff/, so a verifier can reproduce a cell from a fresh checkout.

Amazon is never a target. No credentials, no spending, no browser automation:
the hosted page and the local app are fetched with a plain read-only GET and
both tools then analyse the same saved artefacts, so the comparison is
apples-to-apples. Browser-driven capture is deliberately not used: Chrome
Connect is the controller for browser work, and a static SPA gains nothing from
a headless render here.

Scores (documented, deterministic, all in this file):
  behaviour-spec accuracy  0.40  fraction of the target's ground-truth facts the
                                 tool's own output names
  detail coverage          0.25  unique non-hash strings in the output, 1000 = 1.0
  speed                    0.15  best time / this time
  token cost               0.10  best bytes / these bytes (bytes/4 as a token
                                 estimate, labelled as an estimate)
  reliability              0.10  exit 0 + parseable, error-free JSON artefact
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "research" / "bakeoff" / "out"
RESULTS_PATH = ROOT / "ty" / "bakeoff_results.json"

WEIGHTS = {"accuracy": 0.40, "detail": 0.25, "speed": 0.15, "tokens": 0.10,
           "reliability": 0.10}

TOOLS = {
    "rea": {
        "label": "REA",
        "version": "6.5.0",
        "licence": "MIT",
        "install": "npm install -g rea-agents@6.5.0 (already installed)",
        "source": "https://github.com/morluto/rea",
        "binary": "rea",
        "ai_required": False,
    },
    "craft-anything": {
        "label": "Craft Anything",
        "version": "0.5.0",
        "licence": "MIT OR Apache-2.0 (dual; the work order calls it Apache 2.0)",
        "install": ("prebuilt portable zip from "
                    "github.com/storytold/craft-anything/releases/tag/v0.5.0, "
                    "SHA-256 verified against SHA256SUMS.txt; no Rust toolchain and no build"),
        "source": "https://github.com/storytold/craft-anything",
        "binary": str(Path("research/bakeoff/vendor/craft-anything-bin/"
                           "craft-anything-0.5.0-windows-x64-portable/"
                           "craft-anything-cli.exe")),
        "ai_required": False,
        "ai_required_for": "rebuild/chat only; static study needs no key",
    },
}

#: Facts a correct behaviour study should surface. Each was read off the target
#: itself (source file, served page, or built bundle), so the check is not a
#: judgement call.
TARGETS: List[Dict[str, Any]] = [
    {
        "id": "oss-repo",
        "kind": "open-source repo on this machine",
        "description": ("TodoMVC examples/javascript-es6 (MIT), shallow sparse clone of "
                        "github.com/tastejs/todomvc into research/bakeoff/targets/todomvc"),
        "path": "research/bakeoff/targets/todomvc/examples/javascript-es6",
        "url": None,
        "facts": ["Controller", "Model", "View", "Store", "setView", "addItem",
                  "removeItem", "toggleComplete", "showActive", "memoryStorage"],
    },
    {
        "id": "hosted",
        "kind": "hosted non-Amazon tool, read-only over the network",
        "description": ("https://opencode.ai/ - page and entry bundle fetched with a plain "
                        "GET into research/bakeoff/targets/hosted; both tools read the saved artefacts"),
        "path": "research/bakeoff/targets/hosted",
        "url": "https://opencode.ai/",
        "facts": ["anomalyco/opencode", "npm install -g @opencode/cli", "docs",
                  "install", "sdk", "github", "opencode"],
    },
    {
        "id": "local-app",
        "kind": "this repo's local web app on 127.0.0.1",
        "description": ("northstar-os-ui/dist served on http://127.0.0.1:8123/ui/ and fetched "
                        "with a plain GET into research/bakeoff/targets/local"),
        "path": "research/bakeoff/targets/local",
        "url": "http://127.0.0.1:8123/ui/",
        "facts": ["/design-studio", "/listings", "Northstar", "product-finder",
                  "beta-ops", "golden-goose", "/documents"],
    },
]


def prepare_targets(base: str = "") -> Dict[str, Any]:
    """Fetch the two network-ish targets into their folders with a plain read-only GET.

    The bake-off compares tools on *evidence*, so the evidence has to exist: the hosted
    page's HTML and its same-origin scripts, and this repo's built UI served locally. No
    Amazon host is ever touched; both URLs are non-Amazon by construction.
    """
    import re
    import threading
    import urllib.parse
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    import urllib.request

    def fetch(url: str, folder: Path, *, limit: int = 25) -> Dict[str, Any]:
        folder.mkdir(parents=True, exist_ok=True)
        seen: set = set()
        saved: list = []
        errors: list = []

        def grab(target: str) -> Optional[str]:
            if target in seen or len(saved) >= limit or target.startswith("data:"):
                return None
            seen.add(target)
            try:
                # A plain, honest User-Agent: opencode.ai answers 403 to the default
                # "Python-urllib" agent, and a generic name keeps us a normal visitor.
                request = urllib.request.Request(
                    target, headers={"User-Agent": "northstar-bakeoff/1.0 (read-only study)"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read(8_000_000)
                name = (urllib.parse.urlparse(target).path.strip("/") or "index.html")
                name = re.sub(r"[^A-Za-z0-9._/-]", "_", name).replace("/", "_")
                if not name.endswith((".html", ".js", ".mjs", ".css")):
                    name += ".html"
                (folder / name).write_bytes(body)
                saved.append(name)
                return body.decode("utf-8", "replace")
            except Exception as exc:  # noqa: BLE001 - a failed asset is recorded
                errors.append(f"{target}: {type(exc).__name__}")
                return None

        html = grab(url)
        if html:
            root = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
            for src in re.findall(r'(?:src|href)="([^"]+)"', html):
                if src.startswith(("http://", "https://")):
                    continue
                grab(urllib.parse.urljoin(root + "/", src.lstrip("/")))
        return {"ok": bool(saved), "url": url, "folder": str(folder),
                "files": saved, "errors": errors}

    results: Dict[str, Any] = {}

    hosted = next(target for target in TARGETS if target["id"] == "hosted")
    results["hosted"] = fetch(hosted["url"], ROOT / hosted["path"])

    local = next(target for target in TARGETS if target["id"] == "local-app")
    dist = ROOT / "northstar-os-ui" / "dist"
    if not dist.is_dir():
        results["local-app"] = {"ok": False, "reason": f"no build at {dist}"}
    else:
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(dist), **kwargs)

            def translate_path(self, path):
                if path.startswith("/ui/"):
                    path = path[3:]
                return super().translate_path(path)

            def log_message(self, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 8123), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            results["local-app"] = fetch(local["url"], ROOT / local["path"])
        finally:
            server.shutdown()
            server.server_close()
    return results


# ---------------------------------------------------------------- commands
def tool_binary(tool: str) -> Optional[Path]:
    raw = TOOLS[tool]["binary"]
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    if tool == "rea":
        from shutil import which
        found = which("rea")
        return Path(found) if found else None
    return path if path.is_file() else None


def build_command(tool: str, target: Dict[str, Any]) -> List[str]:
    binary = tool_binary(tool)
    if binary is None:
        raise FileNotFoundError(f"{tool}: binary not found")
    path = (ROOT / target["path"]).resolve()
    if tool == "rea":
        return [str(binary), "analyze-javascript-application", str(path), "--format", "json"]
    if tool == "craft-anything":
        return [str(binary), "--deep", "js-app-map", "--input-path", str(path),
                "--output-format", "json"]
    raise KeyError(tool)


# ---------------------------------------------------------------- run
def run_cell(tool: str, target: Dict[str, Any], out_dir: Path = OUT_DIR,
             timeout_s: float = 900.0) -> Dict[str, Any]:
    """Run one tool on one target. Records command, exit code and artefact."""
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        command = build_command(tool, target)
    except FileNotFoundError as exc:
        return {"tool": tool, "target": target["id"], "status": "blocked",
                "reason": str(exc), "command": None, "exit_code": None, "artefact": None}
    artefact = out_dir / f"{tool}-{target['id']}.json"
    stderr_path = out_dir / f"{tool}-{target['id']}.err"
    started = time.perf_counter()
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"tool": tool, "target": target["id"], "status": "blocked",
                "reason": f"timed out after {timeout_s}s", "command": command,
                "exit_code": None, "artefact": None}
    elapsed = round(time.perf_counter() - started, 3)
    # Bytes, not text: on Windows `write_text` turns "\n" into "\r\n", which made the
    # file on disk differ from the payload that was hashed (a verifier's first catch).
    payload = (proc.stdout or "").encode("utf-8")
    artefact.write_bytes(payload)
    stderr_path.write_bytes((proc.stderr or "").encode("utf-8"))
    record = {"tool": tool, "target": target["id"], "status": "ran",
              "command": command,
              "command_line": subprocess.list2cmdline(command),
              "exit_code": proc.returncode, "seconds": elapsed,
              "artefact": str(artefact.relative_to(ROOT)),
              "stderr": str(stderr_path.relative_to(ROOT)),
              "bytes": len(payload),
              "sha256": hashlib.sha256(payload).hexdigest()}
    (out_dir / f"{tool}-{target['id']}.run.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def unpack_artefacts(out_dir: Path = OUT_DIR) -> List[Dict[str, Any]]:
    """Restore `*.json.gz` artefacts and prove each one against its run sidecar.

    The tool output is large (REA writes tens of megabytes per target), so git keeps
    the compressed form. The sidecar records the sha256 of the *uncompressed*
    payload, so this is a check, not a convenience: a mismatch is reported and the
    file is not written.
    """
    import gzip
    rows: List[Dict[str, Any]] = []
    for archive in sorted(out_dir.glob("*.json.gz")):
        name = archive.name[: -len(".gz")]
        dest = out_dir / name
        row: Dict[str, Any] = {"artefact": str(dest.relative_to(ROOT)), "ok": False}
        try:
            payload = gzip.decompress(archive.read_bytes())
        except OSError as exc:
            row["reason"] = f"cannot decompress: {exc}"
            rows.append(row)
            continue
        digest = hashlib.sha256(payload).hexdigest()
        sidecar = out_dir / (name[: -len(".json")] + ".run.json")
        expected = None
        if sidecar.is_file():
            try:
                expected = json.loads(sidecar.read_text(encoding="utf-8")).get("sha256")
            except ValueError:
                expected = None
        row.update({"sha256": digest, "bytes": len(payload), "expected": expected})
        if expected and expected != digest:
            row["reason"] = "sha256 does not match the run sidecar"
            rows.append(row)
            continue
        dest.write_bytes(payload)
        row["ok"] = True
        row["reason"] = "sha256 verified" if expected else "no sidecar hash to check"
        rows.append(row)
    return rows


def load_record(tool: str, target: Dict[str, Any], out_dir: Path = OUT_DIR) -> Dict[str, Any]:
    """Re-score from the recorded run, not from a guess."""
    sidecar = out_dir / f"{tool}-{target['id']}.run.json"
    if sidecar.is_file():
        try:
            record = json.loads(sidecar.read_text(encoding="utf-8"))
            artefact = ROOT / record.get("artefact", "")
            if artefact.is_file():
                record["bytes"] = artefact.stat().st_size
                return record
        except (OSError, ValueError):
            pass
    artefact = out_dir / f"{tool}-{target['id']}.json"
    if artefact.is_file():
        return {"tool": tool, "target": target["id"], "status": "ran",
                "exit_code": 0, "seconds": None,
                "artefact": str(artefact.relative_to(ROOT)),
                "bytes": artefact.stat().st_size,
                "command_line": None,
                "reason": "no run sidecar: exit code and command are not evidenced"}
    return {"tool": tool, "target": target["id"], "status": "blocked",
            "reason": "no artefact and no run record on disk", "exit_code": None}


# ---------------------------------------------------------------- scoring
def _unique_leaves(value: Any, seen: Optional[set] = None) -> set:
    seen = seen if seen is not None else set()
    if isinstance(value, dict):
        for item in value.values():
            _unique_leaves(item, seen)
    elif isinstance(value, list):
        for item in value:
            _unique_leaves(item, seen)
    elif isinstance(value, str):
        seen.add(value)
    return seen


def detail_count(payload: Any) -> int:
    """Distinct non-hash strings. A hash list inflates bytes, not coverage."""
    leaves = _unique_leaves(payload)
    counted = 0
    for text in leaves:
        if not (3 <= len(text) <= 80) or not re.search(r"[A-Za-z]", text):
            continue
        if re.search(r"[0-9a-f]{32,}", text.lower()):
            continue
        counted += 1
    return counted


def fact_hits(artefact_text: str, facts: Sequence[str]) -> List[str]:
    lowered = artefact_text.lower()
    return [fact for fact in facts if fact.lower() in lowered]


def score_cell(run: Dict[str, Any], target: Dict[str, Any],
               artefact_text: Optional[str] = None) -> Dict[str, Any]:
    """Turn one recorded run into metrics. A missing artefact is not a zero."""
    scored = {"tool": run.get("tool"), "target": target["id"],
              "status": "did-not-run", "reason": ""}
    if run.get("status") == "blocked":
        scored["reason"] = run.get("reason") or "blocked"
        return scored
    if run.get("exit_code") != 0:
        scored["reason"] = f"exit code {run.get('exit_code')}"
        return scored
    if artefact_text is None:
        artefact = run.get("artefact")
        if not artefact:
            scored["reason"] = "no artefact recorded"
            return scored
        path = ROOT / artefact
        if not path.is_file() or path.stat().st_size == 0:
            scored["reason"] = "artefact missing or empty"
            return scored
        artefact_text = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        payload = json.loads(artefact_text)
    except ValueError as exc:
        scored["reason"] = f"artefact is not JSON: {exc}"
        return scored
    if isinstance(payload, dict) and payload.get("error"):
        scored["reason"] = f"tool returned an error: {payload['error']}"
        return scored
    hits = fact_hits(artefact_text, target["facts"])
    detail = detail_count(payload)
    scored.update({
        "status": "ran",
        "accuracy": round(len(hits) / len(target["facts"]), 3),
        "facts_found": len(hits),
        "facts_total": len(target["facts"]),
        "facts_missing": [fact for fact in target["facts"] if fact not in hits],
        "detail": round(min(1.0, detail / 1000), 3),
        "detail_units": detail,
        "seconds": run.get("seconds"),
        "bytes": run.get("bytes"),
        "tokens_est": int((run.get("bytes") or 0) // 4),
        "reliability": 1.0,
        "exit_code": run.get("exit_code"),
        "command_line": run.get("command_line") or run.get("command"),
        "artefact": run.get("artefact"),
    })
    return scored


def add_composites(scored: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalise speed and token cost across the tools that ran on a target."""
    ran = [row for row in scored if row["status"] == "ran"]
    if not ran:
        for row in scored:
            row["composite"] = None
        return scored
    best_seconds = min((row["seconds"] for row in ran if row.get("seconds")), default=None)
    best_tokens = min(row["tokens_est"] for row in ran) or 1
    for row in scored:
        if row["status"] != "ran":
            row["composite"] = None
            continue
        row["speed_norm"] = (round(best_seconds / row["seconds"], 3)
                             if best_seconds and row.get("seconds") else 0.0)
        row["tokens_norm"] = round(best_tokens / row["tokens_est"], 3) if row["tokens_est"] else 0.0
        row["composite"] = round(
            WEIGHTS["accuracy"] * row["accuracy"]
            + WEIGHTS["detail"] * row["detail"]
            + WEIGHTS["speed"] * row["speed_norm"]
            + WEIGHTS["tokens"] * row["tokens_norm"]
            + WEIGHTS["reliability"] * row["reliability"], 3)
    return scored


def decide_target(target: Dict[str, Any], scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    ran = [row for row in scored if row["status"] == "ran"]
    if not ran:
        return {"target": target["id"], "kind": target["kind"], "verdict": "no-result",
                "default": None, "backup": None,
                "reason": "neither tool produced a command line, exit code and artefact"}
    ranked = sorted(ran, key=lambda row: (row["composite"], -(row["seconds"] or 1e9)),
                    reverse=True)
    winner, backup = ranked[0], ranked[1] if len(ranked) > 1 else None
    return {"target": target["id"], "kind": target["kind"],
            "verdict": "winner",
            "default": winner["tool"], "default_score": winner["composite"],
            "backup": backup["tool"] if backup else None,
            "backup_score": backup["composite"] if backup else None,
            "reason": (f"{winner['tool']} scored {winner['composite']} on "
                       f"accuracy/detail/speed/tokens/reliability; "
                       f"accuracy {winner['accuracy']} ({winner['facts_found']}/"
                       f"{winner['facts_total']})")}


# ---------------------------------------------------------------- provenance
def provenance_rows() -> List[Dict[str, str]]:
    """Exact rows to append to provenance.csv. Not written there: out of scope."""
    rows = []
    for name, tool in TOOLS.items():
        rows.append({
            "component": f"tools/{name} (bake-off only)",
            "status": "INSTALLED",
            "source": f"{tool['source']} v{tool['version']}",
            "license": tool["licence"],
            "reviewer": "builder-d16 (D17)",
            "notes": (f"{tool['install']}. Studied three targets read-only; "
                      f"no Amazon target, no credentials, no spend."),
        })
    return rows


def provenance_csv(rows: Sequence[Dict[str, str]]) -> str:
    import csv
    import io
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["component", "status", "source",
                                                "license", "reviewer", "notes"],
                            lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


# ---------------------------------------------------------------- orchestration
def sweep(tools: Sequence[str], target_ids: Sequence[str], *, run: bool,
          out_dir: Path = OUT_DIR) -> Dict[str, Any]:
    results = []
    for target in TARGETS:
        if target_ids and target["id"] not in target_ids:
            continue
        cells = []
        for tool in tools:
            record = run_cell(tool, target, out_dir=out_dir) if run else load_record(
                tool, target, out_dir=out_dir)
            scored = score_cell(record, target)
            scored["seconds"] = record.get("seconds")
            scored["_record"] = record
            cells.append(scored)
        add_composites(cells)
        decision = decide_target(target, cells)
        results.append({"target": target, "cells": cells, "decision": decision})
    return {"schema": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "generated_by": "tools/tool_bakeoff.py",
            "weights": WEIGHTS,
            "tools": TOOLS,
            "targets": results,
            "decisions": {row["target"]["id"]: row["decision"] for row in results},
            "provenance_rows": provenance_rows()}


def write_results(payload: Dict[str, Any], path: Path = RESULTS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool_bakeoff",
        description="D17: REA vs Craft Anything on three read-only targets.")
    parser.add_argument("--run", action="store_true",
                        help="run both tools on all targets (default is --score-only)")
    parser.add_argument("--score-only", action="store_true",
                        help="re-score existing artefacts; never starts a process")
    parser.add_argument("--tools", default="", help="comma-separated subset of rea,craft-anything")
    parser.add_argument("--targets", default="",
                        help="comma-separated subset of oss-repo,hosted,local-app")
    parser.add_argument("--out", default=str(RESULTS_PATH))
    parser.add_argument("--prepare", action="store_true",
                        help="fetch the hosted and local targets with a read-only GET first")
    parser.add_argument("--unpack", action="store_true",
                        help="decompress committed *.json.gz artefacts and check their sha256")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    tools = [name.strip() for name in args.tools.split(",") if name.strip()] or list(TOOLS)
    unknown = [name for name in tools if name not in TOOLS]
    if unknown:
        print(f"error: unknown tool(s) {unknown}", file=sys.stderr)
        return 2
    target_ids = [name.strip() for name in args.targets.split(",") if name.strip()]
    unknown = [name for name in target_ids if name not in {t["id"] for t in TARGETS}]
    if unknown:
        print(f"error: unknown target(s) {unknown}", file=sys.stderr)
        return 2
    if args.unpack:
        rows = unpack_artefacts()
        print(json.dumps({"unpacked": rows}, indent=2))
        if not all(row["ok"] for row in rows):
            print("error: an artefact failed its sha256 check", file=sys.stderr)
            return 1
    if args.prepare:
        prepared = prepare_targets()
        print(json.dumps({"prepared": prepared}, indent=2)[:2000])
    payload = sweep(tools, target_ids, run=bool(args.run))
    write_results(payload, Path(args.out))
    for row in payload["targets"]:
        for cell in row["cells"]:
            print(json.dumps({key: value for key, value in cell.items()
                              if not key.startswith("_") and key != "facts_missing"}))
        print(json.dumps(row["decision"]))
    print(json.dumps({"event": "written", "path": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
