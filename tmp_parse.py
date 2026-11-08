import re, html as ht

# what did walmart/etsy return?
for n in ('walmart', 'etsy'):
    try:
        t = open('reports/_bd_%s.html' % n, encoding='utf-8', errors='replace').read()
        print('%s -> %r' % (n, t[:240]))
    except Exception as e:
        print(n, e)
print()

# parse amazon results
src = open('reports/_bd_amazon.html', encoding='utf-8', errors='replace').read()

# split on data-asin blocks
blocks = re.split(r'data-asin="', src)
rows = []
for b in blocks[1:]:
    asin = b[:12].strip('"')
    if not re.fullmatch(r'[A-Z0-9]{10}', asin):
        continue
    # title
    m = re.search(r'<h2[^>]*>.*?<span[^>]*>([^<]{10,140})</span>', b, re.S)
    if not m:
        m = re.search(r'aria-label="([^"]{10,140})"', b)
    title = ht.unescape(m.group(1)).strip() if m else ''
    # price
    pm = re.search(r'a-offscreen">\$([\d.]+)</span>', b) or re.search(r'\$([\d]{1,3}\.\d{2})', b)
    price = pm.group(1) if pm else ''
    # reviews
    rm = re.search(r'aria-label="([\d,]+) ratings"', b) or re.search(r'>([\d,]{1,7})</span>\s*</a>', b)
    rev = rm.group(1) if rm else ''
    # rating
    sm = re.search(r'([\d.]+) out of 5 stars', b)
    star = sm.group(1) if sm else ''
    if title:
        rows.append((asin, title[:60], price, star, rev))

seen, uniq = set(), []
for r in rows:
    if r[0] in seen:
        continue
    seen.add(r[0])
    uniq.append(r)

print('parsed products:', len(uniq))
for r in uniq[:20]:
    print('  %-11s %-60s $%-7s %-4s %s rev' % r)
