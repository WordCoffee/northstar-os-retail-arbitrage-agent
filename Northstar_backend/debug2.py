#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend')
import dataforseo_adapter as df

# Check the global set
print('_GLOBAL_APPROVED_RUNS:', df._GLOBAL_APPROVED_RUNS)

# Create approval
rec = df.create_approval('first', 'first')
print('After create_approval _GLOBAL_APPROVED_RUNS:', df._GLOBAL_APPROVED_RUNS)

# Check is_first_approved_run
print('is_first_approved_run("first"):', df.is_first_approved_run('first'))

# Check effective_budget_cents
print('effective_budget_cents("first"):', df.effective_budget_cents('first'))