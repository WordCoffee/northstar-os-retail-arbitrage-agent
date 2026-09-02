#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend')
import dataforseo_adapter as df

# Test is_first_approved_run
print('is_first_approved_run("first"):', df.is_first_approved_run('first'))

# Test effective_budget_cents
print('effective_budget_cents("first"):', df.effective_budget_cents('first'))
print('effective_budget_cents("second"):', df.effective_budget_cents('second'))

# Test create_approval
rec = df.create_approval('first', 'first')
print('create_approval result:', rec)

# Test is_first_approved_run after create_approval
print('is_first_approved_run("first") after create:', df.is_first_approved_run('first'))