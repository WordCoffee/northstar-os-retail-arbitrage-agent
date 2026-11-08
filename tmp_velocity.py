import os, sys, re, time, requests
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
    r = fetch(url)
    print('\n== %s http=%d bytes=%d' % (label, r.status_code, len(r.text)))
    if r.status_code != 200 or len(r.text) < 5000:
        print('   blocked/short:', r.text[:160])
        return
    src = r.text
    open('reports/_bd_%s.html' % label, 'w', encoding='utf-8').write(src)
    blocks = src.split('data-component-type="s-search-result"')
    print('   blocks:', len(blocks) - 1)
    for b in blocks[1:21]:
        a = re.search(r'data-asin="([A-Z0-9]{10})"', b)
        if not a:
            continue
        t = re.search(r'<h2[^>]*aria-label="([^"]+)"', b) or \
            re.search(r'<span class="a-size-(?:base-plus|medium)[^"]*">([^<]+)</span>', b)
        title = t.group(1)[:46] if t else ''
        p = re.search(r'<span class="a-offscreen">\$([\d,]+\.\d{2})</span>', b)
        price = p.group(1) if p else '-'
        # velocity badge
        v = re.search(r'([\d,.]+[KkMm]?\+?)\s*bought in past month', b)
        vel = v.group(1) if v else '-'
        rv = re.search(r'([\d,]+)\s*</span>\s*</a>', b)
        rev = rv.group(1) if rv else '-'
        print('   %-11s %-46s $%-7s %-6s vel=%-5s rev=%s'
              % (a.group(1), title, price, '', vel, rev))
    time.sleep(6)


scan('unpaper', 'https://www.amazon.com/s?k=unpaper+towels+reusable')
scan('beeswax', 'https://www.amazon.com/s?k=beeswax+wraps+for+food')
