from pathlib import Path

path = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\reports\ty\needs_you.md")
text = path.read_text(encoding="utf-8")

anchor = "## DIR-1. Rotate three credentials that are already committed"
assert anchor in text, "DIR-1 heading not found"

replacement = '''## DIR-1a. Rotate the Scavio API key (committed)

`FirstNorthstarautomationchat.md` **line 1143** and **line 1291** contain a Scavio API key — the same
credential twice. It is in git history, not just the working tree, so editing the file is not enough.

**Rotate it at Scavio, then say so** and the history purge becomes a Director job (the value must be
removed from every commit that carries it). gitleaks rule `generic-api-key`.

## DIR-1b. Rotate the Bright Data API key (committed)

`FirstNorthstarautomationchat.md` **line 1148** and **line 1296** — the same Bright Data key twice.
Same action: rotate at the provider, then I purge history. Rule `generic-api-key`.

## DIR-1c. Rotate the GitHub personal access token (committed)

`autothink-ui-chat-export.md` **line 7852** carries a GitHub PAT, which is the highest-risk of the
three: a PAT can push code. **Revoke it in GitHub → Settings → Developer settings → Tokens**, then I
purge the line from history. Rule `github-pat`.

## DIR-1. The measure that made these visible

`reports/ty/gitleaks_classified.md` classifies **all 312 gitleaks findings** in this working tree:

| class | findings |
|---|---|
| real, **committed** (the three above) | **5** |
| real, local only (`.env` files, untracked) | 43 |
| fixtures, test modules and captured logs | 69 |
| vendored third-party code (`venv-crew`, `site-packages`) | 44 |
| untracked review (exports, worktree copies) | 151 |

The `.env` findings are credentials too, but they are not in history, so no rotation is needed for
the leak; they are the live keys and stay where they are.

**Promotion is still blocked by two findings that are not real** — `test_chrome_uia.py:93` and
`test_vision_computer.py:74`, both synthetic values in tests that build fake accessibility trees and
fake secret files. Those are allowlisted in `.gitleaks.toml` with a logged commit
(`reports/ty/gitleaks_allowlist_20261109.md`); the three above are not, and must not be.

'''
text = text.replace(anchor, replacement, 1)

# the superseded note stays attached to DIR-1's history
old_note = '''> **Now also blocking promotion (2026-11-09).**'''
if old_note in text:
    text = text.replace(old_note, "> **History note.**")

path.write_text(text, encoding="utf-8")
print("DIR-1 split into one entry per real secret")
