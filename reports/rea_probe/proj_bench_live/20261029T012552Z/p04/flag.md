# Feature Flag: `enable_new_feature`

## Description
A default-off feature flag to control the activation of a new feature.

## Implementation
```python
import os

def is_feature_enabled(feature_name: str, default: bool = False) -> bool:
    """
    Check if a feature is enabled via environment variable.
    """
    env_var = f"FEATURE_{feature_name.upper()}"
    value = os.getenv(env_var)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes")
```

## Test
```python
import os
import unittest

class TestFeatureFlag(unittest.TestCase):
    def test_default_off(self):
        """Test that the feature is off by default when env var is not set."""
        os.environ.pop("FEATURE_ENABLE_NEW_FEATURE", None)
        self.assertFalse(is_feature_enabled("enable_new_feature"))

    def test_enabled_state(self):
        """Test that the feature is on when env var is set to true."""
        os.environ["FEATURE_ENABLE_NEW_FEATURE"] = "true"
        self.assertTrue(is_feature_enabled("enable_new_feature"))

    def test_disabled_state(self):
        """Test that the feature is off when env var is set to false."""
        os.environ["FEATURE_ENABLE_NEW_FEATURE"] = "false"
        self.assertFalse(is_feature_enabled("enable_new_feature"))

    def tearDown(self):
        os.environ.pop("FEATURE_ENABLE_NEW_FEATURE", None)
```
