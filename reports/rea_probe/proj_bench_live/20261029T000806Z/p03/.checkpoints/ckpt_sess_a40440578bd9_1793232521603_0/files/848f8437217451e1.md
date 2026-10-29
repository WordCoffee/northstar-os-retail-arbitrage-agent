1. **Isolate Logic**: Extract the target functionality into a new module, ensuring it has no circular dependencies with the original.
2. **Refactor Original**: Replace the extracted code in the original module with imports from the new module, keeping the original's public interface identical.
3. **Verify Behavior**: Run the full test suite to confirm all tests pass and no regressions have occurred.
4. **Validate API**: Execute a diff on the public API surface (e.g., via `pydoc` or type stubs) to ensure no exports were added, removed, or renamed.
