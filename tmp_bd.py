import os, sys, re, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Northstar_backend'))
import env_bootstrap
env_bootstrap.load_project_env()

KEY = os.environ.get('BRIGHTDATA_UNLOCKER_API_KEY', '').strip()
ZONE = os.environ.get('BRIGHTDATA_UNLOCKER_ZONE', 'web_unlocker1')
print('zone:', ZONE, '| key present:', bool(KEY))

def fetch(url):
    r = requests.post('https://api.brightdata.com/request',
                      headers={'Authorization': 'Bearer ' + KEY,
                               'Content-Type': 'application/json'},
                      json={'zone': ZONE, 'url': url, 'format': 'raw'},
                      timeout=120)
    return r.status_code, r.text

URLS = [
    ('AMAZON', 'https://www.amazon.com/s?k=unpaper+towels+reusable'),
    ('WALMART', 'https://www.walmart.com/search?q=unpaper+towels'),
    ('ETSY', 'https://www.etsy.com/search?q=unpaper+towels'),
]

out = {}
for name, u in URLS:
    try:
        code, html = fetch(u)
        out[name] = {'code': code, 'len': len(html)}
        print('\n== %s  http=%s  bytes=%d' % (name, code, len(html)))
        # crude price extraction
        prices = re.findall(r'\$\s?(\d{1,3}\.\d{2})', html)
        uniq = []
        for p in prices:
            v = float(p)
            if 5 <= v <= 120:
                uniq.append(p)
        print('   prices found:', uniq[:18])
        # review counts
        revs = re.findall(r'([\d,]{1,7})\s*(?:ratings|reviews)', html, re.I)
        print('   review counts:', revs[:12])
        open('reports/_bd_%s.html' % name.lower(), 'w', encoding='utf-8').write(html)
    except Exception as e:
        print('FAIL', name, repr(e)[:140])
json.dump(out, open('reports/_bd_result.json', 'w'), indent=1)
