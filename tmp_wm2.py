import os, sys, re, json, time, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Northstar_backend'))
import env_bootstrap
env_bootstrap.load_project_env()

KEY = os.environ.get('BRIGHTDATA_UNLOCKER_API_KEY', '').strip()
ZONE = os.environ.get('BRIGHTDATA_UNLOCKER_ZONE', 'web_unlocker1')


def parse(path):
    src = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', src, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))
    stack, items = [data], []
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if 'name' in cur and ('priceInfo' in cur or 'canonicalUrl' in cur):
                items.append(cur)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    out, seen = [], set()
    for it in items:
        nm = (it.get('name') or '').strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        cp = ((it.get('priceInfo') or {}).get('currentPrice') or {})
        badge = ''
        for b in (it.get('badges') or []):
            badge += (b.get('text') if isinstance(b, dict) else str(b)) or ''
            badge += ' '
        out.append({
            'name': nm,
            'price': cp.get('price'),
            'rating': it.get('customerRating'),
            'reviews': it.get('numReviews'),
            'seller': ((it.get('sellerInfo') or {}).get('name') or ''),
            'badge': badge.strip(),
            'marketplace': bool(it.get('sellerInfo')),
        })
    return out


def show(label, rows):
    print('\n===== %s  (%d unique) =====' % (label, len(rows)))
    wm = [r for r in rows if r['marketplace']]
    print('  marketplace (3P) listings: %d / %d' % (len(wm), len(rows)))
    for r in rows[:20]:
        print('   %-50s $%-8s %-4s %-6s %-20s %s' % (
            r['name'][:50], r['price'], r['rating'], r['reviews'],
            (r['seller'] or 'Walmart')[:20], r['badge'][:24]))


# unpaper already saved
show('UNPAPER TOWELS', parse('reports/_wm_unpaper.html'))

# fetch beeswax
def fetch(url):
    return requests.post('https://api.brightdata.com/request',
                         headers={'Authorization': 'Bearer ' + KEY,
                                  'Content-Type': 'application/json'},
                         json={'zone': ZONE, 'url': url, 'format': 'raw'},
                         timeout=150)

for a in range(3):
    r = fetch('https://www.walmart.com/search?q=beeswax+food+wraps')
    if r.status_code == 200 and len(r.text) > 100000:
        break
    print('retry', a + 1, r.status_code, len(r.text), r.text[:80])
    time.sleep(15)
open('reports/_wm_beeswax.html', 'w', encoding='utf-8').write(r.text)
print('\nbeeswax fetched:', r.status_code, len(r.text))
show('BEESWAX WRAPS', parse('reports/_wm_beeswax.html'))
