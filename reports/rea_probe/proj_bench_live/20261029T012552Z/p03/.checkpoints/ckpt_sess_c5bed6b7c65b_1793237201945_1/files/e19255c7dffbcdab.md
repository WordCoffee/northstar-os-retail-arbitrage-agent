# Refactoring Plan: Split Oversized Module

## Objective
Split the oversized module `core.py` into two modules: `core.py` and `core_utils.py`, without changing behavior or the public API.

## Steps

1. **Identify Public API**
   - List all functions/classes in `core.py` that are imported by other modules or used externally.
   - These must remain accessible from `core.py`.

2. **Identify Internal Helpers**
   - Identify functions/classes in `core.py` that are only used internally (not imported elsewhere).
   - Move these to `core_utils.py`.

3. **Create `core_utils.py`**
   - Create a new file `core_utils.py`.
   - Move the internal helper functions/classes into this file.
   - Ensure no circular imports: `core_utils.py` should not import from `core.py`.

4. **Update `core.py`**
   - Remove the moved functions/classes from `core.py`.
   - Import the moved functions/classes from `core_utils.py` if they are still needed internally.
   - Ensure all public API functions/classes remain in `core.py`.

5. **Update Imports**
   - If any other modules import the moved functions directly from `core.py`, update those imports to use `core_utils.py` or re-export from `core.py` to maintain backward compatibility.
   - Prefer re-exporting from `core.py` to keep the public API unchanged.

6. **Run Tests**
   - Run the full test suite to ensure all tests pass.
   - Verify that no new errors or warnings are introduced.

7. **Verify Public API**
   - Confirm that all previously public functions/classes are still accessible from `core.py`.
   - Use `dir(core)` or similar introspection to verify the API surface.

## Constraints
- No changes to behavior.
- Public API must remain identical.
- No circular imports.
- All tests must pass.
