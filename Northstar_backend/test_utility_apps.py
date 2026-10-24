"""BOJO-UTIL: a calculator request must produce a calculator, not an offer.

The scope test always passed on classification; these tests are about output.
"""

from pathlib import Path
from types import SimpleNamespace

import chat_tools
import shell_focus
from specialists import utility_apps as ua


def test_the_router_and_the_builder_agree_that_a_calculator_is_bojo_work():
    from specialists import router
    scope = router.scope("make me a quick tip calculator")
    assert scope["kind"] == "utility"
    built = ua.build("make me a quick tip calculator")
    assert built["ok"] is True
    assert built["template"] == "tip"


def test_an_unknown_utility_is_refused_with_a_list_of_what_can_be_built():
    out = ua.build("make me a rocket telemetry dashboard")
    assert out["ok"] is False
    assert out["reason"] == "no_template"
    assert len(out["available"]) == 3
    assert "tip calculator" in " ".join(out["available"]).lower()


def test_every_page_is_self_contained():
    for tpl in ua.TEMPLATES:
        low = tpl.build().lower()
        for banned in ("http://", "https://", "<script src", "@import", "url(http", "cdn."):
            assert banned not in low, f"{tpl.id} reaches outside itself: {banned}"


def test_the_formula_on_the_page_matches_the_one_under_test():
    """The arithmetic exists twice (Python + JS); this keeps them honest."""
    pages = {t.id: t.build() for t in ua.TEMPLATES}
    pairs = (("tip", ua.TIP_TOTAL), ("tip", ua.TIP_SHARE),
             ("percentage", ua.PCT_OF), ("percentage", ua.PCT_IS),
             ("breakeven", ua.BREAK_UNITS), ("breakeven", ua.BREAK_MARGIN))
    for template_id, formula in pairs:
        assert formula in pages[template_id], f"{template_id} page never computes {formula}"


def test_no_field_ships_with_an_invented_value():
    """A plausible default (18% tip) is still a number the user did not give."""
    page = ua.build("tip calculator")["html"]
    assert 'value=""' in page
    assert 'value="18"' not in page
    assert "placeholder" in page


def test_a_build_writes_the_file_it_reports(tmp_path):
    out = ua.build("a percentage calculator", out_dir=tmp_path)
    assert out["ok"] is True and out["template"] == "percentage"
    assert out["mime_type"] == "text/html"
    written = Path(str(out["path"]))
    assert written.exists()
    assert written.read_text(encoding="utf-8") == out["html"]


def test_the_same_request_builds_byte_identical_html():
    assert ua.build("break even calculator")["html"] == ua.build("break-even")["html"]


def test_the_page_title_is_escaped():
    page = ua._page(title="<script>alert(1)</script>", lede="x", body="", script="")
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;" in page


def test_the_tool_refuses_without_an_account_instead_of_claiming_a_build():
    res = chat_tools.run_tool("build_utility", {"request": "a tip calculator"}, {})
    assert res["ok"] is False
    assert "store" in res["summary"].lower()


def test_the_tool_persists_a_utility_app_asset():
    class Assets:
        def __init__(self):
            self.calls = []

        def create(self, payload):
            self.calls.append(payload)
            return "asset-util-1"

    db = SimpleNamespace(design_studio=SimpleNamespace(assets=Assets()))
    res = chat_tools.run_tool(
        "build_utility", {"request": "a quick tip calculator"},
        {"db": db, "account_id": "acct-1"})

    assert res["ok"] is True
    assert res["assets"][0]["id"] == "asset-util-1"
    assert res["assets"][0]["url"].endswith("/file")
    payload = db.design_studio.assets.calls[0]
    assert payload["asset_type"] == "utility-app"
    assert payload["mime_type"] == "text/html"
    assert payload["metadata"]["utility"]["template"] == "tip"

    written = Path(chat_tools._out_dir()) / payload["storage_key"]
    assert written.exists(), "the asset row must point at a file that exists"
    written.unlink()


def test_every_element_the_javascript_reaches_for_actually_exists():
    """A typo here is a page that renders and silently never computes."""
    import re
    for tpl in ua.TEMPLATES:
        page = tpl.build()
        wanted = set(re.findall(r"(?:getElementById|num)\(['\"]([^'\"]+)['\"]\)", page))
        wanted |= set(re.findall(r"set\(['\"]([^'\"]+)['\"]", page))
        present = set(re.findall(r'id="([^"]+)"', page))
        assert wanted, f"{tpl.id} page never reads an input"
        assert wanted <= present, f"{tpl.id} reads missing ids: {sorted(wanted - present)}"


def test_the_utility_tool_is_reachable_where_the_work_happens():
    assert "build_utility" in shell_focus.tools_for_focus("operate")
    assert "build_utility" in shell_focus.tools_for_focus("create")
