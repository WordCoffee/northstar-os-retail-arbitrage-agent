#!/usr/bin/env python3
"""Run the FLUX 3 failure test."""
import os
import sys

# Add Northstar_backend to path
sys.path.insert(0, 'Northstar_backend')

# Import the test module
from tests.test_flux3_failure import test_flux3_failure_mode, test_flux3_forced_failure

if __name__ == '__main__':
    print("=== Testing FLUX 3 failure mode ===")
    test_flux3_failure_mode()
    print()
    print("=== Testing FLUX.2 forced mode ===")
    test_flux3_forced_failure()
    print("\n✅ All tests passed!")