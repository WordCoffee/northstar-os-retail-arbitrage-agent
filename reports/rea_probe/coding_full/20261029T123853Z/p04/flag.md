# Feature Flag: `enable_new_parser`

## Description
A default-off feature flag that controls whether the new parser is used.

## Default State
- **Default:** `False` (off)
- When off, the legacy parser is used.

## Enabled State
- When set to `True`, the new parser is used.

## Usage
```python
from config import get_config

config = get_config()
if config.enable_new_parser:
    # use new parser
else:
    # use legacy parser
```
