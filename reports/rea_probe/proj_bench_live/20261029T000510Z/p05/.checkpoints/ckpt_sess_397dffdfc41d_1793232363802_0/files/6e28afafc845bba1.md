1. **Execute Build**: Run the project's standard build command (e.g., `npm run build`, `mvn clean install`, or `make`) and capture the full output.
2. **Identify Root Cause**: Parse the output to locate the first error message; determine the specific file, line, and underlying cause (e.g., syntax error, missing dependency, type mismatch).
3. **Apply Fix**: Modify the source code or configuration to resolve the identified root cause.
4. **Verify Clean Build**: Re-run the build command and confirm the exit code is `0` with no error output.
5. **Document Resolution**: Record the root cause and the specific fix applied to ensure traceability.
