import sys
import unittest
import re

loader = unittest.TestLoader()
suite = loader.loadTestsFromName('test_dataforseo_adapter')
runner = unittest.TextTestRunner(verbosity=0)
result = runner.run(suite)

fail = len(result.failures)
error = len(result.errors)
ran_match = re.search(r'Ran (\d+) tests', result._baseTestResult)
ran = ran_match.group(1) if ran_match else '?'

print(f'Ran: {ran}, FAIL: {fail}, ERROR: {error}')

# Show first few failure names
for idx, (test, tb) in enumerate(result.failures[:5]):
    # Extract test name from str(test)
    name = str(test).split('\n')[0] if '\n' in str(test) else str(test)
    print(f'  FAIL {idx+1}: {name}')

for idx, (test, tb) in enumerate(result.errors[:5]):
    name = str(test).split('\n')[0] if '\n' in str(test) else str(test)
    print(f'  ERROR {idx+1}: {name}')