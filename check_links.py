import urllib.request
import re

r = urllib.request.urlopen('http://127.0.0.1:8000/')
html = r.read().decode()
links = re.findall('href="([^"]+)"', html)
for l in links[:20]:
    print(l)