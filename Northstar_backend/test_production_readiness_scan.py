"""The readiness scanner must not cry wolf.

A scanner is only useful if a finding is worth acting on. Every case below pins a
way it could lie: counting a tag inside a comment, missing a label that is
present, ignoring a declared waiver, or flagging a button that cannot submit.

The checks read module-level roots, so each test points them at a temporary tree.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import production_readiness_scan as prs  # noqa: E402


def _tree(tmp_path, files):
    """files: {relative path: source}. Returns the UI src root."""
    ui = tmp_path / "ui"
    for rel, body in files.items():
        path = ui / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return ui


def _run(tmp_path, monkeypatch, files, check):
    ui = _tree(tmp_path, files)
    monkeypatch.setattr(prs, "UI_SRC", ui)
    return check()


# ── comment stripping ───────────────────────────────────────────────────────

def test_comments_are_not_code():
    text = '// an <img> in a comment\nconst a = 1\n/* <img> block */\n'
    stripped = prs._strip_comments(text)
    assert "<img>" not in stripped
    assert len(stripped) == len(text), "offsets must be preserved"
    assert stripped.count("\n") == text.count("\n")


def test_a_double_slash_inside_a_string_is_not_a_comment():
    text = 'const url = "http://x/y"\nconst b = 2\n'
    stripped = prs._strip_comments(text)
    assert "http://x/y" in stripped
    assert "const b = 2" in stripped


def test_an_img_in_a_comment_is_not_reported(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "// renders an <img> later\nexport default () => null\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_images) == []


# ── images and buttons ──────────────────────────────────────────────────────

def test_an_img_without_alt_is_reported(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "export default () => <img src='x.png' />\n"}
    found = _run(tmp_path, monkeypatch, files, prs.check_images)
    assert len(found) == 1 and found[0]["check"] == "img-no-alt"


def test_an_img_with_alt_is_clean(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "export default () => <img src='x.png' alt='a pouch' />\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_images) == []


def test_a_button_outside_a_form_is_not_a_defect(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "export default () => <button onClick={go}>Go</button>\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_buttons) == []


def test_a_button_inside_a_form_without_type_is_a_defect(tmp_path, monkeypatch):
    files = {"pages/A.jsx":
             "export default () => <form onSubmit={save}><button onClick={go}>Go</button></form>\n"}
    found = _run(tmp_path, monkeypatch, files, prs.check_buttons)
    assert len(found) == 1 and found[0]["severity"] == "high"


def test_a_typed_button_inside_a_form_is_clean(tmp_path, monkeypatch):
    files = {"pages/A.jsx":
             "export default () => <form><button type='button' onClick={go}>Go</button></form>\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_buttons) == []


# ── inputs ──────────────────────────────────────────────────────────────────

def test_an_input_with_aria_label_is_clean(tmp_path, monkeypatch):
    files = {"pages/A.jsx":
             "export default () => <input aria-label='Search rooms' placeholder='x' />\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_inputs) == []


def test_an_input_wrapped_by_a_label_is_clean(tmp_path, monkeypatch):
    files = {"pages/A.jsx":
             "export default () => (<label>Name<input value='' /></label>)\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_inputs) == []


def test_a_bare_input_is_reported(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "export default () => <input value='' />\n"}
    found = _run(tmp_path, monkeypatch, files, prs.check_inputs)
    assert len(found) == 1 and found[0]["check"] == "input-unlabelled"


def test_a_declared_waiver_suppresses_the_finding(tmp_path, monkeypatch):
    files = {"components/Fields.jsx":
             "// readiness-scan: input-unlabelled waived - the consumer supplies <Field label>\n"
             "export default () => <input value='' />\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_inputs) == []


def test_a_waiver_is_reported_so_it_can_be_reviewed(tmp_path, monkeypatch):
    ui = _tree(tmp_path, {"components/Fields.jsx":
                          "// readiness-scan: input-unlabelled waived - consumer labels it\n"})
    monkeypatch.setattr(prs, "UI_SRC", ui)
    monkeypatch.setattr(prs, "BACKEND", tmp_path / "none")
    report = prs.scan(["input-unlabelled"])
    assert report["waivers"], "a waiver must be visible in the report"
    assert "consumer labels it" in report["waivers"][0]["reason"]


# ── dead modules ────────────────────────────────────────────────────────────

def test_a_lib_module_nothing_imports_is_dead(tmp_path, monkeypatch):
    files = {"lib/orphan.js": "export const x = 1\n",
             "pages/A.jsx": "export default () => null\n"}
    found = _run(tmp_path, monkeypatch, files, prs.check_dead_modules)
    assert [f["file"].split("/")[-1] for f in found] == ["orphan.js"]


def test_a_lib_module_with_an_importer_is_not_dead(tmp_path, monkeypatch):
    files = {"lib/used.js": "export const x = 1\n",
             "pages/A.jsx": "import { x } from '../lib/used.js'\nexport default () => x\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_dead_modules) == []


# ── placeholder copy ────────────────────────────────────────────────────────

def test_placeholder_copy_is_found(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "export const note = 'TODO: wire this up'\n"}
    found = _run(tmp_path, monkeypatch, files, prs.check_placeholder_copy)
    assert len(found) == 1


# ── error state that is set but never shown ─────────────────────────────────

def test_an_error_that_is_rendered_is_clean(tmp_path, monkeypatch):
    files = {"pages/A.jsx":
             "export default function A(){\n"
             "  const [error, setError] = useState('')\n"
             "  const go = () => setError('boom')\n"
             "  return (<div><button type='button' onClick={go}>Go</button>{error}</div>)\n"
             "}\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_error_state_unrendered) == []


def test_an_error_that_is_never_rendered_is_a_defect(tmp_path, monkeypatch):
    files = {"pages/A.jsx":
             "export default function A(){\n"
             "  const [error, setError] = useState('')\n"
             "  const go = () => setError('boom')\n"
             "  return (<div><button type='button' onClick={go}>Go</button></div>)\n"
             "}\n"}
    found = _run(tmp_path, monkeypatch, files, prs.check_error_state_unrendered)
    assert len(found) == 1 and found[0]["severity"] == "high"


def test_a_state_that_is_never_set_is_not_a_finding(tmp_path, monkeypatch):
    files = {"pages/A.jsx":
             "export default function A(){\n"
             "  const [error, setError] = useState('')\n"
             "  return (<div>{error}</div>)\n"
             "}\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_error_state_unrendered) == []


def test_a_hook_without_jsx_is_not_checked(tmp_path, monkeypatch):
    """A store returns state for its consumer to render; it renders nothing itself."""
    files = {"studio/engine/store.js":
             "export function useStore(){\n"
             "  const [error, setError] = useState('')\n"
             "  const load = async () => { try { await go() } catch (e) { setError(e.message) } }\n"
             "  return { error, load }\n"
             "}\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_error_state_unrendered) == []


# ── icon-only buttons ──────────────────────────────────────────────────────

def test_an_icon_button_with_a_name_is_clean(tmp_path, monkeypatch):
    files = {"pages/A.jsx":
             "export default () => <button aria-label='Close'><svg /></button>\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_icon_buttons) == []


def test_an_icon_button_without_a_name_is_a_defect(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "export default () => <button><svg /></button>\n"}
    found = _run(tmp_path, monkeypatch, files, prs.check_icon_buttons)
    assert len(found) == 1 and found[0]["check"] == "icon-button-unnamed"


def test_an_icon_button_with_a_title_is_clean(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "export default () => <button title='Close'><svg /></button>\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_icon_buttons) == []


def test_a_button_with_text_is_not_an_icon_button(tmp_path, monkeypatch):
    files = {"pages/A.jsx": "export default () => <button><svg />Close</button>\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_icon_buttons) == []


def test_an_expression_child_is_undecidable_not_a_finding(tmp_path, monkeypatch):
    """The rail renders {g.label}: an expression may be text, so it cannot be flagged."""
    files = {"pages/A.jsx":
             "export default () => <button><svg /><span>{label}</span></button>\n"}
    assert _run(tmp_path, monkeypatch, files, prs.check_icon_buttons) == []
