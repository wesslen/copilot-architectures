---
name: data-quality-report
description: Use when validating and cleaning loan application data and producing a data-quality report — profiling a dataset against numbered validation rules (R1–R8), applying a documented remediation table, writing a cleaned CSV, and writing a report from the bundled report template.
---

# Data Quality Report

A procedure for turning a raw loan-application extract into a validated finding set, a
cleaned dataset, and a report that matches the bundled template exactly.

## Bundled resources

- **`templates/report_template.md`** — the authoritative report structure, shipped with this
  skill. Read it and copy its headers and table columns verbatim. It is loaded with the skill,
  so you do not need to go looking for a template elsewhere in the workspace.

## Inputs

| Path | Role |
|---|---|
| `data/loan_applications.csv` | Read-only source data |
| `docs/validation_rules.md` | Rules `R1`–`R8` |
| `docs/remediation_rules.md` | Rule → remediation action table |
| `tests/test_validation.py` | Structural checks on your output |

Everything you write goes in `output/`. Do not modify any file outside `output/`.

## Steps

### 1. Profile the dataset

Load the CSV and record row count, columns, per-column null counts, duplicate
`application_id` count, and the date formats present in `application_date`.

### 2. Apply all eight rules

Read `docs/validation_rules.md` in full and evaluate every rule `R1`–`R8` against the
**original** input. Record the pair (rule ID, `application_id`) for every violation.

- Violation counts are counts of distinct `application_id` values, not physical rows.
- `R6`–`R8` are controls. Zero violations is the expected, correct answer for them. Report
  `0` with an empty ID list. Never invent findings to fill the table.
- A row may violate more than one rule; record it under each.

### 3. Write the cleaned CSV

Apply **only** the actions in `docs/remediation_rules.md`:

- R1 → keep the first occurrence of each duplicated `application_id`; drop later duplicates
- R2 → drop the row (do not impute)
- R3 → drop the row
- R4 → normalize `application_date` to ISO 8601 in place; keep the row
- R5 → drop the row
- R6, R7, R8 → no action

Write `output/cleaned_loan_applications.csv`, preserving column names, column order, and all
untouched values exactly as they appear in the source.

### 4. Write the report from the bundled template

Open `templates/report_template.md` from this skill folder. Reproduce its four section
headers verbatim and in order, and its findings table columns exactly:

```
| Rule ID | Description | Violation Count | Affected Application IDs |
|---|---|---|---|
```

Fill each section with real numbers from step 2 and step 3. Include one table row per rule
`R1`–`R8`, in order, including the zero-violation rules. Write the result to
`output/report.md`.

### 5. Write the commit message

Write `output/commit_message.txt`: a single line in Conventional Commits form,
`type(scope): summary`.

### 6. Run the tests

Run `pytest tests/test_validation.py` and write the actual observed result to
`output/test_result.txt`. If it fails, fix your cleaned CSV and re-run. Never edit the test
file and never record an unobserved result.

## Do not

- Improvise a report structure when the bundled template is right there.
- Impute missing values — the remediation table says drop.
- Apply any remediation not in `docs/remediation_rules.md`.
- Write anywhere outside `output/`.
