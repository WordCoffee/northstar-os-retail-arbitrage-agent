import urllib.request
import re

response = urllib.request.urlopen('http://127.0.0.1:8000/')
html = response.read().decode()
links = re.findall('href="([^"]+\.html)"', html)
print('Links:', links)