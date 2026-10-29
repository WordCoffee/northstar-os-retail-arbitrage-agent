# Refactor Plan: Split `core.py`

## Objective
Split the oversized `core.py` module into two modules (`core.py` and `core_utils.py`) without changing behavior.

## Constraints
1. **Tests Green**: All existing unit tests must pass.
2. **Public API Unchanged**: The public interface of `core.py` must remain identical.

## Steps

### 1. Identify Public API
- List all public functions, classes, and constants in `core.py`.
- Ensure these remain accessible from `core.py`.

### 2. Identify Internal Utilities
- Identify helper functions, constants, and classes that are not part of the public API.
- Move these to `core_utils.py`.

### 3. Update Imports
- In `core.py`, import necessary items from `core_utils.py`.
- Ensure no circular dependencies.

### 4. Update Tests
- Update test imports if they directly reference internal utilities.
- Ensure tests still pass.

### 5. Verify
- Run all tests.
- Confirm public API is unchanged.

## Files to Modify
- `core.py`
- `core_utils.py` (new)
- `tests/test_core.py` (if needed)

## Rollback Plan
- If tests fail, revert changes.
- If public API changes, revert and re-evaluate split.
