```markdown
# Refactor Plan: Split `core.py`

## Objective
Split the oversized `core.py` module into two focused modules without changing behaviour.

## Current State
- `core.py` contains:
  - `Config` class
  - `Logger` class
  - `DataProcessor` class
  - `utils` functions

## Proposed Structure
1. `config.py`
   - `Config` class
2. `logging.py`
   - `Logger` class
3. `processor.py`
   - `DataProcessor` class
4. `utils.py`
   - Utility functions

## Public API
- `core.py` will re-export all public symbols to maintain backward compatibility.

## Steps
1. Create `config.py` with `Config` class.
2. Create `logging.py` with `Logger` class.
3. Create `processor.py` with `DataProcessor` class.
4. Create `utils.py` with utility functions.
5. Update `core.py` to import and re-export all public symbols.
6. Run tests to ensure green.
7. Verify public API unchanged.

## Verification
- All tests pass.
- Public API unchanged.
```
