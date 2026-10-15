# Advisories triage - running doc (started 2026-10-14)

Sources: `osv-scanner scan source -r .` (full local run, 2026-10-14, exit 1 = findings) and `grype dir:.` (same day, corroborates the npm set). Raw evidence: `reports/phase3_unit2_scanners_20261014.md`. Re-run anytime (tools at `%LOCALAPPDATA%\osv-scanner\2.7.0\` and `%LOCALAPPDATA%\grype\0.120.1\`):
```
osv-scanner scan source -r .
grype dir:.
```
Status legend: OPEN (untriaged) / WONTFIX / FIXED. **Nothing below has been fixed or patched** - listing only.

## Lane A - UI (`northstar-os-ui/package-lock.json`) - owner: UI lane
| Advisory | Score | Package | Installed | Fixed in | Lockfile |
|---|---|---|---|---|---|
| GHSA-67mh-4wv8-2f99 | 5.3 | esbuild (dev) | 0.21.5 | 0.25.0 | `northstar-os-ui/package-lock.json` |
| GHSA-337j-9hxr-rhxg | 6.1 | react-router | 6.30.6 | 7.18.0 | `northstar-os-ui/package-lock.json` |
| GHSA-wrjc-x8rr-h8h6 | 5.1 | react-router | 6.30.6 | 7.18.0 | `northstar-os-ui/package-lock.json` |
| GHSA-68fv-2mgg-jv7q | 8.7 | source-map-js (dev) | 1.2.1 | 1.2.2 | `northstar-os-ui/package-lock.json` |
| GHSA-4w7w-66w2-5vf9 | 6.3 | vite (dev) | 5.4.21 | 6.4.2 | `northstar-os-ui/package-lock.json` |
| GHSA-fx2h-pf6j-xcff | 8.2 | vite (dev) | 5.4.21 | 6.4.3 | `northstar-os-ui/package-lock.json` |
| GHSA-v6wh-96g9-6wx3 | 5.5 | vite (dev) | 5.4.21 | 6.4.3 | `northstar-os-ui/package-lock.json` |

## Lane B - legacy dirs + root lockfiles - owner: Phase-7 / legacy cleanup
| Advisory | Score | Package | Installed | Fixed in | Lockfile |
|---|---|---|---|---|---|
| GHSA-5p39-cfhj-2xmp |  |  |  | - | `` |
| GHSA-82r6-8w77-94w6 |  |  |  | - | `` |
| GHSA-65pc-fj4g-8rjx |  |  |  | - | `` |
| GHSA-jqcg-44mw-7w3h | 9.1 | proxy-addr | 2.0.7 | 2.0.8 | `motivation-quotes/package-lock.json` |
| GHSA-4mjr-xmp4-gh2g | 6.3 | qs | 6.15.3 | 6.16.0 | `motivation-quotes/package-lock.json` |
| GHSA-x5fp-wj9c-mxmx | 6.3 | qs | 6.15.3 | 6.16.0 | `motivation-quotes/package-lock.json` |
| GHSA-3pq3-5fj3-cg6v | 7.0 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-44g4-m2mj-wpvx | 6.9 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-4hqw-qxg8-jxx2 | 6.9 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-542g-h47m-68v8 | 8.2 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-9fr6-4gfg-395g | 6.9 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-c29m-xwm3-cm6r | 8.2 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-j8rh-479h-cp32 | 6.9 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-m8m8-qj5v-23w3 | 7.6 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-mghh-pgcx-3jjj | 8.2 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-r4gj-5m52-g5wh | 7.0 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-vh66-26gq-q6x8 | 6.9 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-x97p-jq2g-jp4f | 8.3 | axios | 1.18.1 | 1.20.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-jqcg-44mw-7w3h | 9.1 | proxy-addr | 2.0.7 | 2.0.8 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-4mjr-xmp4-gh2g | 6.3 | qs | 6.15.3 | 6.16.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-x5fp-wj9c-mxmx | 6.3 | qs | 6.15.3 | 6.16.0 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-w5hq-g745-h8pq | 7.5 | uuid | 8.3.2 | 11.1.1 | `northstar-os-retail-arbitrage-agent/package-lock.json` |
| GHSA-vfj7-8cjw-p6xm | 8.7 | braces | 3.0.3 | -- | `package-lock.json` |
| GHSA-jqcg-44mw-7w3h | 9.1 | proxy-addr | 2.0.7 | 2.0.8 | `package-lock.json` |
| GHSA-2v37-7h3g-55p8 | 8.2 | nanoid (dev) | 3.3.16 | 3.3.18 | `quick-draw-app/package-lock.json` |
| GHSA-fxqj-rqcc-2cmp | 6.3 | postcss (dev) | 8.5.22 | 8.5.23 | `quick-draw-app/package-lock.json` |
| GHSA-68fv-2mgg-jv7q | 8.7 | source-map-js (dev) | 1.2.1 | 1.2.2 | `quick-draw-app/package-lock.json` |
| GHSA-hp3w-g68c-fv3c | 6.9 | sprintf-js | 1.0.3 | -- | `quick-draw-app/package-lock.json` |

## The pip-audit vs osv nuance (OPEN)
`osv-scanner` flags `anyio`/`idna` in `uv.lock` while `pip-audit` (same day) reported "no known vulnerabilities" - likely advisory-record/fix-availability filtering differences between the tools. Triage item: reconcile both tools' criteria on the Python lock before the Phase-7 freeze.

## Notes
- grype's repo-wide run corroborated the same npm families (axios/braces/qs/uuid/react-router/sprintf-js); its `northstar/` scan was clean.
- Fix versions shown where an advisory provides one; several entries have no fix (-).
- Per standing rules: no live provider calls, no Amazon, patches require their own change window + gates.
