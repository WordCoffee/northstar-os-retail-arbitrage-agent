import json
d=json.load(open('docs/mogra-organics-research-2026-10-02/_raw/amazon_search_obs.json',encoding='utf-8'))
for q,items in d.items():
    print('===',q,'===')
    for o in items:
        if o.get('asin') and o.get('price_usd'):
            print(f"  {o['asin']:<12} ${o['price_usd']:<8} {o['rating']:<4} {o['ratings']:<7} {o['title'][:72]}")
