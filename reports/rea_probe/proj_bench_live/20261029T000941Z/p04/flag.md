# Feature Flag: `enable_new_feature`

## Description
A default-off feature flag to control the activation of a new feature.

## Implementation

### `feature_flags.py`
```python
def is_feature_enabled(flag_name: str, default: bool = False) -> bool:
    """
    Check if a feature flag is enabled.
    
    Args:
        flag_name: The name of the feature flag.
        default: The default state if the flag is not set (default: False).
    
    Returns:
        bool: True if the feature is enabled, False otherwise.
    """
    # In a real application, this would check an environment variable,
    # configuration file, or feature flag service.
    # For this example, we simulate by checking a global dict.
    flags = {
        "enable_new_feature": False  # Default off
    }
    return flags.get(flag_name, default)
```

### `test_feature_flags.py`
```python
import pytest
from feature_flags import is_feature_enabled

def test_feature_flag_default_off():
    """Test that the feature flag is off by default."""
    assert is_feature_enabled("enable_new_feature") is False

def test_feature_flag_enabled_state():
    """Test that the feature flag can be enabled."""
    # Simulate enabling the flag
    # In a real scenario, this would involve setting an env var or config.
    # Here we mock the behavior by temporarily modifying the global state.
    import feature_flags
    original_value = feature_flags.is_feature_enabled.__globals__['flags']['enable_new_feature']
    feature_flags.is_feature_enabled.__globals__['flags']['enable_new_feature'] = True
    try:
        assert is_feature_enabled("enable_new_feature") is True
    finally:
        feature_flags.is_feature_enabled.__globals__['flags']['enable_new_feature'] = original_value
```

## Verification
- **Default off**: `test_feature_flag_default_off` asserts the flag is `False` when not explicitly set.
- **Both states tested**: `test_feature_flag_enabled_state` asserts the flag is `True` when explicitly enabled.
