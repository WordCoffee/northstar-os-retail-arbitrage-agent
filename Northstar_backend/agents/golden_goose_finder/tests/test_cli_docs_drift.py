"""Phase G — FIXES_50 #50: --docs drift CI assertion (offline).

Regenerates the CLI reference from the live source (CLI_DOCS_ARGS in
agents/golden_goose_finder/main.py) and requires it to match the committed
docs/golden-goose-cli-reference.md. Any drift fails the suite so the flag list
and the committed reference can NEVER silently diverge.

To refresh after an intentional flag change:
    python -m agents.golden_goose_finder.main --docs > docs/golden-goose-cli-reference.md
and commit both files together.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder.main import _docs_reference  # noqa: E402

_REFERENCE = _BACKEND.parent / "docs" / "golden-goose-cli-reference.md"


def test_cli_docs_does_not_drift() -> None:
    current = _docs_reference()
    committed = _REFERENCE.read_text(encoding="utf-8")
    assert committed == current, (
        "CLI reference drifted. Re-generate and commit both:\n"
        "  python -m agents.golden_goose_finder.main --docs "
        "> docs/golden-goose-cli-reference.md\n"
    )


def test_reference_covers_expected_flags() -> None:
    text = _REFERENCE.read_text(encoding="utf-8")
    for flag in ("--dry-run", "--scout-csv", "--rollback-to", "--docs"):
        assert flag in text, "reference missing flag %s" % flag