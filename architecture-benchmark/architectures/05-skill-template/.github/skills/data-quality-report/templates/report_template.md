# Report Template

The report written to `output/report.md` must use these four section headers **verbatim**,
in this order, and the Rule-by-Rule Findings table must use exactly these columns:

```
# Data Quality & Segment Report

## 1. Summary

## 2. Rule-by-Rule Findings
| Rule ID | Description | Violation Count | Affected Application IDs |
|---|---|---|---|

## 3. Cleaned Dataset Summary

## 4. Recommendations
```

## Section contents

- **1. Summary** — input row count, total violations found, output row count, one or two
  sentences on overall data quality.
- **2. Rule-by-Rule Findings** — one table row per rule `R1`–`R8`, in order. Include rules
  with zero violations (`0` and an empty ID list). List every affected `application_id` in
  the last column, comma-separated.
- **3. Cleaned Dataset Summary** — rows dropped per rule, rows repaired per rule, and the
  final row count of `output/cleaned_loan_applications.csv`.
- **4. Recommendations** — short, concrete suggestions for preventing these defects upstream.
