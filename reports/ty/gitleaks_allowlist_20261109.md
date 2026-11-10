# gitleaks allowlist — what was allowed, and why

Commit: the one that touched `.gitleaks.toml` with this file (see `git log -- .gitleaks.toml`).

Two findings were allowlisted, both in test modules, both verified by reading the line's *shape* (never
its value) and the code around it:

| file | line | rule | why it is a false positive |
|---|---|---|---|
| `Northstar_backend/test_chrome_uia.py` | 93 | `generic-api-key` | the line builds a fake UI Automation element — `{"role": "TextControl", "name": "api_key"}` — standing in for an accessibility tree in a unit test. The match is a field *label*, not a value, and nothing reaches a provider. |
| `Northstar_backend/test_vision_computer.py` | 74 | `generic-api-key` | the line writes a fake secret file into `tmp_path` so the vision pipeline can be tested for refusing/redacting it. The value exists in order to be refused. |

**What was NOT allowlisted**, deliberately:

- `FirstNorthstarautomationchat.md` lines 1143, 1148, 1291, 1296 and `autothink-ui-chat-export.md`
  line 7852 — those are real credentials in tracked files. They are `DIR-1a/b/c` in `needs_you.md`
  and must be rotated and purged, not hidden.
- `.env` findings (43) — real values, but the files are untracked. Not a leak; no rotation needed for
  this, and allowlisting them would hide a genuine prompt to keep them out of git.
- `venv-crew/`, `site-packages/` (44) — third-party library test fixtures, not ours to allow or fix.
- `.playwright-mcp/` captures (part of the 69 fixtures) — browser logs containing third-party page
  tokens; untracked.

The scan that produced the classification ran with `--redact` and the reader dropped `Secret` and
`Match` on load, so no value is in `reports/ty/gitleaks_classified.md`, in this file, or in the JSON
the tool wrote.
