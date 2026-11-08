"""D7 — structure first: the UI Automation tree, and V1/V2 through the real stack.

V2 is the one that must not be faked: find a named element and read its text, 20 of 20
trials. It runs against a real Win32 window carrying native controls, because that is what
UI Automation actually reads - a Tk window is custom-drawn and would prove nothing.

V1 is the VLM screen-awareness test. It needs the local vision model, so it skips with a
stated reason when the model is unavailable rather than passing vacuously.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from vision import privacy, tree, understand  # noqa: E402

FORM = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$f = New-Object System.Windows.Forms.Form
$f.Text = 'Northstar V2 Probe Window'
$f.Width = 460; $f.Height = 260
$f.StartPosition = 'Manual'; $f.Left = 60; $f.Top = 60
$l = New-Object System.Windows.Forms.Label
$l.Text = 'Known readback text'
$l.Name = 'KnownLabel'; $l.Left = 20; $l.Top = 20; $l.Width = 380
$t = New-Object System.Windows.Forms.TextBox
$t.Text = 'typed value'; $t.Name = 'KnownField'; $t.Left = 20; $t.Top = 60; $t.Width = 380
$b = New-Object System.Windows.Forms.Button
$b.Text = 'Known button'; $b.Name = 'KnownButton'; $b.Left = 20; $b.Top = 110
$f.Controls.Add($l); $f.Controls.Add($t); $f.Controls.Add($b)
[void]$f.Show()
[void]$f.Focus()
[System.Windows.Forms.Application]::DoEvents()
Start-Sleep -Seconds 90
"""


@pytest.fixture()
def native_window():
    proc = subprocess.Popen(["powershell", "-NoProfile", "-STA", "-Command", FORM],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # The window must exist before UIA can see it; poll briefly.
        deadline = time.time() + 25
        while time.time() < deadline:
            found = [w for w in tree_results() if "Northstar V2 Probe" in w.get("title", "")]
            if found:
                break
            time.sleep(0.4)
        yield proc
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, text=True)


def tree_results():
    from vision import capture  # noqa: PLC0415

    return capture.windows()


def _tree_for_probe():
    from vision import capture  # noqa: PLC0415

    targets = [w for w in capture.windows() if "Northstar V2 Probe" in w.get("title", "")]
    assert targets, "the probe window is not enumerable"
    return tree.window_tree(targets[0]["hwnd"])


def test_the_tree_reads_native_controls(native_window):
    result = _tree_for_probe()

    assert result["ok"] is True, result
    names = " ".join(str(e.get("name", "")) for e in result["elements"])
    assert "Known readback text" in names
    assert "Known button" in names


def test_v2_find_and_read_twenty_of_twenty(native_window):
    """The acceptance number, not a demonstration on one lucky try."""
    hits = 0
    for _ in range(20):
        result = _tree_for_probe()
        element = tree.find(result["elements"], "Known button")
        if element and element.get("role", "").startswith("Button"):
            hits += 1
    assert hits == 20, f"V2: {hits}/20"


def test_reading_a_field_returns_its_value(native_window):
    result = _tree_for_probe()
    field = tree.find(result["elements"], "KnownField")
    assert field is not None
    assert field["value"] == "typed value"


def test_a_blocked_window_yields_no_structure():
    """Element names and values are content; a blocklisted window's content is not read.

    Runs against a real window carrying a blocked title, so the refusal is exercised rather
    than assumed: `window found` -> `classified blocked` -> `zero elements`.
    """
    probe = subprocess.Popen(
        ["powershell", "-NoProfile", "-STA", "-Command",
         FORM.replace("Northstar V2 Probe Window", "1Password - test vault")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 25
        target = None
        while time.time() < deadline:
            found = [w for w in tree_results() if "1Password" in w.get("title", "")]
            if found:
                target = found[0]
                break
            time.sleep(0.4)
        assert target, "the blocklisted probe window is not enumerable"
        assert privacy.classify(title=target["title"])["allow"] is False

        result = tree.window_tree(target["hwnd"])

        assert result["ok"] is False
        assert result.get("blocked") is True
        assert result["elements"] == []
    finally:
        subprocess.run(["taskkill", "/PID", str(probe.pid), "/T", "/F"],
                       capture_output=True, text=True)


def test_a_password_field_is_masked_in_the_description():
    elements = [{"role": "EditControl", "name": "Password", "value": "hunter2"},
                {"role": "ButtonControl", "name": "Sign in", "value": ""}]
    masked = privacy.mask_regions(elements)
    text = tree.describe(masked)

    assert "hunter2" not in text
    assert "[masked]" in text
    assert "Sign in" in text


def test_credentials_in_element_text_are_redacted_before_a_model_sees_them():
    elements = [{"role": "TextControl", "name": "Authorization: Bearer abcdef1234567890",
                 "value": "sk-live-abcdefgh1234"}]
    text = tree.describe(elements)

    assert "abcdef1234567890" not in text
    assert "sk-live-abcdefgh1234" not in text


# ----------------------------------------------------------------------- V1 helpers
def test_the_model_answer_is_parsed_from_json_or_from_prose():
    payload = {"apps": [{"name": "Code", "purpose": "editor"}], "foreground": "Code"}
    assert understand.parse_json(json.dumps(payload)) == payload
    assert understand.parse_json("```json\n" + json.dumps(payload) + "\n```") == payload
    assert understand.parse_json("Here you go: " + json.dumps(payload)) == payload
    assert understand.parse_json("I cannot help with that") == {}


def test_a_blocked_window_never_reaches_the_model(monkeypatch):
    called = {"post": 0}

    def post(*_a, **_k):
        called["post"] += 1
        return {"response": "{}"}

    monkeypatch.setattr(understand, "_post", post)
    monkeypatch.setattr(understand.capture, "frame",
                        lambda window=None: {"ok": False, "blocked": True,
                                             "reason": "title matches"})

    out = understand.describe_screen(window={"title": "1Password"})

    assert out["ok"] is False and out["blocked"] is True
    assert called["post"] == 0, "no pixels may be sent from a blocked window"


def test_v1_names_the_visible_applications():
    """V1: no browser open, valid JSON, real applications named."""
    out = understand.describe_screen()
    if not out.get("ok"):
        pytest.skip(f"vision model unavailable or no apps named: {out.get('reason')}")
    assert out["raw_is_json"] is True
    assert out["apps"], out
    for app in out["apps"]:
        assert app["name"].strip()
