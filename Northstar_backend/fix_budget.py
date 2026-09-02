#!/usr/bin/env python3
import sys

with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'r') as f:
    content = f.read()

# Find and replace the two functions
old1 = """def is_first_approved_run(run_id: str) -> bool:
    \"\"\"Check whether a run ID is the first approved run.\"\"\"
    return run_id in _GLOBAL_APPROVED_RUN_SET


def effective_budget_cents(run_id: str) -> int:
    \"\"\"Return the effective budget in cents for a given run ID.

    Default budget: 1 for first approved run, 100 for subsequent runs
    \"\"\"
    if run_id in _GLOBAL_APPROVED_RUN_SET:
        return 1  # simplified: first run gets 1 cent"""

new1 = """def is_first_approved_run(run_id: str) -> bool:
    \"\"\"Check whether a run ID is the first approved run.\"\"\"
    return run_id in _GLOBAL_APPROVED_RUNS


def effective_budget_cents(run_id: str) -> int:
    \"\"\"Return the effective budget in cents for a given run ID.

    First approved run gets 1 cent budget.
    All subsequent approved runs get 100 cent default budget.
    \"\"\"
    if run_id in _GLOBAL_APPROVED_RUNS:
        run_order = list(_GLOBAL_APPROVED_RUNS).index(run_id)
        if run_order == 0:
            return 1
    return 100"""

if old1 in content:
    content = content.replace(old1, new1)
    print('Replaced first function pair')
else:
    print('First old string NOT found')

old2 = """_GLOBAL_APPROVED_RUNS: set = set()"""

new2 = """_GLOBAL_APPROVED_RUNS: set = set()"""

# The create_approval function needs to add to the set
old3 = """def create_approval(run_id: str, operator_token: str) -> Dict:
    \"\"\"Create/authorize a run approval token.

    The operator_token must equal the run_id exactly; otherwise GuardError is raised.
    \"\"\"
    if run_id != operator_token:
        raise GuardError("approval token must equal run_id")
    return {"run_status": "authorized"}"""

new3 = """def create_approval(run_id: str, operator_token: str) -> Dict:
    \"\"\"Create/authorize a run approval token.

    The operator_token must equal the run_id exactly; otherwise GuardError is raised.
    The run_id is added to the global approved runs set.
    \"\"\"
    if run_id != operator_token:
        raise GuardError("approval token must equal run_id")
    _GLOBAL_APPROVED_RUNS.add(run_id)
    return {"run_status": "authorized"}"""

changed = 0
if old3 in content:
    content = content.replace(old3, new3)
    changed += 1
    print('Replaced create_approval')

if changed > 0:
    with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'w') as f:
        f.write(content)
    print('File written')
else:
    print('No changes made - old3 not found')