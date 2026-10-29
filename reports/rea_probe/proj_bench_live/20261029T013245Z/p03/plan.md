1. **Isolate Dependencies**: Identify the internal logic and state that can be cleanly separated, defining the interface between the new module and the original.
2. **Extract Code**: Move the identified logic into a new module, ensuring it has no circular dependencies with the original.
3. **Update References**: Replace direct calls in the original module with imports from the new module, keeping the original module's public API signature identical.
4. **Verify Behavior**: Run the full test suite to confirm all tests pass and that no behavioral regressions have occurred.
5. **Refine & Commit**: Clean up any unused imports or variables in both modules, then commit the changes.
