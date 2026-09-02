#!/usr/bin/env python3
import sys

with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'r') as f:
    content = f.read()

# Fix 1: effective_budget_cents should use _GLOBAL_APPROVED_RUNS, not _GLOBAL_APPROVED_RUN_SET
content = content.replace(
    'if run_id in _GLOBAL_APPROVED_RUN_SET:\n        return 1  # simplified: first run gets 1 cent\n    return 100  # subsequent runs get 100 cent default',
    'if run_id in _GLOBAL_APPROVED_RUNS:\n        run_order = list(_GLOBAL_APPROVED_RUNS).index(run_id)\n        if run_order == 0:\n            return 1\n    return 100'
)

# Fix 2: Remove the duplicate is_first_approved_run at line 540 that returns False
# The correct one is at line 497-499: return run_id in _GLOBAL_APPROVED_RUNS
# Need to remove the duplicate at line 540-542
old_dup = '''\ndef is_first_approved_run(run_id: str) -> bool:
    \"\"\"Check whether a run ID is the first approved run.\"\"\"
    return False


\ndef effective_budget_cents'''

new_dup = '''\ndef effective_budget_cents'''

if old_dup in content:
    content = content.replace(old_dup, new_dup)
    print('Removed duplicate is_first_approved_run')
else:
    print('Duplicate not found - checking...')
    # Check if the pattern exists
    if '\ndef is_first_approved_run(run_id: str) -> bool:\n    \"\"\"Check whether a run ID is the first approved run.\"\"\"\n    return False\n\n\ndef effective_budget_cents' in content:
        print('Pattern found with different whitespace')
    else:
        print('Pattern not found')

with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'w') as f:
    f.write(content)

print('Done')