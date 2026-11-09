# ui-foundation — review pack, 20261109

This slice of `staging-candidate/20261109-0158` touches 19 commit(s) ahead of `main` and changes **20 path(s)**, 20 of which render. It is refused for auto-promotion (`slice_visual`): a person has to look at these images first.

- candidate `staging-candidate/20261109-0158` @ `433c5d87d5ef`
- target `main` @ `ecef24a75d92`

## Gates

| gate | result | evidence |
|---|---|---|
| suite | FAIL | candidate staging-candidate/20261109-0158 = 433c5d87d5ef summary: 32 failed, 7189 passed, 125 skipped, 2 xfailed, 17 warning, 125 subtests |
| verifier | PASS | d15_verification.md: 17 agree, 2 FAILED, 1 BLOCKED reproduced by: not recorded (--verifier not given) |
| slice | FAIL | slice ui-foundation: 20 path(s), 0 image(s) rendering paths: 20 |

Refused by: `suite`, `slice`

## Images (10 of 5–10)

Slice images first, then committed evidence as context. `before` shows the same path on the target branch; a blank before means the file is new here.

| after (this slice) | before | where |
|---|---|---|
| `northstar-os-ui/screenshots/1-command-center.png`<br>![after](../../../northstar-os-ui/screenshots/1-command-center.png) | _new here_ | context |
| `northstar-os-ui/screenshots/10-customer-workspace.png`<br>![after](../../../northstar-os-ui/screenshots/10-customer-workspace.png) | _new here_ | context |
| `northstar-os-ui/screenshots/10b-customer-workspace-services.png`<br>![after](../../../northstar-os-ui/screenshots/10b-customer-workspace-services.png) | _new here_ | context |
| `northstar-os-ui/screenshots/11-beta-ops.png`<br>![after](../../../northstar-os-ui/screenshots/11-beta-ops.png) | _new here_ | context |
| `northstar-os-ui/screenshots/12-mobile-tools-sheet.png`<br>![after](../../../northstar-os-ui/screenshots/12-mobile-tools-sheet.png) | _new here_ | context |
| `northstar-os-ui/screenshots/13-listing-guardian.png`<br>![after](../../../northstar-os-ui/screenshots/13-listing-guardian.png) | _new here_ | context |
| `northstar-os-ui/screenshots/14-keyword-tracker.png`<br>![after](../../../northstar-os-ui/screenshots/14-keyword-tracker.png) | _new here_ | context |
| `northstar-os-ui/screenshots/15-competitor-monitor.png`<br>![after](../../../northstar-os-ui/screenshots/15-competitor-monitor.png) | _new here_ | context |
| `northstar-os-ui/screenshots/16-socialpulse.png`<br>![after](../../../northstar-os-ui/screenshots/16-socialpulse.png) | _new here_ | context |
| `northstar-os-ui/screenshots/17-creative-studio.png`<br>![after](../../../northstar-os-ui/screenshots/17-creative-studio.png) | _new here_ | context |

## Scorecard delta

`ty/scorecards.json` is **absent on `main`** — every score is new.

at_bar **2**: hub, prospector

| service | score | at bar |
|---|---|---|
| hub | 100 | yes |
| prospector | 100 | yes |
| ledger | 86.2 | no |
| auctioneer | 86.2 | no |
| autothink | 86.2 | no |
| thewatch | 86.2 | no |
| rankledger | 86.2 | no |
| rivalboard | 86.2 | no |
| account | 86.2 | no |
| foundation | 86.2 | no |
| jobs | 86.2 | no |
| keywords | 86.2 | no |

## Changed paths (20)

```
northstar-os-ui/src/foundation/HelpTour.jsx
northstar-os-ui/src/foundation/api.js
northstar-os-ui/src/foundation/components/CommandPalette.jsx
northstar-os-ui/src/foundation/components/EnvBadge.jsx
northstar-os-ui/src/foundation/components/Notifications.jsx
northstar-os-ui/src/foundation/components/OrgSelector.jsx
northstar-os-ui/src/foundation/components/PinnedDrawer.jsx
northstar-os-ui/src/foundation/components/PreviewBanner.jsx
northstar-os-ui/src/foundation/components/RouteGuard.jsx
northstar-os-ui/src/foundation/components/StatusPrimitives.jsx
northstar-os-ui/src/foundation/dev.js
northstar-os-ui/src/foundation/flags.js
northstar-os-ui/src/foundation/foundation.css
northstar-os-ui/src/foundation/pages/BetaOps.jsx
northstar-os-ui/src/foundation/pages/BetaSignup.jsx
northstar-os-ui/src/foundation/pages/BetaTester.jsx
northstar-os-ui/src/foundation/pages/FoundationStatus.jsx
northstar-os-ui/src/foundation/pages/Jobs.jsx
northstar-os-ui/src/foundation/pages/Keywords.jsx
northstar-os-ui/src/foundation/session.jsx
```

## Commands

Promote just this slice:

```
python tools/promote_staging.py --source staging-candidate/20261109-0158 --slice ui-foundation --promote --candidate staging-candidate/20261109-0158 --approve-visual "<what you looked at and accepted>"
```

Revert it:

```
python tools/promote_staging.py --slice ui-foundation --revert promote/20261109-ui-foundation-433c5d87
```
