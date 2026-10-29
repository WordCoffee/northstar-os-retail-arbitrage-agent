1. **Identify and Isolate the Defect**
   - Locate the specific legal-copy defect within the source file.
   - Extract the exact defective string to ensure precise targeting.

2. **Verify Front Panel Integrity**
   - Compute the cryptographic hash of the current front panel.
   - Record this hash as the baseline for the "unchanged" check.

3. **Apply Targeted Correction**
   - Edit only the identified legal-copy defect.
   - Ensure no other text, formatting, or structural elements are modified.

4. **Validate Constraints**
   - Confirm the corrected legal copy matches the required standard.
   - Re-compute the front panel hash and verify it matches the baseline hash exactly.

5. **Finalize and Report**
   - Save the updated file.
   - Output the quoted defect and the verification result confirming the front panel hash remains unchanged.
