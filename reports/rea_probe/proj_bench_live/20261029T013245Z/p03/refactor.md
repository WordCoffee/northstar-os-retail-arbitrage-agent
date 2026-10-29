# Refactor Plan: Split `core.py` into `core.py` and `utils.py`

## Objective
Split the oversized `core.py` module into two modules:
1. `core.py` – retains the primary public API and core logic.
2. `utils.py` – contains internal helper functions and constants.

**Constraints:**
- No changes to public API.
- No changes to behaviour.
- All existing tests must remain green.

## Step 1: Identify Public API
Inspect `core.py` to identify:
- Public classes/functions (no leading underscore).
- Public constants.
- Imports used by external consumers.

## Step 2: Identify Internal Helpers
Identify:
- Private functions (`_helper`, `_compute`, etc.).
- Internal constants.
- Utility functions not part of the public API.

## Step 3: Create `utils.py`
Move internal helpers and constants to `utils.py`.

```python
# utils.py
"""Internal helpers and constants for core module."""

# Move internal constants here
INTERNAL_TIMEOUT = 30
MAX_RETRIES = 5

# Move private helper functions here
def _validate_input(data):
    ...

def _compute_hash(payload):
    ...
```

## Step 4: Update `core.py`
- Remove moved code.
- Import from `utils.py` as needed.
- Keep all public API intact.

```python
# core.py
"""Core module – public API unchanged."""

from utils import _validate_input, _compute_hash, INTERNAL_TIMEOUT, MAX_RETRIES

# Public classes and functions remain here
class CoreService:
    def process(self, data):
        if not _validate_input(data):
            raise ValueError("Invalid input")
        return _compute_hash(data)

def public_api_call(x):
    return CoreService().process(x)
```

## Step 5: Update Imports in Tests
If tests import directly from `core`, no changes needed (public API unchanged).
If tests import internal helpers from `core`, update to import from `utils`.

## Step 6: Run Tests
```bash
pytest
```
Verify all tests pass.

## Step 7: Verify Public API Unchanged
```bash
python -c "import core; print(dir(core))"
```
Compare with pre-refactor output.

## Rollback Plan
If tests fail or API changes:
1. `git checkout core.py utils.py`
2. Re-evaluate split strategy.

## Checklist
- [ ] `utils.py` created with internal helpers
- [ ] `core.py` imports from `utils.py`
- [ ] Public API identical
- [ ] All tests green
- [ ] No circular imports
