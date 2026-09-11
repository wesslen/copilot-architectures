# AGENTS.md

Operational runbook for this workspace. Follow these steps in order. Do not skip steps and
do not reorder them.

## Environment

- Input data: `data/loan_applications.csv` (read-only)
- Rule definitions: `docs/validation_rules.md`
- Remediation table: `docs/remediation_rules.md`
- Report structure: `docs/report_template.md`
- Test suite: `tests/test_validation.py`
- All generated artifacts go in `output/`. Nothing outside `output/` may be modified.

## Procedure

### Step 1 — Profile

Load `data/loan_applications.csv` and profile it: row count, column names and dtypes,
null counts per column, duplicate `application_id` count, and the distinct formats present in
`application_date`. Record what you observe; do not guess.

### Step 2 — Validate

Read `docs/validation_rules.md` in full. Evaluate **all eight** rules `R1`–`R8` against the
*original* input. For every violation record the pair (rule ID, `application_id`). Violation
counts are counts of distinct `application_id` values. Rules `R6`–`R8` are controls and are
expected to return zero — report `0`, never fabricate findings.

### Step 3 — Remediate

Read `docs/remediation_rules.md` and apply **only** the actions in that table:

- R1 → keep the first occurrence of each duplicated `application_id`, drop later ones
- R2, R3, R5 → drop the row
- R4 → normalize `application_date` to ISO 8601 in place, keep the row
- R6, R7, R8 → no action

Write the result to `output/cleaned_loan_applications.csv`, preserving column names, column
order, and all untouched values exactly.

### Step 4 — Report

Write `output/report.md` using the four section headers from `docs/report_template.md`
verbatim and in order, with the Rule-by-Rule Findings table carrying exactly the columns
`Rule ID | Description | Violation Count | Affected Application IDs`. Include a row for every
rule `R1`–`R8`, including the zero-violation ones.

### Step 5 — Commit message

Write `output/commit_message.txt` containing a single line in Conventional Commits form:
`type(scope): summary`. No body, no trailing blank line beyond one newline.

### Step 6 — Test

Run:

```bash
pytest tests/test_validation.py
```

Write the actual observed result to `output/test_result.txt`, including the pass/fail counts.
If the suite fails, fix `output/cleaned_loan_applications.csv` and re-run — do not edit the
test file, and do not record a result you did not observe.

## Invariants

- Never modify a file outside `output/`.
- Never impute a missing value; the remediation table says drop.
- Never widen the rule set or the remediation set beyond what the docs state.
