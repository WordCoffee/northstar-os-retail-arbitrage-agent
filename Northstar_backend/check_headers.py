with open('static/index.html', 'r') as f:
    content = f.read()
import re
match = re.search(r'id="scoutTable"', content)
if match:
    start = match.start()
    end = content.find('</table>', start)
    table = content[start:end+8]
    headers = re.findall(r'<th scope="col"[^>]*>([^<]+)', table)
    for h in headers:
        print(repr(h.strip()))
    print(f"Total: {len(headers)} headers")