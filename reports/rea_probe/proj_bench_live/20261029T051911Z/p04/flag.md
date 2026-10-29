# Feature Flag: `enable_new_feature`

## Overview
This document describes the implementation of a default-off feature flag named `enable_new_feature`. The flag controls the activation of a new feature in the application. By default, the feature is disabled.

## Implementation

### Configuration
The feature flag is defined in the application's configuration system. It is a boolean value that defaults to `false`.

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
        # Default behavior
        return "Feature disabled"
```

## Testing

### Test Cases
The following tests verify that the feature flag works as expected in both states (enabled and disabled).

```python
# test_feature.py
import pytest
from config import FEATURE_FLAGS
from feature import execute_feature

@pytest.mark.parametrize("flag_state, expected_output", [
    (False, "Feature disabled"),
    (True, "Feature enabled")
])
def test_feature_flag(flag_state, expected_output):
    # Set the flag state
    FEATURE_FLAGS["enable_new_feature"] = flag_state
    # Execute the feature
    result = execute_feature()
    # Assert the expected output
    assert result == expected_output
```

### Test Execution
Run the tests using `pytest`:

```bash
pytest test_feature.py
```

## Verification
- **Default Off**: The feature flag is set to `False` by default, ensuring the feature is disabled unless explicitly enabled.
- **Both States Tested**: The test suite covers both the enabled (`True`) and disabled (`False`) states of the feature flag, verifying the correct behavior in each case.
