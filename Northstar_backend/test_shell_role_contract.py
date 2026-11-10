"""Regression tests for the role-vocabulary mismatch that broke the shell.

Two symptoms came from ONE defect: the session carries a BACKEND role
(organization_owner, operator, internal_platform_admin) while the shell's
permission checks compare against the UI display vocabulary (operator,
platform_admin, customer). Direct comparison matched nothing, so:

  - SuiteRail filtered every nav group out and rendered the
    "Sign in to open your workspace" stub for a SIGNED-IN owner, and
  - App.jsx's GuardedRoutes redirected every platform admin away from
    /beta-ops and /admin back to /home.

data/roles.js now owns the translation in both directions, and both call sites
use it. These tests pin that contract.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "northstar-os-ui" / "src"

# The checker's filename contains a dash, so it is not importable by name.
import importlib.util as _ilu  # noqa: E402

_checker_path = Path(__file__).resolve().parent.parent / "tools" / "check-jsx-imports.py"
_spec = _ilu.spec_from_file_location("check_jsx_imports", _checker_path)
_checker = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_checker)
names_from = _checker.names_from


def _read(rel: str) -> str:
    return io.open(SRC / rel, encoding="utf-8").read()


# --- the translation itself -------------------------------------------------

def test_inverse_role_map_covers_every_backend_role():
    from importlib import util
    spec = util.spec_from_file_location("roles_js", SRC / "data" / "roles.js")
    # Parse the file directly: it is an ES module, so read the mapping table.
    text = _read("data/roles.js")
    listed = set(re.findall(r"\['([a-z_]+)',\s*'([a-z_]+)'\]", text))
    assert ("internal_platform_admin", "platform_admin") in listed, listed
    assert ("organization_owner", "customer") in listed, listed
    assert ("operator", "operator") in listed, listed
    assert ("viewer", "invitee") in listed, listed


def test_from_backend_role_is_exported():
    assert "export function fromBackendRole" in _read("data/roles.js")


def test_unknown_role_fails_closed():
    text = _read("data/roles.js")
    assert "return 'invitee'" in text, "an unknown role must fail closed"


# --- both call sites use the translation ------------------------------------

def test_suite_rail_translates_the_role():
    text = _read("components/SuiteRail.jsx")
    assert "fromBackendRole" in text, "SuiteRail must translate the backend role"
    assert "roleLabelFromUi" not in text, "the undefined helper must stay removed"


def test_app_guard_translates_the_role():
    text = _read("App.jsx")
    assert "fromBackendRole" in text, "App.jsx's guard must translate the role"
    # The guard's comparison must be against the translated value.
    guard = text[text.find("function GuardedRoutes"):]
    assert "role !== 'platform_admin'" in guard


# --- no undefined JSX component references ---------------------------------

def test_the_checker_ignores_a_component_name_inside_a_comment(tmp_path):
    """A comment explaining why a page has no router outlet is not a reference to one."""
    sample = (
        "// the shell renders this instead of an <Outlet/> swap\n"
        "/* and <Ghost/> here is prose too */\n"
        "const url = 'https://example.com/path'\n"
        "export default function A() { return <Real /> }\n"
    )
    cleaned = _checker.strip_comments(sample)
    assert "<Outlet" not in cleaned
    assert "<Ghost" not in cleaned
    assert "https://example.com/path" in cleaned, "a URL in a string must survive"


def test_a_string_containing_two_slashes_does_not_hide_a_real_missing_component():
    """The verifier's counter-example: `"a//b"` must not truncate the line.

    A comment stripper that treats any `//` as a comment start silently loses everything after it —
    including a genuinely unimported component. That is a false negative, which is worse than a
    noisy checker.
    """
    sample = 'const p = "a//b";\nexport default function A() { return <Ghost /> }\n'
    cleaned = _checker.strip_comments(sample)
    assert "a//b" in cleaned
    used = set(_checker.JSX_TAG.findall(cleaned)) - _checker.REACT_BUILTINS
    assert "Ghost" in used
    assert "Ghost" not in _checker.names_from(sample)


def test_no_undefined_jsx_components():
    """The Product Designer shipped two crashes from unimported components."""
    checker = Path(__file__).resolve().parent.parent / "tools" / "check-jsx-imports.py"
    result = subprocess.run(
        [sys.executable, str(checker)],
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout


def test_product_designer_imports_what_it_renders():
    text = _read("pages/internal/ProductDesigner.jsx")
    available = names_from(text)
    assert "createDoc" in available, "createDoc is used at line 94 but not imported"
    assert "MetricTiles" in available, "MetricTiles is rendered but not imported"


def test_socialpulse_imports_what_it_renders():
    text = _read("pages/internal/SocialPulse.jsx")
    assert "AssetThumb" in names_from(text)


def test_destructured_component_aliases_are_bindings_not_crashes():
    """`{ as: Tag = 'section' }` binds Tag; the guard must not call it undefined.

    The first version of tools/check-jsx-imports.py reported kit/Glass.jsx as a
    crash because <Tag> had no import - it is a destructured prop alias. Pin both
    halves: the alias counts as a binding, and a genuinely unbound component is
    still a problem.
    """
    assert "Tag" in names_from(_read("kit/Glass.jsx"))
    assert "Ghost" not in names_from("export default function A(){ return <Ghost /> }")
