#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend')
import dataforseo_adapter as df

print('Set before create:', df._GLOBAL_APPROVED_RUNS)
rec = df.create_approval('first', 'first')
print('Set after create:', df._GLOBAL_APPROVED_RUNS)
print('"first" in set:', 'first' in df._GLOBAL_APPROVED_RUNS)
lst = list(df._GLOBAL_APPROVED_RUNS)
print('List:', lst)
if 'first' in lst:
    print('Index of first:', lst.index('first'))
print('effective_budget_cents("first"):', df.effective_budget_cents('first'))