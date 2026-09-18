"""Quick report inspection."""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))

r = json.load(open(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend\agents\data\golden-goose-reports\goose_live_scan_20260917_041651.json"))
print(f"Opportunities: {len(r.get('opportunities', []))}")
print(f"Discarded: {len(r.get('discarded', []))}")
opps = r.get("opportunities", [])[:5]
for o in opps:
    print(f"\n  #{o.get('rank')} {o.get('brand', '?')} - {o.get('product_title', '?')[:60]}")
    print(f"    ASIN: {o.get('amazon_asin')}")
    print(f"    Profit: ${o.get('net_profit_per_unit')} | ROI: {o.get('roi_per_unit')}%")
    print(f"    Score: {o.get('composite_score')} | Tier: {o.get('tier')}")
    print(f"    Ad Score: {o.get('ad_feasibility_score')} | Undercut: ${o.get('undercut_headroom')}")
    print(f"    Tags: {o.get('opportunity_tags')}")
    fb = o.get("financial_breakdown", {})
    print(f"    Buy Box: ${fb.get('buy_box_price')} | Max Undercut: ${fb.get('max_undercut_price')}")
    sc = o.get("scoring", {})
    print(f"    Ad Breakdown: {sc.get('ad_feasibility_breakdown')}")
