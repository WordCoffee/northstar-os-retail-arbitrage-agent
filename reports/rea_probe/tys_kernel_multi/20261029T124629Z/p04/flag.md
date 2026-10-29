# Feature Flag: `new_ledger_ui`

## Overview
A default-off feature flag `new_ledger_ui` has been added to the ledger service configuration.

## Behavior
- **Default state**: `False` (off)
- **Enabled state**: `True` (on)
- The flag can be overridden via environment variable `NEW_LEDGER_UI`.

## Configuration
The flag is registered in `DEFAULTS` with a default value of `False`.

## Testing
- `test_flag_default_off` verifies the flag is `False` by default.
- `test_flag_enabled_via_environ` verifies the flag becomes `True` when set via environment.
- `test_flag_disabled_via_environ` verifies the flag remains `False` when explicitly set to off.

## Files Modified
- `config.py` – added `new_ledger_ui: False` to `DEFAULTS`
- `test_config.py` – added tests for both states
