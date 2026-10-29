```markdown
# Feature Flag: `enable_new_feature`

## Overview
This document describes the implementation of a default-off feature flag named `enable_new_feature`. The flag controls the activation of a new feature within the application. By default, the feature is disabled to ensure backward compatibility and stability.

## Implementation Details

### Configuration
The feature flag is managed through a configuration module. The default value is set to `false`.

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
        return "Feature enabled"
    else:
        # Fallback logic
        return "Feature disabled"
```

## Testing

### Test Suite
A test suite is provided to verify the behavior of the feature flag in both states (enabled and disabled).

```python
# test_feature.py
import unittest
from config import FEATURE_FLAGS
from feature import execute_feature

class TestFeatureFlag(unittest.TestCase):
    def test_feature_disabled_by_default(self):
        """Test that the feature is disabled by default."""
        self.assertFalse(FEATURE_FLAGS["enable_new_feature"])
        self.assertEqual(execute_feature(), "Feature disabled")

    def test_feature_enabled(self):
        """Test that the feature works when enabled."""
        FEATURE_FLAGS["enable_new_feature"] = True
        self.assertTrue(FEATURE_FLAGS["enable_new_feature"])
        self.assertEqual(execute_feature(), "Feature enabled")
        
        # Reset flag to default state
        FEATURE_FLAGS["enable_new_feature"] = False

if __name__ == "__main__":
    unittest.main()
```

## Verification
- **Default State**: The flag is `False` by default, ensuring the feature is off.
- **Both States Tested**: The test suite explicitly checks both the disabled (default) and enabled states of the flag.
```
