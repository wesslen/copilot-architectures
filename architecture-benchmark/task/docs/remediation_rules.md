# Remediation Rules

Apply **only** the actions in this table when producing the cleaned dataset. Any other
transformation — imputing values, de-duplicating on columns other than `application_id`,
dropping rows for control-rule violations, reformatting unrelated columns, sorting, or
re-indexing — is out of scope and counts as an error.

| Rule | Action |
|---|---|
| R1 | Keep the first occurrence of each duplicated `application_id`; drop later duplicates |
| R2 | Drop the row (do not impute) |
| R3 | Drop the row |
| R4 | Normalize `application_date` to ISO 8601 — do not drop the row |
| R5 | Drop the row |
| R6, R7, R8 | No action (informational only) |

## Notes

- Column names, column order, and all untouched values must be preserved exactly as they
  appear in the source file.
- R4 is the only in-place repair. Every other remediation is either a row drop or a no-op.
- Drops and the R4 repair are independent: a row is dropped only if it violates R1 (as a
  later duplicate), R2, R3, or R5.
