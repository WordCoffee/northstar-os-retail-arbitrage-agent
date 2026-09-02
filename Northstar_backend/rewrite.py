#!/usr/bin/env python3
import sys

with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'r') as f:
    content = f.read()

# Replace is_first_approved_run
content = content.replace(
    'def is_first_approved_run(run_id: str) -> bool:\n    """Check whether a run ID is the first approved run."""\n    return run_id in _GLOBAL_APPROVED_RUN_SET\n\n',
    'def is_first_approved_run(run_id: str) -> bool:\n    """Check whether a run ID is the first approved run."""\n    return run_id in _GLOBAL_APPROVED_RUNS\n\n'
)

# Replace effective_budget_cents
content = content.replace(
    'def effective_budget_cents(run_id: str) -> int:\n    """Return the effective budget in cents for a given run ID.\n    # Default budget: 1 for first approved run, 100 for subsequent runs\n    if run_id in _GLOBAL_APPROVED_RUN_SET:\n        return 1  # simplified: first run gets 1 cent\n    return 100  # subsequent runs get 100 cent default',
    'def effective_budget_cents(run_id: str) -> int:\n    """Return the effective budget in cents for a given run ID.\n\n    First approved run gets 1 cent budget.\n    All subsequent approved runs get 100 cent default budget.\n    \"\"\"\n    if run_id in _GLOBAL_APPROVED_RUNS:\n        run_order = list(_GLOBAL_APPROVED_RUNS).index(run_id)\n        if run_order == 0:\n            return 1\n    return 100'
)

# Add _GLOBAL_APPROVED_RUNS set population in create_approval
content = content.replace(
    'def create_approval(run_id: str, operator_token: str) -> Dict:\n    \"\"\"Create/authorize a run approval token.\n\n    The operator_token must equal the run_id exactly; otherwise GuardError is raised.\n    \"\"\"\n    if run_id != operator_token:\n        raise GuardError("approval token must equal run_id")\n    return {"run_status": "authorized"}',
    'def create_approval(run_id: str, operator_token: str) -> Dict:\n    \"\"\"Create/authorize a run approval token.\n\n    The operator_token must equal the run_id exactly; otherwise GuardError is raised.\n    The run_id is added to the global approved runs set.\n    \"\"\"\n    if run_id != operator_token:\n        raise GuardError("approval token must equal run_id")\n    _GLOBAL_APPROVED_RUNS.add(run_id)\n    return {"run_status": "authorized"}'
)

with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'w') as f:
    f.write(content)

print('Done rewriting')