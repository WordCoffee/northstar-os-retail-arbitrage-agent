# Screenshot probe — PASS (2026-10-25)

## Probe command
- url: http://127.0.0.1:8101/ui/
- require_isolated: false
- max_steps: 8
- task:
  ```
  STEPS:
  screenshot reports/northstar_acceptance_20261025/screenshots/probe-desktop.png
  screenshot reports/northstar_acceptance_20261025/screenshots/probe-mobile.png @390x844
  ```

## Journal evidence
- Run journal: `2026-10-25T02-20-57-283Z_steps_screenshot_reports_northstar_accep_mvn7b1oi.jsonl`
- Step 0: navigate → http://127.0.0.1:8101/ui/) — page_status READ
- Step 1: screenshot (pw_tool "screenshot", ok: true, duration 687ms) → probe-desktop.png
- Step 2: screenshot (pw_tool "screenshot", ok: true) → probe-mobile.png @390x844
  - viewport: {width: 390, height: 844}
  - previous_viewport: {width: 2100, height: 1216}
  - restored: true
  - restore_error: null
  - full_page: true

## File verification
| File | Exists | Size | Dimensions |
|---|---|---|---|
| probe-desktop.png | yes | 511,943 bytes | 2625 × 1520 |
| probe-mobile.png | yes | 94,221 bytes | 488 × 1055 |

Both files are non-empty PNGs. Mobile image is 390×844 CSS pixels at 1.25 DPR (488×1055).

## Page content (not a login wall)
- URL: http://127.0.0.1:8101/ui/)
- Title: "NorthstarOS — Retail Arbitrage Suite"
- Text: "NorthstarOS · Simple · Operator · Deep field · vista 7 of 7 · Auto · Create · Grow · Research · Operate · AutothinK 🔒 · Dictate · Send"
- This is the authenticated Simple Mode home view (vista annotation, focus chips, Dictate button, telemetry chip all visible).

## Viewport restore
- Original viewport (2100×1216) was restored after mobile capture (restored: true, restore_error: null).

## Verdict: PASS
Both screenshot steps executed, both PNG files exist and are non-empty, dimensions recorded, mobile viewport (390×844) reported and restored, captured page is Simple Mode (not login wall).