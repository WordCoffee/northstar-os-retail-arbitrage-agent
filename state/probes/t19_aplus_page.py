"""Contract: a complete A+ page from product copy, every module measured.

The renderer already refuses a bad module. This probe requires the missing
half: a brief that produces a full page (header, tiles, comparison, banner,
premium, logo) in which every module's own QA passes, the canvases are exact,
the bytes are under the A+ limit, the output is deterministic, and prohibited
copy is refused before a pixel is written.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import aplus_brief as ab  # noqa: E402
import aplus_layout as geo  # noqa: E402
import aplus_render as ar  # noqa: E402

PRODUCT = {
    "brand": "MOGRA", "product": "LION'S MANE", "subtitle": "MUSHROOM POWDER",
    "weight": "6 oz (170 g)", "claims": ["100% PURE", "NO FILLERS"],
}


def main() -> int:
    result = ab.build_page(PRODUCT)
    page = result["page"]
    print("page ok", page.get("ok"), "problems", page.get("problems"))
    assert page.get("ok") is True, page
    assert not page.get("problems"), page["problems"]
    assert len(result["modules"]) == len(ab.PAGE_MODULES), result["modules"]

    for module in result["modules"]:
        kind = module["kind"]
        print(f"{kind:16s} {module['size']} {module['bytes']} B "
              f"qa={module['qa']['ok']} sha={module['sha256'][:12]}")
        assert module["qa"]["ok"] is True, module
        assert tuple(module["size"]) == tuple(geo.CANVAS[kind]), (kind, module["size"])
        assert module["bytes"] < 2 * 1024 * 1024, (kind, module["bytes"])

    again = ab.build_page(PRODUCT)
    assert [m["sha256"] for m in result["modules"]] == [
        m["sha256"] for m in again["modules"]
    ], "the A+ pack is not deterministic"

    bad = {**PRODUCT, "claims": ["cures disease"]}
    try:
        ab.build_page(bad)
    except ar.AplusNotPerfect as exc:
        print("prohibited copy refused:", str(exc)[:120])
    else:
        raise AssertionError("a prohibited medical claim must be refused")
    print("t19 aplus page: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
