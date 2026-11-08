import os, sys, re, json, time, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Northstar_backend'))
import env_bootstrap
env_bootstrap.load_project_env()

KEY = os.environ.get('BRIGHTDATA_UNLOCKER_API_KEY', '').strip()
ZONE = os.environ.get('BRIGHTDATA_UNLOCKER_ZONE', 'web_unlocker1')

def fetch(url):
    return requests.post('https://api.brightdata.com/request',
                         headers={'Authorization': 'Bearer ' + KEY,
                                  'Content-Type': 'application/json'},
                         json={'zone': ZONE, 'url': url, 'format': 'raw'},
                         timeout=150)

def scan(label, url):
    for attempt in range(3):
        r = fetch(url)
        if r.status_code == 200 and len(r.text) > 100000:
            break
        print('  retry', attempt + 1, r.status_code, len(r.text), r.text[:90])
        time.sleep(15)
    src = r.text
    print('\n== %s http=%d bytes=%d' % (label, r.status_code, len(src)))
    open('reports/_wm_%s.html' % label, 'w', encoding='utf-8').write(src)

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', src, re.S)
    if not m:
        print('  no __NEXT_DATA__')
        return
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        print('  json fail', e)
        return

    stack = [data]
    items = []
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if 'name' in cur and ('priceInfo' in cur or 'canonicalUrl' in cur):
                items.append(cur)
            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                stack.append(v)

    print('  product nodes:', len(items))
    seen = set()
    for it in items:
        nm = (it.get('name') or '').strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        pi = it.get('priceInfo') or {}
        cp = pi.get('currentPrice') or {}
        price = cp.get('price')
        rating = it.get('customerRating') or ''
        reviews = it.get('numReviews') or ''
        seller = ((it.get('sellerInfo') or {}).get('name') or '')
        badge = ''
        for b in (it.get('badges') or []):
            badge += (b.get('text') or '') + ' '
        print('   %-52s $%-8s %-5s %-7s %-18s %s'
              % (nm[:52], price, rating, reviews, seller[:18], badge.strip()[:22]))
        if len(seen) >= 22:
            break

    time.sleep(8)


scan('unpaper', 'https://www.walmart.com/search?q=unpaper+towels+reusable')
scan('beeswax', 'https://www.walmart.com/search?q=beeswax+food+wraps')
