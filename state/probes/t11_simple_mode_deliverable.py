"""t11 - simple-mode deliverable gate (scripted, live).

Submits one render through the real endpoint with the adherence gate armed and
asserts the whole promise:

  1. the vision gate accepts the render,
  2. the deliverable folder exists with the five expected files,
  3. every manifest field is resolved - no nulls, no placeholders,
  4. the manifest lists the folder accurately (including itself),
  5. the list endpoint returns the run,
  6. the preview endpoint returns a real PNG,
  7. the built UI bundle actually carries the panel that reads these endpoints.

Run:  python state/probes/t11_simple_mode_deliverable.py
Exit: 0 pass, 1 fail. Needs the backend on 127.0.0.1:8000 with the engine armed.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8000/api/design-studio"
HEADERS = {"X-User-Id": "demo-t2", "Content-Type": "application/json"}
PLACEHOLDERS = ("todo", "tbd", "placeholder", "lorem", "xxx", "none")
REQUIRED = {"run_id", "created_at", "brief", "adherence", "files", "bytes", "citations"}
BRIEF = ("a 6 oz stand-up pouch of organic lion's mane mushroom powder on a warm "
         "neutral background, soft studio light, premium packaging photography, "
         "no text, no lettering")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"X-User-Id": "demo-t2"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _nulls(obj, path="manifest"):
    out = []
    if obj is None:
        out.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_nulls(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_nulls(v, f"{path}[{i}]"))
    return out


def fail(msg: str, detail=None) -> int:
    print(f"FAIL: {msg}")
    if detail is not None:
        print(json.dumps(detail, indent=2)[:1200])
    return 1


def main() -> int:
    payload = {"kind": "image", "brief": BRIEF, "tier": "draft", "text_safe": True,
               "form": "pouch", "deliver": True}
    req = urllib.request.Request(f"{BASE}/generate", data=json.dumps(payload).encode(),
                                 headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=900) as r:
        body = json.loads(r.read().decode())

    adherence = body.get("adherence") or {}
    if not adherence.get("ok"):
        return fail("the vision gate did not accept the render", adherence)
    package = body.get("deliverable") or {}
    folder = Path(package.get("folder") or "")
    if not folder.is_dir():
        return fail("no deliverable folder was written", {"folder": str(folder)})

    expected = {"adherence.json", "brief.txt", "citations.json", "final.png", "manifest.json"}
    present = {p.name for p in folder.iterdir() if p.is_file()}
    if present != expected:
        return fail("folder contents differ", sorted(present))

    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    missing = REQUIRED - set(manifest)
    if missing:
        return fail("manifest is missing required fields", sorted(missing))
    nulls = _nulls(manifest)
    if nulls:
        return fail("manifest holds null fields", nulls)
    raw = json.dumps(manifest).lower()
    hits = [w for w in PLACEHOLDERS if w in raw]
    if hits:
        return fail("manifest holds placeholder words", hits)
    if sorted(manifest["files"]) != sorted(present):
        return fail("manifest file list does not match the folder",
                    {"manifest": sorted(manifest["files"]), "disk": sorted(present)})
    if manifest["adherence"]["requested"] != "pouch" or manifest["adherence"]["observed"] != "pouch":
        return fail("manifest verdict does not match the acceptance", manifest["adherence"])
    if manifest["bytes"] <= 0 or (folder / "final.png").stat().st_size != manifest["bytes"]:
        return fail("manifest byte count does not match final.png")

    runs = json.loads(_get(f"{BASE}/deliverables").decode())
    if manifest["run_id"] not in [row.get("run_id") for row in runs.get("deliverables", [])]:
        return fail("the run is not listed by the deliverables endpoint")

    png = _get(f"{BASE}/deliverables/{manifest['run_id']}/final")
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        return fail("the preview endpoint did not return a PNG")

    try:
        _get(f"{BASE}/deliverables/no-such-run/final")
        return fail("an unknown run returned a preview instead of 404")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            return fail("an unknown run returned the wrong status", {"status": exc.code})

    bundles = list((ROOT / "northstar-os-ui" / "dist" / "assets").glob("*.js"))
    if not any("deliverables-panel" in p.read_text(encoding="utf-8", errors="ignore")
               for p in bundles):
        return fail("the built UI bundle does not contain the deliverables panel")

    print("PASS t11 simple-mode deliverable")
    print(f"  run_id        {manifest['run_id']}")
    print(f"  folder        {folder}")
    print(f"  files         {', '.join(sorted(present))}")
    print(f"  image         {manifest.get('image_size')} / {manifest['bytes']} bytes")
    print(f"  verdict       {manifest['adherence']['requested']} -> "
          f"{manifest['adherence']['observed']} (ok={manifest['adherence']['ok']})")
    print(f"  manifest keys {len(manifest)}")
    print("  ui            built bundle carries the panel (no browser run: static check)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
