# Refactoring Plan: Splitting `legacy_core.py`

## Objective
Split the oversized module `legacy_core.py` into two focused modules:
1. `data_processing.py`: Handles data ingestion, validation, and transformation.
2. `business_logic.py`: Handles core business rules and state management.

**Constraints:**
- No changes to public API.
- All existing tests must remain green.
- No behavioral changes.

## Step-by-Step Execution

### 1. Analysis
- Identify public functions in `legacy_core.py` that are part of the public API.
- Categorize internal helper functions into "data processing" vs. "business logic" based on their dependencies and purpose.
- Map circular dependencies to ensure clean separation.

### 2. Create New Modules
- Create `data_processing.py` and move all data-related functions and classes.
- Create `business_logic.py` and move all business-rule-related functions and classes.
- Ensure imports between the new modules are minimal and acyclic.

### 3. Update `legacy_core.py`
- Remove all moved code.
- Re-export the public API from the new modules to maintain backward compatibility.
  ```python
  from data_processing import *
  from business_logic import *
  ```
- Ensure `__all__` is defined to explicitly list public names.

### 4. Verification
- Run the full test suite to confirm all tests pass.
- Verify that `import legacy_core` still exposes the same public API.
- Confirm no circular imports exist.

## Rollback Plan
If tests fail or API changes are detected:
1. Revert `legacy_core.py` to its original state.
2. Delete `data_processing.py` and `business_logic.py`.
3. Re-run tests to confirm baseline stability.

## Success Criteria
- ✅ All tests pass.
- ✅ Public API unchanged.
- ✅ No circular imports.
- ✅ Code is logically separated into two modules.
