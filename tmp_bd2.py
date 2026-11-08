import os, sys, re, time, html as ht, requests
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

# --- retry walmart ---
time.sleep(12)
r = fetch('https://www.walmart.com/search?q=unpaper+towels')
print('WALMART retry:', r.status_code, len(r.text))
if len(r.text) > 5000:
    t = r.text
    prices = re.findall(r'"price":\s*"?([\d.]+)', t)[:20]
    print('  prices:', prices)
    names = re.findall(r'"name":"([^"]{10,70})"', t)[:10]
    for n in names:
        print('   -', ht.unescape(n))

# --- amazon structured parse ---
src = open('reports/_bd_amazon.html', encoding='utf-8', errors='replace').read()
blocks = src.split('data-component-type="s-search-result"')
print('\nAMAZON blocks:', len(blocks) - 1)
rows = []
for b in blocks[1:]:
    a = re.search(r'data-asin="([A-Z0-9]{10})"', b)
    asin = a.group(1) if a else ''
    if not asin:
        continue
    t = re.search(r'<h2[^>]*aria-label="([^"]+)"', b)
    if not t:
        t = re.search(r'<span class="a-size-base-plus[^"]*">([^<]+)</span>', b)
    if not t:
        t = re.search(r'<span class="a-size-medium[^"]*">([^<]+)</span>', b)
    title = ht.unescape(t.group(1)).strip()[:58] if t else ''
    p = re.search(r'<span class="a-offscreen">\$([\d,]+\.\d{2})</span>', b)
    price = p.group(1) if p else ''
    rv = re.search(r'([\d,]+)\s*</span>\s*</a>', b)
    rev = rv.group(1) if rv else ''
    st = re.search(r'([\d.]+) out of 5 stars', b)
    star = st.group(1) if st else ''
    rows.append((asin, title, price, star, rev))

print('parsed:', len(rows))
for r_ in rows[:18]:
    print('  %-11s %-58s $%-8s %-4s %s' % r_)
