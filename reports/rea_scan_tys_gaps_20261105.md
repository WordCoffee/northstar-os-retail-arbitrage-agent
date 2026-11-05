# REA scan — what Ty is missing, and what to clone free

Date: 2026-11-05. Study instrument: **REA** (`morluto/rea`, MIT, v6.5.0, installed).
Targets: two open-source repos cloned shallow into a temp dir. Nothing was
installed into Northstar; nothing from either repo ships here.

## Why REA was not run as a tool

REA's own skill is explicit:

> "For ordinary analysis of a complete source repository, use normal repository
> tools and do not run REA readiness or provider commands."
> "Skip REA for ordinary source-repository architecture analysis."

Every candidate here is a complete open-source repo, so REA's method applies and
its MCP planner does not. This is the same conclusion `research/rea/capability-map.md`
recorded on 2026-10-24. The study below is therefore clone → read → cite
`file:line`, which is the discipline REA exists to enforce. No tool run is claimed
that did not happen.

## Targets

| repo | licence | why |
|---|---|---|
| `block/goose` | Apache-2.0 | the closest open-source analogue to Claude Code; MCP-native |
| `modelcontextprotocol/python-sdk` | MIT | the MCP client Ty does not have |

## Finding 1 — the MCP client is small and Ty has none

`python-sdk/src/mcp/client/session.py`:

| line | symbol |
|---|---|
| 388 | `class ClientSession` |
| 651 | `async def initialize()` |
| 1278 | `async def list_tools()` |
| 993 | `async def call_tool()` |
| 890 | `async def list_resources()` |
| 912 | `async def read_resource()` |

Transport config is a pydantic model: `python-sdk/src/mcp/client/stdio.py:94
class StdioServerParameters`.

That is the whole surface a client needs. Ty already *serves* MCP
(`tools/northstar_mcp_server.py`, 6 read-only tools) and cannot *consume* any
server, so every MCP server in the ecosystem — filesystem, git, databases, docs —
is unreachable. Six methods close it.

## Finding 2 — the piece that matters most is a malware check, not a feature

`goose/crates/goose/src/agents/extension_malware_check.rs`:

```
pub struct OsvChecker { client, endpoint }
pub async fn deny_if_malicious(&self, name: &str, ecosystem: &str, version: Option<&str>)
```

It queries **OSV.dev** and fails if any `MAL-*` advisory exists for the package
(`deny_if_malicious_impl`), with an `OSV_ENDPOINT` override for testing.

This is the missing half of "grab free things from GitHub and Hugging Face". The
repo's adoption gate (`provider_suite.py`) answers *may this lane use it* — licence,
lane, arming. It does not answer *is this package malicious*. Those are different
questions and Northstar only asks the first.

A `MAL-*` hit is a supply-chain compromise, and an agent with free roam that
installs packages needs that check before `pip install`, not after.

## Finding 3 — goose treats context management as its own crate

`goose/crates/goose-context-management/src/`: `summarize.rs`, `structured.rs`,
`provider.rs`, `format.rs`, `model.rs`, `templates.rs`.

Northstar's answer to the same problem is `headroom`, registered as Apache-2.0 and
**not installed**. Two independent implementations converging on "this is a
first-class subsystem" is a signal that it is not an afterthought.

## Finding 4 — goose's agent is a state machine

`goose/crates/goose/src/agents/state_machine/` plus `goose-acp-macros`. Northstar's
equivalent is `creative_flow.py`'s explicit step machine, which is the same idea in
miniature. No clone needed; recorded so the comparison is not assumed.

## What to clone, in order

| # | piece | from | licence | why first |
|---|---|---|---|---|
| 1 | **OSV pre-install check** | goose `extension_malware_check.rs` | Apache-2.0 | it is the safety precondition for everything else on this list |
| 2 | **MCP client** (6 methods + stdio params) | python-sdk | MIT | unlocks the whole MCP ecosystem for free |
| 3 | **context compaction** | headroom (already registered) | Apache-2.0 | long sessions are what break agents first |
| 4 | web research (trafilatura + ddgs) | separate | Apache-2.0 / MIT | the Perplexity gap, but needs the Amazon refusal first |

Item 1 is in-repo work with **no new dependency** — OSV is a public HTTP API — so
it needs no registry entry and no operator decision. It is the only item on this
list that can ship today.

## What was deliberately not cloned

- goose's Rust crates: the patterns port, the code does not. Northstar is Python.
- goose's provider/ACP layer: a second harness surface, same verdict as the
  AgentConnect rejection.
- Any model weights: nothing here needs one.

## Caveats

- Two repos read, not a survey. Absence of a pattern in these two is not evidence
  it does not exist elsewhere.
- Versions are whatever `--depth 1` gave on 2026-11-05; line numbers will drift.
- The MCP client was read, not exercised. Connecting to a real server is the test.
