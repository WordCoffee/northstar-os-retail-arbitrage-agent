```markdown
# Feature Flag: `enable_new_feature`

## Description
A default-off feature flag to control the activation of a new feature.

## Implementation
```python
# feature_flags.py
import os

def is_feature_enabled(flag_name: str, default: bool = False) -> bool:
    """
    Check if a feature flag is enabled.
    Defaults to False unless explicitly set to True via environment variable.
    """
    env_value = os.environ.get(flag_name, str(default)).lower()
    return env_value in ('true', '1', 'yes')
```

## Tests
```python
# test_feature_flags.py
import os
from unittest.mock import patch
from feature_flags import is_feature_enabled

def test_feature_flag_default_off():
    """Test that the feature flag is off by default."""
    with patch.dict(os.environ, {}, clear=True):
        assert is_feature_enabled('enable_new_feature') is False

def test_feature_flag_enabled():
    """Test that the feature flag can be enabled."""
    with patch.dict(os.environ, {'enable_new_feature': 'true'}):
        assert is_feature_enabled('enable_new_feature') is True
```

## Verification
- **Default off**: `test_feature_flag_default_off` ensures the flag is `False` when not set.
- **Both states tested**: `test_feature_flag_default_off` and `test_feature_flag_enabled` cover both `False` and `True` states.
```
