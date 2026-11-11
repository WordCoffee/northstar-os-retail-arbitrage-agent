"""The production assertion script itself: positive claims and negative controls.

The negative controls matter more than the green run. A check that cannot fail
is theatre, so each family here is driven with a fixture that *should* fail:
an unhashed asset, an unallowlisted innerHTML, a checklist row with no command,
a doc citing a check that does not exist.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import production_assert as pa

REPO = PaRoot = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Asset hashing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("index-BX4gn8M-.js", True),
    ("AccountStatus-BX4gn8M-.js", True),
    ("andromeda-spiral-Dww72-xH.webp", True),
    ("index.js", False),
    ("accounts.css", False),
    ("main.js", False),
])
def test_asset_is_hashed(name, expected):
    assert pa._asset_is_hashed(name) is expected


def test_ui_dist_check_rejects_an_unhashed_asset(tmp_path):
    dist = tmp_path / "northstar-os-ui" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<script src="/ui/assets/index.js"></script>', encoding="utf-8")
    (dist / "assets" / "index.js").write_text("console.log(1)", encoding="utf-8")

    result = pa._check_ui_dist({"root": tmp_path})
    assert result["status"] == "fail"
    assert "unhashed" in result["detail"]


def test_ui_dist_check_rejects_served_source_maps(tmp_path):
    dist = tmp_path / "northstar-os-ui" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<script src="/ui/assets/index-BX4gn8M-.js"></script>', encoding="utf-8")
    (dist / "assets" / "index-BX4gn8M-.js").write_text("x", encoding="utf-8")
    (dist / "assets" / "index-BX4gn8M-.js.map").write_text("{}", encoding="utf-8")

    result = pa._check_ui_dist({"root": tmp_path})
    assert result["status"] == "fail"
    assert "source map" in result["detail"]


def test_ui_dist_check_accepts_a_hashed_build(tmp_path):
    dist = tmp_path / "northstar-os-ui" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<script src="/ui/assets/index-BX4gn8M-.js"></script>', encoding="utf-8")
    (dist / "assets" / "index-BX4gn8M-.js").write_text("x", encoding="utf-8")

    assert pa._check_ui_dist({"root": tmp_path})["status"] == "pass"


# ---------------------------------------------------------------------------
# dangerouslySetInnerHTML
# ---------------------------------------------------------------------------

def _ui_tree(tmp_path: Path, files: dict) -> Path:
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tmp_path


ICON = "northstar-os-ui/src/components/Icon.jsx"
PAGE = "northstar-os-ui/src/pages/Page.jsx"


def test_innerhtml_rejects_a_file_outside_the_allowlist(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "INNERHTML_ALLOWLIST", {
        ICON: "static table",
    })
    _ui_tree(tmp_path, {
        ICON: "const paths = {star: '<path/>'};\n"
              "const svgContent = paths[name];\n"
              "export default () => <svg dangerouslySetInnerHTML={{ __html: svgContent }} />\n",
        PAGE: "export default ({html}) => <div dangerouslySetInnerHTML={{ __html: html }} />\n",
    })
    result = pa._check_ui_innerhtml({"root": tmp_path})
    assert result["status"] == "fail"
    assert PAGE in result["detail"]


def test_innerhtml_rejects_an_expression_even_in_an_allowlisted_file(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "INNERHTML_ALLOWLIST", {ICON: "static table"})
    _ui_tree(tmp_path, {
        ICON: "const paths = {star: '<path/>'};\n"
              "export default ({name}) => <svg "
              "dangerouslySetInnerHTML={{ __html: paths[name] + '<x/>' }} />\n",
    })
    result = pa._check_ui_innerhtml({"root": tmp_path})
    assert result["status"] == "fail"
    assert "expression" in result["detail"]


def test_innerhtml_rejects_a_variable_the_file_never_derives(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "INNERHTML_ALLOWLIST", {ICON: "static table"})
    _ui_tree(tmp_path, {
        ICON: "export default ({name}) => <svg "
              "dangerouslySetInnerHTML={{ __html: svgContent }} />\n",
    })
    result = pa._check_ui_innerhtml({"root": tmp_path})
    assert result["status"] == "fail"
    assert "never derives" in result["detail"]


def test_innerhtml_ignores_a_mention_in_prose(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "INNERHTML_ALLOWLIST", {ICON: "static table"})
    _ui_tree(tmp_path, {
        ICON: "const paths = {star: '<path/>'};\n"
              "const svgContent = paths[name];\n"
              "// This component never uses dangerouslySetInnerHTML.\n"
              "export default () => <svg dangerouslySetInnerHTML={{ __html: svgContent }} />\n",
        PAGE: "/** Inline tokens -> elements. No dangerouslySetInnerHTML anywhere. */\n"
              "export default () => null\n",
    })
    result = pa._check_ui_innerhtml({"root": tmp_path})
    assert result["status"] == "pass", result["detail"]
    assert {use["file"] for use in result["evidence"]["uses"]} == {ICON}


def test_innerhtml_rejects_a_stale_allowlist_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "INNERHTML_ALLOWLIST", {
        ICON: "static table", PAGE: "gone",
    })
    _ui_tree(tmp_path, {
        ICON: "const paths = {star: '<path/>'};\n"
              "const svgContent = paths[name];\n"
              "export default () => <svg dangerouslySetInnerHTML={{ __html: svgContent }} />\n",
    })
    result = pa._check_ui_innerhtml({"root": tmp_path})
    assert result["status"] == "fail"
    assert "no longer injects HTML" in result["detail"]


# ---------------------------------------------------------------------------
# The checklist document
# ---------------------------------------------------------------------------

def _synthetic_doc() -> str:
    rows = "\n".join(
        f"| `{check_id}` | claim | `python Northstar_backend/production_assert.py --only {check_id}` | evidence |"
        for check_id in pa.CHECK_IDS
    )
    gaps = " ".join(sorted(pa.REGISTERED_SECRET_GAPS)) + " " + " ".join(
        sorted(pa.REGISTERED_HOSTED_KEY_GAPS))
    return (
        "# Readiness\n\n"
        "| Area | Requirement | Command | What it proves |\n"
        "|---|---|---|---|\n"
        f"{rows}\n\n"
        f"Registered gaps: {gaps}\n"
    )


def test_doc_rows_skip_separators_and_headers():
    text = (
        "| Area | Requirement | Command |\n"
        "|---|---|---|\n"
        "| Build | hashed | `npm run build` |\n"
    )
    rows = pa._doc_rows(text)
    assert len(rows) == 2
    assert rows[0][1][0] == "Area"


def test_docs_check_passes_on_a_complete_checklist(tmp_path):
    (tmp_path / pa.DOC_PATH).parent.mkdir(parents=True)
    (tmp_path / pa.DOC_PATH).write_text(_synthetic_doc(), encoding="utf-8")
    result = pa._check_docs({"root": tmp_path})
    assert result["status"] == "pass", result["detail"]


def test_docs_check_rejects_a_row_without_a_command(tmp_path):
    text = _synthetic_doc().replace(
        "`python Northstar_backend/production_assert.py --only health.endpoints_answer`",
        "see the script",
    )
    (tmp_path / pa.DOC_PATH).parent.mkdir(parents=True)
    (tmp_path / pa.DOC_PATH).write_text(text, encoding="utf-8")
    result = pa._check_docs({"root": tmp_path})
    assert result["status"] == "fail"
    assert "no verifiable command" in result["detail"]


def test_docs_check_rejects_an_unknown_check_id(tmp_path):
    (tmp_path / pa.DOC_PATH).parent.mkdir(parents=True)
    (tmp_path / pa.DOC_PATH).write_text(
        _synthetic_doc() + "\nSee `ui.this_check_was_deleted`.\n", encoding="utf-8")
    result = pa._check_docs({"root": tmp_path})
    assert result["status"] == "fail"
    assert "do not exist" in result["detail"]


def test_docs_check_rejects_an_undocumented_check(tmp_path):
    text = _synthetic_doc().replace("ui.served_bundle_clean", "ui.served_bundle_old")
    (tmp_path / pa.DOC_PATH).parent.mkdir(parents=True)
    (tmp_path / pa.DOC_PATH).write_text(text, encoding="utf-8")
    result = pa._check_docs({"root": tmp_path})
    assert result["status"] == "fail"
    assert "missing from the doc" in result["detail"]


def test_docs_check_rejects_a_missing_document(tmp_path):
    result = pa._check_docs({"root": tmp_path})
    assert result["status"] == "fail"
    assert "missing" in result["detail"]


# ---------------------------------------------------------------------------
# Real-repo claims (integration)
# ---------------------------------------------------------------------------

def test_env_example_covers_import_time_secrets_in_this_repo():
    result = pa._check_env_secrets({"root": REPO})
    assert result["status"] == "pass", result["detail"]
    for gap in pa.REGISTERED_SECRET_GAPS:
        assert any(gap in note for note in result["advisories"]), gap


def test_hosted_keys_are_documented_in_this_repo():
    result = pa._check_env_hosted({"root": REPO})
    assert result["status"] == "pass", result["detail"]
    assert result["evidence"]["hosted_keys"] >= 10


def test_no_secret_in_shipped_code_in_this_repo():
    result = pa._check_secrets_repo({"root": REPO})
    assert result["status"] == "pass", result["detail"]
    assert result["evidence"]["files_scanned"] > 1000


def test_redaction_is_enforced_in_this_repo():
    result = pa._check_redaction({"root": REPO})
    assert result["status"] == "pass", result["detail"]
    assert result["evidence"]["leaked_values"] == 0


def test_backup_drill_backs_up_and_restores_in_this_repo():
    result = pa._check_backup({"root": REPO})
    if "nothing to drill" in result["detail"]:
        pytest.skip("no SQLite stores in this checkout")
    assert result["status"] == "pass", result["detail"]
    assert result["evidence"]["verified"] == len(result["evidence"]["stores_backed_up"])
    assert result["evidence"]["restores"]


def test_dev_bypass_is_guarded_in_this_repo():
    result = pa._check_dev_bypass({"root": REPO})
    assert result["status"] == "pass", result["detail"]


def test_the_checklist_in_this_repo_carries_commands():
    result = pa._check_docs({"root": REPO})
    assert result["status"] == "pass", result["detail"]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def test_list_prints_every_check_id(capsys):
    assert pa.main(["--list"]) == 0
    printed = capsys.readouterr().out.split()
    assert printed == list(pa.CHECK_IDS)
    assert len(printed) == len(pa.CHECKS)


def test_an_unknown_only_filter_is_an_error():
    report = pa.run(only=["no.such_check"])
    assert report["ok"] is False
    assert "no check matches" in report["error"]
    assert pa.main(["--json", "--only", "no.such_check"]) == 1


def test_json_report_has_a_stable_shape(capsys):
    assert pa.main(["--json", "--only", "docs.checklist_commands"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == pa.SCHEMA
    assert set(report["summary"]) == {"pass", "fail", "skip", "advisory"}
    for check in report["checks"]:
        assert set(check) >= {"id", "title", "status", "detail", "command",
                              "evidence", "advisories"}


def test_a_crashing_check_is_reported_as_a_failure(monkeypatch):
    def _boom(_ctx):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(pa, "CHECKS", (("docs.checklist_commands", _boom),))
    report = pa.run()
    assert report["ok"] is False
    assert report["summary"]["fail"] == 1
    assert "kaboom" in report["checks"][0]["detail"]


@pytest.mark.skipif(
    not (REPO / "northstar-os-ui" / "dist" / "index.html").is_file(),
    reason="no production build in this tree",
)
@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_full_run_is_production_shaped():
    report = pa.run()
    failed = [(row["id"], row["detail"]) for row in report["checks"]
              if row["status"] != "pass"]
    assert report["ok"] is True, failed
    assert len(report["checks"]) == len(pa.CHECKS)
    assert report["summary"]["pass"] == len(pa.CHECKS)
    assert report["summary"]["fail"] == 0
