import re, json

def load(path):
    src = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', src, re.S)
    return json.loads(m.group(1)) if m else None


def walk_items(d):
    """Find the search itemStacks items list."""
    found = []

    def rec(o):
        if isinstance(o, dict):
            if 'itemStacks' in o and isinstance(o['itemStacks'], list):
                for st in o['itemStacks']:
                    for it in (st.get('items') or []):
                        found.append(it)
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
    rec(d)
    return found


def total_count(d):
    s = json.dumps(d)
    m = re.search(r'"totalResultCount":\s*(\d+)', s)
    if m:
        return m.group(1)
    m = re.search(r'([\d,]+)\s*results', s)
    return m.group(1) if m else '?'


for label, path in (('UNPAPER', 'reports/_wm_unpaper.html'),
                    ('BEESWAX', 'reports/_wm_beeswax.html')):
    d = load(path)
    if not d:
        print(label, 'no data')
        continue
    items = walk_items(d)
    print('\n===== %s =====' % label)
    print('  totalResultCount:', total_count(d), '| items parsed:', len(items))
    seen = set()
    for it in items:
        nm = (it.get('name') or '').strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        pi = it.get('priceInfo') or {}
        cp = pi.get('currentPrice') or {}
        price = cp.get('price') or pi.get('linePrice') or ''
        seller = ((it.get('sellerInfo') or {}).get('name') or '')
        mp = it.get('sellerInfo') is not None
        print('   %-52s $%-8s %-4s %-6s %-16s %s' % (
            nm[:52], price, it.get('customerRating') or '',
            it.get('numReviews') or '', (seller or 'Walmart')[:16],
            '3P' if mp else '1P'))
        if len(seen) >= 18:
            break
