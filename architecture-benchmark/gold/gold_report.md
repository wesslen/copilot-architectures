# Data Quality & Segment Report

## 1. Summary

The source dataset `data/loan_applications.csv` contains 1000 rows across 8 columns.
Applying rules R1-R8 from `docs/validation_rules.md` produced 76 rule
violations covering 76 distinct application IDs. After
applying `docs/remediation_rules.md`, 26 rows were dropped and 50 rows were
repaired in place, leaving 974 rows. Data quality issues are concentrated in the
`income` and `application_date` columns; `credit_score`, `loan_amount`, and `state` are clean.

## 2. Rule-by-Rule Findings
| Rule ID | Description | Violation Count | Affected Application IDs |
|---|---|---|---|
| R1 | application_id must be unique | 3 | APP-000249, APP-000331, APP-000641 |
| R2 | income must not be null or missing | 20 | APP-000003, APP-000005, APP-000014, APP-000032, APP-000061, APP-000178, APP-000285, APP-000314, APP-000447, APP-000519, APP-000638, APP-000701, APP-000711, APP-000712, APP-000743, APP-000766, APP-000821, APP-000895, APP-000930, APP-000969 |
| R3 | income must be greater than 0 | 2 | APP-000547, APP-000954 |
| R4 | application_date must be stored in ISO 8601 (YYYY-MM-DD) format | 50 | APP-000004, APP-000028, APP-000030, APP-000077, APP-000088, APP-000094, APP-000110, APP-000124, APP-000157, APP-000179, APP-000254, APP-000265, APP-000303, APP-000327, APP-000340, APP-000346, APP-000352, APP-000365, APP-000381, APP-000392, APP-000465, APP-000469, APP-000484, APP-000491, APP-000552, APP-000561, APP-000569, APP-000576, APP-000578, APP-000590, APP-000614, APP-000621, APP-000628, APP-000654, APP-000657, APP-000719, APP-000771, APP-000777, APP-000782, APP-000788, APP-000908, APP-000912, APP-000939, APP-000955, APP-000957, APP-000973, APP-000974, APP-000978, APP-000986, APP-000988 |
| R5 | application_date must fall between 2015-01-01 and 2026-09-11 inclusive | 1 | APP-000165 |
| R6 | credit_score must be between 300 and 850 inclusive | 0 | (none) |
| R7 | loan_amount must be greater than 0 | 0 | (none) |
| R8 | state must be a valid two-letter US state abbreviation | 0 | (none) |

## 3. Cleaned Dataset Summary

- Input rows: 1000
- Rows dropped (R1, later duplicate occurrences): 3
- Rows dropped (R2, missing income): 20
- Rows dropped (R3, non-positive income): 2
- Rows dropped (R5, out-of-range date): 1
- Rows repaired in place (R4, date normalized to ISO 8601): 50
- Rows dropped for R6/R7/R8: 0 (informational rules, no action)
- **Final row count: 974**

## 4. Recommendations

- Enforce a uniqueness constraint on `application_id` at ingestion so duplicate submissions
  are rejected rather than silently appended.
- Make `income` a required, non-negative field in the intake form and reject sentinel or
  negative values at the API boundary.
- Store and transmit all dates as ISO 8601 strings; normalize at the ingestion edge instead of
  accepting locale-specific `MM/DD/YYYY` input.
- Add a plausibility window on `application_date` (not before 2015-01-01, not in the future)
  as a hard validation at write time.
- Schedule this rule set as an automated pre-load check so defects are caught before the data
  reaches downstream segmentation.
