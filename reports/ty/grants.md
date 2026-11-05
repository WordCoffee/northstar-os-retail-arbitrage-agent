# Grants

Capability grants: one dedicated commit each, message `GRANT: <what and why>`, rollback tag
immediately before, guardrail baseline re-recorded in the same commit, supervisor still running after.

| # | Date | What | Why | Rollback tag | Commit | Supervisor after |
|---|---|---|---|---|---|---|
| 01 | 2026-11-05 | Register three tools in `shared/provider-suite.json`: `mcp_client` (MIT), `web_research_trafilatura` (Apache-2.0), `web_research_ddgs` (MIT). New `tools/mcp_client.py`, `tools/web_research.py`, `tests/fixtures/mcp_echo_server.py`, two test modules, three `provenance.csv` rows. | The file is outside the loop's commit allowlist by design. Without the entries the adoption gate refuses every one of them with `unknown_tool`, so Ty could not consume an MCP server and could not research the web — the first two Phase B blockers, in dependency order (research first). | `autonomy-grant-01-pre` | see git log `GRANT:` | required: `scripts/continuous_loop.py --ready` run after this commit, fingerprint recorded below |

## Grant 01 details

**Scope (exact files):**

```
shared/provider-suite.json          (3 new tool entries; no existing entry changed)
tools/mcp_client.py                 (new)
tools/web_research.py               (new)
tests/fixtures/mcp_echo_server.py   (new, probe fixture)
Northstar_backend/test_mcp_client.py      (new, 4 tests)
Northstar_backend/test_web_research.py    (new, 16 tests)
provenance.csv                      (3 appended rows)
reports/ty/grants.md                (this file)
```

**What it does NOT do:** it does not touch the Chrome Connect host policy, the hardcoded
Amazon blocklist, the profile lease, the capability grants, the budget caps or the audit-hash chain.
`tools/web_research.py` *adds* a second enforcement point for the Amazon rule rather than
weakening the first: the blocklist is hardcoded, evaluated before any request leaves the
machine, and cannot be overridden by a CLI flag.

**Evidence at grant time:**

- `provider_suite.py --check mcp_client --provider local` -> `available on local (MIT, free_local)`
- `provider_suite.py --check web_research_trafilatura` -> `available on local (Apache-2.0)`
- `provider_suite.py --check web_research_ddgs` -> `available on local (MIT)`
- `pytest test_web_research.py test_mcp_client.py` -> **20 passed**
- `mcp_client.py --arg tests/fixtures/mcp_echo_server.py --list --call add` -> 2 tools, `sum: 5`
- `web_research.py --fetch https://www.amazon.com/dp/B01FYY3M38` -> `REFUSED: amazon_refused`, exit 1
