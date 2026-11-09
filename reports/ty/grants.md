# Capability grants

Every entry is a dedicated one-purpose `GRANT:` commit, with a rollback tag made first.
The supervisor stays ON and is never bypassed.

| date | grant | path or capability | rollback tag | commit |
|---|---|---|---|---|
| 2026-11-09 | **Dev-only use of `ultralytics` (AGPL-3.0)** for the OmniParser-class grounding benchmark, local lane only, never shipped, never exposed over a network service | `state/vendor/grounding-bench/` (dev bench), imported only by `tools/vision/grounding.py` behind the `omniparser` backend | `rollback/pre-grant-ultralytics-20261109` | GRANT: ultralytics dev-only for grounding benchmark (2026-11-09) |

**Scope of this grant.** `ultralytics` (YOLO) is AGPL-3.0; our provider suite refuses
`agpl_network_copyleft_unreviewed` for anything that could be served to a customer. This grant is
narrow on purpose:

- **development only** — the local bench, not the product, not the cloud lane;
- **never offered over a network** — no MCP tool, no API route, no service that a third party can
  call;
- **one purpose** — measuring icon detection for the 40-screen grounding set, so the choice
  between UIA/DOM and pixels is made on evidence;
- **reversible** — `rollback/pre-grant-ultralytics-20261109` is the tag, and removing the package
  plus the `omniparser` backend restores the prior state.

If the benchmark lands in the product rather than in a report, this grant does not cover it and
the AGPL refusal stands.

