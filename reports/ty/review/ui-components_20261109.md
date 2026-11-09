# ui-components — review pack, 20261109

This slice of `staging-candidate/20261109-0158` touches 32 commit(s) ahead of `main` and changes **33 path(s)**, 33 of which render. It is refused for auto-promotion (`slice_visual`): a person has to look at these images first.

- candidate `staging-candidate/20261109-0158` @ `433c5d87d5ef`
- target `main` @ `ecef24a75d92`

## Gates

| gate | result | evidence |
|---|---|---|
| suite | FAIL | candidate staging-candidate/20261109-0158 = 433c5d87d5ef summary: 32 failed, 7189 passed, 125 skipped, 2 xfailed, 17 warning, 125 subtests |
| verifier | PASS | d15_verification.md: 17 agree, 2 FAILED, 1 BLOCKED reproduced by: not recorded (--verifier not given) |
| slice | FAIL | slice ui-components: 33 path(s), 0 image(s) rendering paths: 33 |

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

## Changed paths (33)

```
northstar-os-ui/src/components/Announcer.jsx
northstar-os-ui/src/components/CommandPalette.jsx
northstar-os-ui/src/components/DensityToggle.jsx
northstar-os-ui/src/components/Dock.jsx
northstar-os-ui/src/components/FirstRunGuide.jsx
northstar-os-ui/src/components/Header.jsx
northstar-os-ui/src/components/Icon.jsx
northstar-os-ui/src/components/Markdown.jsx
northstar-os-ui/src/components/MarkdownEditor.jsx
northstar-os-ui/src/components/MobileBottomNav.jsx
northstar-os-ui/src/components/ReasoningModelSelector.jsx
northstar-os-ui/src/components/Reorderable.jsx
northstar-os-ui/src/components/RightRail.jsx
northstar-os-ui/src/components/RoomTabs.jsx
northstar-os-ui/src/components/Shared.jsx
northstar-os-ui/src/components/ShellModeToggle.jsx
northstar-os-ui/src/components/Sidebar.jsx
northstar-os-ui/src/components/Skeletons.jsx
northstar-os-ui/src/components/SuiteRail.jsx
northstar-os-ui/src/components/ToastCenter.jsx
northstar-os-ui/src/components/ToastContext.jsx
northstar-os-ui/src/components/TopNav.jsx
northstar-os-ui/src/components/VirtualList.jsx
northstar-os-ui/src/components/VisionRing.jsx
northstar-os-ui/src/components/baroque/ActionTrigger.jsx
northstar-os-ui/src/components/baroque/BaroqueBackdrop.jsx
northstar-os-ui/src/components/baroque/ControlFrame.jsx
northstar-os-ui/src/components/baroque/NotificationModal.jsx
northstar-os-ui/src/components/baroque/StatusBanner.jsx
northstar-os-ui/src/components/baroque/baroque.js
northstar-os-ui/src/components/markdown.css
northstar-os-ui/src/components/skeletons.css
northstar-os-ui/src/components/toast.css
```

## Commands

Promote just this slice:

```
python tools/promote_staging.py --source staging-candidate/20261109-0158 --slice ui-components --promote --candidate staging-candidate/20261109-0158 --approve-visual "<what you looked at and accepted>"
```

Revert it:

```
python tools/promote_staging.py --slice ui-components --revert promote/20261109-ui-components-433c5d87
```
