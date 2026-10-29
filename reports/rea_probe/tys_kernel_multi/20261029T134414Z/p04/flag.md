# Feature Flag: `new_ledger_mode`

## Overview
A default-off feature flag has been added to the configuration system. The flag is named `new_ledger_mode` and is disabled by default.

## Default State
- **Default value:** `False` (off)
- The flag is **not** present in the `DEFAULTS` dictionary, so `get("new_ledger_mode")` returns `None` unless explicitly set.
- When `load()` is called without any environment override, the flag is absent from the returned settings dict, confirming it is off by default.

## Enabling the Flag
Set the environment variable `new_ledger_mode` to a truthy value (`1`, `true`, `yes`, `on`) to enable it.

## Test Coverage
The test file `test_config.py` includes tests that verify:
1. **Default off:** `load()` without the flag returns settings that do not contain `new_ledger_mode` (or it is `False`).
2. **Enabled state:** `load({"new_ledger_mode": "on"})` returns `True` for the flag.
3. **Disabled state:** `load({"new_ledger_mode": "off"})` returns `False` for the flag.

Both states (on and off) are explicitly tested.
