import urllib.request
import re

r = urllib.request.urlopen('http://127.0.0.1:8000/')
html = r.read().decode()

if 'Northstar Arbitrage OS' in html:
    print('Serving landing page (index.html)')
elif 'Analyst' in html:
    print('Serving Northstar OS (northstar-os/index.html)')
else:
    print('Unknown')

m = re.search('<title>([^<]+)</title>', html)
if m:
    print('Title:', m.group(1))
else:
    print('No title')