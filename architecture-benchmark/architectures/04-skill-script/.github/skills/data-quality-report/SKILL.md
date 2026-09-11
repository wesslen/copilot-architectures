---
name: data-quality-report
description: Use when validating and cleaning loan application data and producing a data-quality report — run the bundled validate_and_clean.py script to apply rules R1–R8 and the remediation table, then transcribe its output into the report and commit message.
---

# Data Quality Report

The rule logic for this task is already implemented. **Do not re-implement it.** Run the
bundled script, then do the orchestration and formatting work around it.

## Bundled resources

- **`scripts/validate_and_clean.py`** — deterministic implementation of rules `R1`–`R8` and
  the full remediation table from `docs/remediation_rules.md`. It reads the CSV, evaluates
  every rule, writes the cleaned dataset, and emits machine-readable findings.

## Steps

### 1. Run the script

From the workspace root:

```bash
python .github/skills/data-quality-report/scripts/validate_and_clean.py \
    --input data/loan_applications.csv \
    --outdir output
```

This writes:

| File | Contents |
|---|---|
| `output/cleaned_loan_applications.csv` | The remediated dataset — **this is the deliverable; do not edit it by hand** |
| `output/findings.json` | `input_rows`, `output_rows`, per-rule violation counts and `application_id` lists, `rows_dropped`, `rows_repaired` |
| `output/findings.csv` | One row per `(rule_id, application_id)` violation |

The script also prints a ready-made Rule-by-Rule Findings table to stdout.

### 2. Read the findings

Read `output/findings.json`. Every number you put in the report must come from that file or
from the script's stdout. Do not recount, re-derive, estimate, or adjust the numbers. If a
rule reports `0` violations, that is the correct answer — report `0` and an empty ID list.

### 3. Write the report

Write `output/report.md` using the headers from `docs/report_template.md` verbatim and in
order:

```
# Data Quality & Segment Report
## 1. Summary
## 2. Rule-by-Rule Findings
## 3. Cleaned Dataset Summary
## 4. Recommendations
```

The findings table columns must be exactly:

```
| Rule ID | Description | Violation Count | Affected Application IDs |
|---|---|---|---|
```

Transcribe one row per rule `R1`–`R8` from `findings.json` (or paste the table the script
printed). Fill section 1 from `input_rows`, `total_violations`, and `output_rows`; fill
section 3 from `rows_dropped` and `rows_repaired`; write section 4 yourself.

### 4. Write the commit message

Write `output/commit_message.txt`: a single line in Conventional Commits form,
`type(scope): summary`.

### 5. Run the tests

Run `pytest tests/test_validation.py` and write the actual observed result to
`output/test_result.txt`.

## Scope

- Write only inside `output/`. Never modify anything outside it, including the bundled script.
- Your job is orchestration and formatting. The rule logic belongs to the script.
