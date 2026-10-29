# Feature Flag: `enable_new_feature`

## Overview
This document describes the `enable_new_feature` feature flag, which is **default-off**. It controls the activation of a new feature in the application.

## Configuration
- **Flag Name:** `enable_new_feature`
- **Default Value:** `false`
- **Type:** Boolean
- **Scope:** Global

## Usage
To enable the feature, set the flag to `true` in the configuration or via environment variable:
```bash
ENABLE_NEW_FEATURE=true
```

## Testing
The following test verifies both states of the feature flag:

```python
import pytest
from app import get_feature_flag

def test_feature_flag_default_off():
    """Test that the feature flag is off by default."""
    assert get_feature_flag('enable_new_feature') is False

def test_feature_flag_enabled():
    """Test that the feature flag can be enabled."""
    with patch('app.config.ENABLE_NEW_FEATURE', True):
        assert get_feature_flag('enable_new_feature') is True
```

## Verification
- ✅ Default state is `false`
- ✅ Both states (`true` and `false`) are tested
