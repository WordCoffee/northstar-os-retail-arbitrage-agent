# Feature Flag: `enable_new_feature`

## Description
A boolean configuration flag that controls whether the new feature is enabled.

## Default
The flag is **off by default** (`False`).

## Usage
```python
from config import get_config

config = get_config()
if config["enable_new_feature"]:
    # enable the new feature
    pass
```

## Behavior
- When `False` (default): the new feature is disabled.
- When `True`: the new feature is enabled.
