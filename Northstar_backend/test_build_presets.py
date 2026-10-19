"""BUILD presets — additive to the six WORK foci, and impossible to drift apart.

The regression this file exists to prevent: adding Thorn's presets to the focus
catalogue would break the V3 shell gate, which asserts exactly six chips. The BUILD
family must stay out of FOCUS_MODES.
"""
from __future__ import annotations

import build_presets as bp
import chat_tools
import shell_focus


def test_the_four_plan_presets_exist():
    assert bp.preset_ids() == ["coding", "general_chat", "product_design", "system_architecture"]


def test_every_preset_tool_is_actually_registered():
    """A preset may never advertise a tool the registry does not have."""
    for pid in bp.preset_ids():
        resolved = bp.resolve(pid)
        assert resolved["ok"] is True
        for tool in resolved["tools"]:
            assert tool in chat_tools.TOOLS, f"{pid} advertises unregistered tool {tool}"


def test_resolve_validates_its_contract():
    out = bp.resolve("coding")
    assert out["family"] == "build"
    assert out["memory_retention"] in bp.RETENTIONS
    assert out["model_family"] in bp.FAMILIES
    assert out["system_addendum"].strip()
    assert out["tools_available"]

    missing = bp.resolve("nope")
    assert missing["ok"] is False and missing["known"] == bp.preset_ids()


def test_build_presets_do_not_replace_the_work_foci():
    """The V3 shell gate asserts exactly six focus chips."""
    assert len(shell_focus.FOCUS_MODES) == 6
    focus_ids = {f["id"] for f in shell_focus.FOCUS_MODES}
    assert focus_ids == {"auto", "create", "grow", "research", "operate", "autothink"}
    for pid in bp.preset_ids():
        assert pid not in focus_ids
    assert not any(f.get("family") == "build" for f in shell_focus.FOCUS_MODES)


def test_for_track_maps_the_autothink_router_tracks():
    assert bp.for_track("build")["id"] == "coding"
    assert bp.for_track("code")["id"] == "coding"
    assert bp.for_track("research")["id"] == "system_architecture"
    assert bp.for_track("design")["id"] == "product_design"
    fallback = bp.for_track("something-else")
    assert fallback["id"] == "general_chat"
    assert fallback["mapped_from_track"] is None


def test_catalogue_lists_the_family_and_says_it_is_separate():
    cat = bp.catalogue()
    assert cat["family"] == "build"
    assert len(cat["presets"]) == 4
    assert "do not replace" in cat["note"]


def test_build_preset_chat_tool_is_registered_and_callable():
    assert "build_preset" in chat_tools.TOOLS
    spec = chat_tools.TOOLS["build_preset"]
    assert spec["parameters"]["properties"]["preset"]["enum"] and (
        sorted(spec["parameters"]["properties"]["preset"]["enum"]) == bp.preset_ids())

    one = chat_tools.run_tool("build_preset", {"preset": "coding"})
    assert one["ok"] is True
    assert "Coding" in one["summary"]
    assert one["preset"]["family"] == "build"

    whole = chat_tools.run_tool("build_preset", {})
    assert whole["ok"] is True
    assert len(whole["catalogue"]["presets"]) == 4

    by_track = chat_tools.run_tool("build_preset", {"track": "build"})
    assert by_track["ok"] is True and by_track["preset"]["id"] == "coding"

    bad = chat_tools.run_tool("build_preset", {"preset": "not-a-preset"})
    assert bad["ok"] is False
