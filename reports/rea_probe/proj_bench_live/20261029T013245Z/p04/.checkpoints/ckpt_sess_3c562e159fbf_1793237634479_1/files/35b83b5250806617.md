# Feature Flag: `enable_new_feature`

## Overview
This document describes the implementation of a default-off feature flag named `enable_new_feature`. The flag controls the activation of a new feature within the application. By default, the feature is disabled.

## Implementation

### Configuration
The feature flag is managed through a configuration system. The default value is set to `false`.

```python
# config.py
FEATURE_FLAGS = {
    "enable_new_feature": False
}
```

### Usage
The feature is conditionally enabled based on the flag's state.

```python
# feature.py
from config import FEATURE_FLAGS

def execute_feature():
    if FEATURE_FLAGS["enable_new_feature"]:
        # New feature logic
        return "New feature is active"
    else:
        # Default behavior
        return "New feature is inactive"
```

## Testing

### Test Cases
The following tests verify the behavior of the feature flag in both states (enabled and disabled).

```python
# test_feature.py
import unittest
from feature import execute_feature
from config import FEATURE_FLAGS

class TestFeatureFlag(unittest.TestCase):
    def test_feature_disabled_by_default(self):
        """Test that the feature is disabled by default."""
        self.assertFalse(FEATURE_FLAGS["enable_new_feature"])
        self.assertEqual(execute_feature(), "New feature is inactive")

    def test_feature_enabled(self):
        """Test that the feature is enabled when the flag is set to True."""
        FEATURE_FLAGS["enable_new_feature"] = True
        self.assertTrue(FEATURE_FLAGS["enable_new_feature"])
        self.assertEqual(execute_feature(), "New feature is active")

    def test_feature_disabled_after_reset(self):
        """Test that the feature is disabled when the flag is reset to False."""
        FEATURE_FLAGS["enable_new_feature"] = False
        self.assertFalse(FEATURE_FLAGS["enable_new_feature"])
        self.assertEqual(execute_feature(), "New feature is inactive")

if __name__ == "__main__":
    unittest.main()
```

## Verification
- **Default Off**: The feature flag is initialized to `False`, ensuring the feature is disabled by default.
- **Both States Tested**: The test suite includes cases for both the enabled (`True`) and disabled (`False`) states of the flag.
