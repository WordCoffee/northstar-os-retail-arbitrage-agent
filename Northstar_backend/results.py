import subprocess
import sys

# Run the tests and capture output
result = subprocess.run(
    [sys.executable, '-m', 'unittest', 'test_dataforseo_adapter'],
    capture_output=True, text=True, cwd=r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend'
)

# Parse the output
output = result.stdout + result.stderr

import re
fail_count = len(re.findall(r'^FAIL:', output, re.MULTILINE))
error_count = len(re.findall(r'^ERROR:', output, re.MULTILINE))
ran_match = re.search(r'Ran (\d+) tests', output)
ran = ran_match.group(1) if ran_match else '?'

print(f'Ran: {ran}, FAIL: {fail_count}, ERROR: {error_count}')

# Show failure details
for m in re.finditer(r'^FAIL:.*$', output, re.MULTILINE):
    name = m.group(0).split(' ')[0] if ' ' in m.group(0) else m.group(0)
    print(f'  FAIL: {name}')

for m in re.finditer(r'^ERROR:.*$', output, re.MULTILINE):
    name = m.group(0).split(' ')[0] if ' ' in m.group(0) else m.group(0)
    print(f'  ERROR: {name}')