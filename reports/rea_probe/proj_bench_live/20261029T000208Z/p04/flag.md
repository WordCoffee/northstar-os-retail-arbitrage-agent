```markdown
# Feature Flag: `enable_new_feature`

## Overview
This document describes the implementation of a default-off feature flag named `enable_new_feature`. The flag controls the activation of a new feature within the application.

## Implementation Details

### Configuration
- **Flag Name**: `enable_new_feature`
- **Default State**: `false` (Off)
- **Type**: Boolean

### Code Snippet (Example)
```python
# config.py
FEATURE_FLAGS = {
    "enable_new_feature": False  # Default is off
}

# app.py
from config import FEATURE_FLAGS

def get_feature_status():
    return FEATURE_FLAGS.get("enable_new_feature", False)
```

## Testing

### Test Cases
The following test cases verify that the feature flag behaves correctly in both states (on and off).

#### Test 1: Default State (Off)
- **Description**: Verify that the feature is disabled by default.
- **Expected Result**: `get_feature_status()` returns `False`.

#### Test 2: Enabled State (On)
- **Description**: Verify that the feature can be enabled.
- **Expected Result**: After setting `FEATURE_FLAGS["enable_new_feature"] = True`, `get_feature_status()` returns `True`.

### Test Code (Example)
```python
import unittest
from config import FEATURE_FLAGS
from app import get_feature_status

class TestFeatureFlag(unittest.TestCase):
    def test_default_off(self):
        """Test that the feature is off by default."""
        self.assertFalse(get_feature_status())

    def test_enabled_state(self):
        """Test that the feature can be enabled."""
        FEATURE_FLAGS["enable_new_feature"] = True
        self.assertTrue(get_feature_status())
        # Reset for other tests
        FEATURE_FLAGS["enable_new_feature"] = False

if __name__ == "__main__":
    unittest.main()
```

## Verification
- **Default Off**: Confirmed by `test_default_off`.
- **Both States Tested**: Confirmed by `test_default_off` and `test_enabled_state`.
```
