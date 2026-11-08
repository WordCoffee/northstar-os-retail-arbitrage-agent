import os, sys, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Northstar_backend'))
import env_bootstrap
env_bootstrap.load_project_env()
KEY = (os.environ.get('RAINFOREST_API_KEY') or '').strip()
r = requests.get('https://api.rainforestapi.com/request',
                 params={'api_key': KEY, 'type': 'search',
                         'amazon_domain': 'amazon.com',
                         'search_term': 'unpaper towels reusable'}, timeout=150).json()
res = r.get('search_results', []) or []
print('results:', len(res), 'credits left:', r.get('request_info', {}).get('credits_remaining'))
for p in res[:10]:
    t = (p.get('title') or '').encode('ascii', 'ignore').decode('ascii')[:44]
    print('  %-12s %-44s $%-7s %s* %s rev' % (
        p.get('asin'), t, (p.get('price') or {}).get('value'),
        p.get('rating'), p.get('ratings_total')))
