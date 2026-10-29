# Refactoring Plan: Splitting `core.py`

## Objective
Split the oversized `core.py` module into two focused modules (`core.py` and `utils.py`) without changing behavior or the public API.

## Current State
- `core.py` contains:
  - Public API functions: `process_data`, `validate_input`
  - Internal helper functions: `_normalize`, `_cache_lookup`, `_log_debug`
  - Constants: `MAX_RETRIES`, `DEBUG_MODE`

## Target Structure

### `core.py` (Public API)
```python
"""Core module exposing the public API."""
from utils import _normalize, _cache_lookup, _log_debug
from constants import MAX_RETRIES, DEBUG_MODE

def process_data(data):
    """Process input data."""
    # Implementation unchanged
    pass

def validate_input(data):
    """Validate input data."""
    # Implementation unchanged
    pass
```

### `utils.py` (Internal helpers)
```python
"""Internal utility functions."""

def _normalize(data):
    """Normalize data."""
    # Implementation unchanged
    pass

def _cache_lookup(key):
    """Look up cached value."""
    # Implementation unchanged
    pass

def _log_debug(msg):
    """Log debug message."""
    # Implementation unchanged
    pass
```

### `constants.py` (Shared constants)
```python
"""Shared constants."""
MAX_RETRIES = 3
DEBUG_MODE = False
```

## Steps
1. Create `constants.py` with `MAX_RETRIES` and `DEBUG_MODE`.
2. Create `utils.py` with `_normalize`, `_cache_lookup`, `_log_debug`.
3. Update `core.py` to import from `utils` and `constants`.
4. Ensure all imports in `core.py` are explicit and no circular dependencies.
5. Run test suite to verify green tests.
6. Verify public API (`process_data`, `validate_input`) remains unchanged.

## Verification
- [ ] All tests pass
- [ ] Public API unchanged
- [ ] No circular imports
- [ ] No behavior changes
