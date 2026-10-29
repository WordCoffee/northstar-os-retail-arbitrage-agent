1. **Execute Build**: Run the project's standard build command (e.g., `npm run build` or `mvn clean install`) and capture the full output.
2. **Identify Root Cause**: Isolate the first error message in the log, trace it to the specific file and line, and determine the underlying cause (e.g., syntax error, missing dependency, type mismatch).
3. **Apply Fix**: Modify the source code or configuration to resolve the identified root cause.
4. **Verify Clean Build**: Re-run the build command and confirm the exit code is `0` with no error messages in the output.
