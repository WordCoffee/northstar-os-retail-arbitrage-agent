#!/usr/bin/env python3
with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'r') as f:
    lines = f.readlines()

# Find _is_number and add idempotency_key after it
new_lines = []
added = False
for i in range(len(lines)):
    new_lines.append(lines[i])
    if not added and i > 60 and 'def _is_number' in lines[i-1]:
        # Add the idempotency_key function
        new_lines.append('\n')
        new_lines.append('def idempotency_key(asin: str, marketplace: str, task_type: str, bd_ref: str, run_id: str) -> str:\n')
        new_lines.append('    """Generate an idempotency key for a given ASIN/task/budget combination.\"\"\"\n')
        new_lines.append('    Used to prevent duplicate task planning across runs.\n')
        new_lines.append('    \"\"\"\n')
        new_lines.append('    import hashlib\n')
        new_lines.append('    key_data = f"{run_id}:{asin}:{task_type}:{bd_ref}"\n')
        new_lines.append('    return hashlib.sha256(key_data.encode()).hexdigest()[:16]\n')
        new_lines.append('\n')
        added = True

with open(r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\dataforseo_adapter.py', 'w') as f:
    f.writelines(new_lines)

if added:
    print('Added idempotency_key function')
else:
    print('Function not added - _is_number not found at expected location')