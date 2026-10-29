# Feature Flag: `enable_new_feature`

## Description
A default-off feature flag that controls whether the new feature is enabled.

## Default State
- **Default:** `False` (off)
- The flag is disabled by default to ensure backward compatibility.

## Usage
- Set `enable_new_feature = True` in `config.py` to enable the feature.
- Set `enable_new_feature = False` in `config.py` to disable the feature.

## Testing
- `test_config.py` covers both states (on and off) of the flag.
