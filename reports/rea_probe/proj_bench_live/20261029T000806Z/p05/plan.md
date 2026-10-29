1. **Reproduce**: Execute the standard build command (e.g., `npm run build` or `mvn clean install`) and capture the full terminal output.
2. **Identify**: Parse the output to locate the first error message, noting the specific file, line number, and error code.
3. **Diagnose**: Inspect the source code at the identified location to determine the root cause (e.g., syntax error, missing dependency, type mismatch).
4. **Remediate**: Apply the minimal code change required to resolve the root cause.
5. **Verify**: Re-run the build command; confirm the exit code is `0` and no errors are reported.
