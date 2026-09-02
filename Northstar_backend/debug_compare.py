#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend')
import dataforseo_adapter as df
from test_dataforseo_adapter import SHORTLIST_ASIN, MARKETPLACE, BD_REF

# Exactly replicate the test_compare_provider_error test
bd = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water"}
df_norm = {"asin": SHORTLIST_ASIN, "title": "Kirkland Water", "observed_price": 19.99}

# Add debug prints
print("bd:", bd)
print("df_norm:", df_norm)
print("bd observed_price:", bd.get("observed_price"))
print("df_norm observed_price:", df_norm.get("observed_price"))

# Call the function
res = df.compare_with_bright_data(bd, df_norm)
print("Result:", res)
print("Classification:", res["classification"])