1. **Execute Build**: Run the standard build command (e.g., `npm run build`, `mvn clean install`, or `make`) and capture the full console output.
2. **Identify Root Cause**: Parse the output to locate the first error message; isolate the specific file, line, and error type (e.g., syntax error, missing dependency, type mismatch).
3. **Apply Fix**: Modify the source code or configuration to resolve the identified root cause.
4. **Verify Clean Build**: Re-run the build command; confirm the exit code is `0` and no error messages remain in the output.
