# Default-Off Flag

This document describes a configuration flag that is **off by default**.

## Flag: `enable_feature`

- **Default value:** `False`
- **Purpose:** Enables an optional feature in the application.
- **Behavior when off:** The feature is disabled and no additional processing occurs.
- **Behavior when on:** The feature is enabled and the corresponding logic is executed.

## Usage

```python
from config import get_config

config = get_config()
print(config['enable_feature'])  # False by default
```

To enable the flag, set it explicitly in the configuration or via environment variable.
