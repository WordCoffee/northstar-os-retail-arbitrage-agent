#!/usr/bin/env python3
import subprocess
import sys
import re

result = subprocess.run(
    [sys.executable, '-m', 'unittest', 'test_dataforseo_adapter'],
    capture_output=True, text=True, cwd=r'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend'
)

output = result.stdout + result.stderr

fail_match = re.search(r'FAIL\: ([^\n]+)', output)
error_match = re.search(r'ERROR\: ([^\n]+)', output)
ran_match = re.search(r'Ran (\d+) tests', output)

fail_count = len(re.findall(r'^FAIL:', output, re.MULTILINE))
error_count = len(re.findall(r'^ERROR:', output, re.MULTILINE))
ran = ran_match.group(1) if ran_match else '?'

print(f'Ran: {ran}, FAIL: {fail_count}, ERROR: {error_count}')

# Show the last summary line
for line in output.split('\n')[-5:]:
    print(line)