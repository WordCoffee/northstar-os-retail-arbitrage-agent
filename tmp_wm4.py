import re

for lbl in ('unpaper', 'beeswax'):
    src = open('reports/_wm_%s.html' % lbl, encoding='utf-8', errors='replace').read()
    revs = [int(x) for x in re.findall(r'"numReviews":\s*(\d+)', src) if x]
    sper = re.findall(r'"sellerName":"([^"]{2,30})"', src)
    uniq = list(dict.fromkeys(sper))
    print('%s | listings with reviews: %d | max reviews: %d' % (lbl, len(revs), max(revs) if revs else 0))
    print('   top review counts:', sorted(revs, reverse=True)[:10])
    print('   marketplace sellers: %d unique | %s' % (len(set(sper)), uniq[:8]))
    wm1p = len(re.findall(r'"sellerName":"Walmart"', src))
    print('   Walmart-sold listings:', wm1p)
    print()
