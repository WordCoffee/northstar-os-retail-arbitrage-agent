# opencode.json DENY rules added (2026-10-27)

## Deny rules (additive only)
- bash: `git push*`, `git push *`, `rm -rf*`, `rm -rf *`
- read: `*.env`, `*.env.*`, `*secrets.masterkey*`, `*secrets.vault*`, `*.masterkey*`, `*.key`, `*.pem`
- edit (Tier-2 paths):
  - AGENTS.md
  - docs/OPERATING_CONSTITUTION.md
  - shared/master-brain/brain_policy.json
  - shared/usage-caps.json
  - watchdog.py
  - steward/watchdog.py
  - steward/charter.json
  - shared/steward/charter.json
  - shared/steward/ledger.jsonl
  - shared/steward/ledger_head_hash.txt
  - shared/steward/vault_store/**
  - steward/vault_broker.py
  - Northstar_backend/foundation/secrets.py
  - steward/rules_engine.py
  - steward/folder_grants.py
  - steward/orchestrator.py
  - steward/supervisor.py
  - steward/needs_you_queue.py
  - 00_STATE.json
  - ROLLBACK.md
  - ROLLBACK_DRILL.md
  - tools/rollback.ps1
  - scripts/rollback_drill.ps1
  - reports/operator_authorized_chromeconnect_policy_*.md
  - docs/WRITE_PATH_AUTHORIZATION.md
  - *chromecontrol_policy_owner.json*
  - steward/**

## Windows ACL commands (run manually; do NOT run by agent)
```
icacls "AGENTS.md" /deny %USERNAME%:(W)
icacls "docs\OPERATING_CONSTITUTION.md" /deny %USERNAME%:(W)
icacls "shared\master-brain\brain_policy.json" /deny %USERNAME%:(W)
icacls "shared\usage-caps.json" /deny %USERNAME%:(W)
icacls "watchdog.py" /deny %USERNAME%:(W)
icacls "steward\watchdog.py" /deny %USERNAME%:(W)
icacls "steward\charter.json" /deny %USERNAME%:(W)
icacls "shared\steward\charter.json" /deny %USERNAME%:(W)
icacls "shared\steward\ledger.jsonl" /deny %USERNAME%:(W)
icacls "shared\steward\ledger_head_hash.txt" /deny %USERNAME%:(W)
icacls "steward\vault_broker.py" /deny %USERNAME%:(W)
icacls "Northstar_backend\foundation\secrets.py" /deny %USERNAME%:(W)
icacls "steward\rules_engine.py" /deny %USERNAME%:(W)
icacls "00_STATE.json" /deny %USERNAME%:(W)
icacls "ROLLBACK.md" /deny %USERNAME%:(W)
icacls "ROLLBACK_DRILL.md" /deny %USERNAME%:(W)
icacls "tools\rollback.ps1" /deny %USERNAME%:(W)
icacls "scripts\rollback_drill.ps1" /deny %USERNAME%:(W)
icacls "shared\steward\vault_store" /deny %USERNAME%:(W) /T
icacls "C:\Users\T2Hol\OneDrive\Documents\Default Project\config\chromecontrol_policy_owner.json" /deny %USERNAME%:(W)
```