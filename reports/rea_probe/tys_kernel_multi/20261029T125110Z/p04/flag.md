# Feature Flag: `new_ledger_ui`

## Default
The flag is **off** by default. It is not present in `DEFAULTS` and `get()` returns `False` when the environment variable is absent.

## How to enable
Set the environment variable `NEW_LEDGER_UI` to a truthy value (`1`, `true`, `yes`, `on`). The existing `coerce` helper handles the conversion.

## Tests
`test_config.py` contains two tests:
- `test_flag_default_off` – asserts the flag is `False` when no environment variable is set.
- `test_flag_on_via_environ` – asserts the flag is `True` when `NEW_LEDGER_UI=1` is provided.
