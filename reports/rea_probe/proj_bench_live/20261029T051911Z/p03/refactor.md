# Refactoring Plan: Splitting `core.py`

## Objective
Split the oversized `core.py` module into two distinct modules (`core.py` and `core_utils.py`) without changing external behavior or public API.

## Strategy
1. **Identify Public API**: Keep all classes/functions currently imported by external modules in `core.py`.
2. **Identify Internal Helpers**: Move private helper functions, constants, and internal classes to `core_utils.py`.
3. **Update Imports**: Update `core.py` to import from `core_utils.py`.
4. **Verify**: Run tests to ensure no behavior changes.

## Step-by-Step Execution

### 1. Create `core_utils.py`
Move the following items from `core.py` to `core_utils.py`:
- `_calculate_hash`
- `_normalize_input`
- `INTERNAL_TIMEOUT`
- `class _InternalCache`

### 2. Update `core.py`
- Remove the moved items.
- Add `from core_utils import _calculate_hash, _normalize_input, INTERNAL_TIMEOUT, _InternalCache`.
- Ensure all public classes/functions remain in `core.py`.

### 3. Update `__init__.py` (if applicable)
Ensure `core` is still the primary entry point. No changes needed if `core_utils` is not exposed publicly.

### 4. Run Tests
Execute `pytest` to confirm all tests pass.

## Expected Outcome
- `core.py` size reduced by ~40%.
- `core_utils.py` contains internal logic.
- Public API unchanged.
- All tests green.
