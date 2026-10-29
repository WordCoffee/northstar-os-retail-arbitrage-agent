# Refactor Plan: Split `core.py`

## Objective
Split the oversized `core.py` module into two focused modules without changing behavior.

## Current State
- **File**: `core.py`
- **Size**: ~1,200 lines
- **Issues**:
  - Mixed concerns: data validation, business logic, and I/O handling
  - Hard to test in isolation
  - High cyclomatic complexity

## Target Structure

### 1. `core/validation.py`
**Responsibility**: Input validation and data normalization.

**Contents to extract**:
- `validate_input()`
- `normalize_data()`
- `ValidationException`
- Related helper functions

**Public API preserved**:
- All functions remain importable from `core` via re-exports

### 2. `core/logic.py`
**Responsibility**: Business logic and core processing.

**Contents to extract**:
- `process_data()`
- `calculate_metrics()`
- `transform_records()`
- Related helper functions

**Public API preserved**:
- All functions remain importable from `core` via re-exports

### 3. `core/__init__.py`
**Responsibility**: Public API facade.

**Contents**:
```python
from .validation import (
    validate_input,
    normalize_data,
    ValidationException,
)
from .logic import (
    process_data,
    calculate_metrics,
    transform_records,
)

__all__ = [
    "validate_input",
    "normalize_data",
    "ValidationException",
    "process_data",
    "calculate_metrics",
    "transform_records",
]
```

## Migration Steps

1. **Create `core/validation.py`**
   - Move validation functions from `core.py`
   - Update internal imports

2. **Create `core/logic.py`**
   - Move business logic functions from `core.py`
   - Import from `validation.py` if needed

3. **Update `core/__init__.py`**
   - Re-export all public symbols
   - Maintain backward compatibility

4. **Remove `core.py`**
   - Delete the original file
   - Ensure no direct imports of `core.py` remain

## Verification

### Tests
- Run full test suite: `pytest`
- All tests must pass without modification
- No new test failures

### Public API Check
- Verify all previously importable symbols remain accessible:
  ```python
  from core import validate_input, normalize_data, ValidationException
  from core import process_data, calculate_metrics, transform_records
  ```
- No `ImportError` or `AttributeError`

### Behavior Preservation
- No changes to function signatures
- No changes to return values
- No changes to side effects
- No changes to exception behavior

## Rollback Plan
If issues arise:
1. Restore `core.py` from version control
2. Remove `core/validation.py` and `core/logic.py`
3. Revert `core/__init__.py`
