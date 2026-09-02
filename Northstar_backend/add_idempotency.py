#!/usr/bin/env python3
import sys

with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'r') as f:
    content = f.read()

# Add idempotency_key function after _is_number
old = """def _is_number(value) -> bool:
    \"\"\"Check if a value is a number (int or float), not a boolean.\"\"\"
    return isinstance(value, (int, float)) and not isinstance(value, bool)


DATAFORSEO_ACCEPTED_STATE"""

new = """def _is_number(value) -> bool:
    \"\"\"Check if a value is a number (int or float), not a boolean.\"\"\"
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def idempotency_key(asin: str, marketplace: str, task_type: str, bd_ref: str, run_id: str) -> str:
    \"\"\"Generate an idempotency key for a given ASIN/task/budget combination.

    Used to prevent duplicate task planning across runs.
    \"\"\"
    import hashlib
    key_data = f"{run_id}:{asin}:{task_type}:{bd_ref}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


DATAFORSEO_ACCEPTED_STATE"""

if old in content:
    content = content.replace(old, new)
    with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'w') as f:
        f.write(content)
    print('Added idempotency_key function')
else:
    print('Old string not found')