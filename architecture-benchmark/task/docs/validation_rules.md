# Validation Rules

Every rule below must be evaluated against `data/loan_applications.csv`. Each rule has a
stable ID (`R1`–`R8`). Findings must be recorded at row level: the rule ID plus the
`application_id` of every affected record.

| Rule | Description |
|---|---|
| **R1** | `application_id` must be unique; flag every row whose ID appears more than once. |
| **R2** | `income` must not be null or missing. |
| **R3** | `income` must be greater than 0. |
| **R4** | `application_date` must be stored in ISO 8601 (`YYYY-MM-DD`) format. |
| **R5** | `application_date` must fall between 2015-01-01 and 2026-09-11 inclusive. |
| **R6** | `credit_score` must be between 300 and 850 inclusive. |
| **R7** | `loan_amount` must be greater than 0. |
| **R8** | `state` must be a valid two-letter US state abbreviation. |

## Counting conventions

- **Violation Count** for a rule is the number of **distinct `application_id` values** that
  violate that rule — not the number of physical rows. For `R1` this means a duplicated ID
  counts once, even though it occupies two or more rows.
- A row may violate more than one rule. Record it under every rule it violates.
- Evaluate each rule independently. Do not let one rule's remediation change another rule's
  finding count: all findings describe the **original** input file.

## R6–R8 are controls

`R6`, `R7`, and `R8` are included as **control rules**. It is expected and correct that they
may report **zero violations** on this dataset. A zero count is a valid result — it is not a
sign that the check was implemented incorrectly, and it is **not** an invitation to invent
findings to fill the table. Report `0` and an empty ID list for any rule with no violations.

## Valid US state abbreviations (R8)

```
AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD
MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC
SD TN TX UT VT VA WA WV WI WY
```
