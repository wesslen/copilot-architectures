"""Build the gold-standard fixtures for the benchmark.

This script consumes ``task/data/defect_manifest.json`` directly instead of
re-deriving the defects from the CSV. That guarantees the gold standard can
never drift from the data that was actually injected.

Outputs (all written into this folder):

  * ``gold_findings.csv``  -- one row per violation (rule_id, description,
    application_id, reason). This is the scoring input for precision/recall.
  * ``gold_cleaned.csv``   -- the correctly remediated dataset (974 rows).
  * ``gold_report.md``     -- a human-readable reference report. NOT a scoring
    input; it exists so a reviewer can eyeball the expected numbers.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = Path(__file__).resolve().parent

SOURCE_CSV = ROOT / "task" / "data" / "loan_applications.csv"
MANIFEST = ROOT / "task" / "data" / "defect_manifest.json"

FINDINGS_CSV = GOLD_DIR / "gold_findings.csv"
CLEANED_CSV = GOLD_DIR / "gold_cleaned.csv"
REPORT_MD = GOLD_DIR / "gold_report.md"

EXPECTED_CLEANED_ROWS = 974

RULES = {
    "R1": "application_id must be unique",
    "R2": "income must not be null or missing",
    "R3": "income must be greater than 0",
    "R4": "application_date must be stored in ISO 8601 (YYYY-MM-DD) format",
    "R5": "application_date must fall between 2015-01-01 and 2026-09-11 inclusive",
    "R6": "credit_score must be between 300 and 850 inclusive",
    "R7": "loan_amount must be greater than 0",
    "R8": "state must be a valid two-letter US state abbreviation",
}

MANIFEST_KEYS = {
    "R1": "R1_duplicate_ids",
    "R2": "R2_missing_income_ids",
    "R3": "R3_negative_income_ids",
    "R4": "R4_nonISO_date_ids",
    "R5": "R5_out_of_range_date_ids",
    "R6": "R6_credit_score_violations",
    "R7": "R7_loan_amount_violations",
    "R8": "R8_state_violations",
}

REASONS = {
    "R1": "application_id appears more than once in the source file",
    "R2": "income is blank/null",
    "R3": "income is less than or equal to 0",
    "R4": "application_date is formatted MM/DD/YYYY instead of YYYY-MM-DD",
    "R5": "application_date falls outside 2015-01-01..2026-09-11",
    "R6": "credit_score outside 300..850",
    "R7": "loan_amount less than or equal to 0",
    "R8": "state is not a valid two-letter US state abbreviation",
}

# Rules whose remediation is "drop the row" (see task/docs/remediation_rules.md).
DROP_RULES = ("R2", "R3", "R5")


def load_manifest() -> dict[str, list[str]]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def build_findings(manifest: dict[str, list[str]]) -> pd.DataFrame:
    rows = []
    for rule_id, description in RULES.items():
        for application_id in manifest[MANIFEST_KEYS[rule_id]]:
            rows.append(
                {
                    "rule_id": rule_id,
                    "description": description,
                    "application_id": application_id,
                    "reason": REASONS[rule_id],
                }
            )
    return pd.DataFrame(rows, columns=["rule_id", "description", "application_id", "reason"])


def to_iso(value: str) -> str:
    """Normalize an MM/DD/YYYY date string to ISO 8601."""
    month, day, year = (int(part) for part in value.split("/"))
    return date(year, month, day).isoformat()


def build_cleaned(manifest: dict[str, list[str]]) -> pd.DataFrame:
    # Read everything as text so untouched values round-trip byte-for-byte.
    df = pd.read_csv(SOURCE_CSV, dtype=str, keep_default_na=False)

    # R1 -- keep the first occurrence of each duplicated application_id.
    df = df.drop_duplicates(subset="application_id", keep="first")

    # R2, R3, R5 -- drop the offending rows.
    drop_ids: set[str] = set()
    for rule_id in DROP_RULES:
        drop_ids.update(manifest[MANIFEST_KEYS[rule_id]])
    df = df[~df["application_id"].isin(drop_ids)]

    # R4 -- normalize in place, keep the row.
    non_iso = set(manifest["R4_nonISO_date_ids"])
    mask = df["application_id"].isin(non_iso)
    df.loc[mask, "application_date"] = df.loc[mask, "application_date"].map(to_iso)

    return df.reset_index(drop=True)


def build_report(findings: pd.DataFrame, cleaned: pd.DataFrame, source_rows: int) -> str:
    counts = {rule_id: 0 for rule_id in RULES}
    ids_by_rule = {rule_id: [] for rule_id in RULES}
    for rule_id, group in findings.groupby("rule_id"):
        counts[rule_id] = len(group)
        ids_by_rule[rule_id] = sorted(group["application_id"].tolist())

    table_rows = []
    for rule_id, description in RULES.items():
        ids = ", ".join(ids_by_rule[rule_id]) if ids_by_rule[rule_id] else "(none)"
        table_rows.append(f"| {rule_id} | {description} | {counts[rule_id]} | {ids} |")

    dropped = counts["R1"] + counts["R2"] + counts["R3"] + counts["R5"]
    total_violations = sum(counts.values())

    return f"""# Data Quality & Segment Report

## 1. Summary

The source dataset `data/loan_applications.csv` contains {source_rows} rows across 8 columns.
Applying rules R1-R8 from `docs/validation_rules.md` produced {total_violations} rule
violations covering {len(set(findings["application_id"]))} distinct application IDs. After
applying `docs/remediation_rules.md`, {dropped} rows were dropped and {counts["R4"]} rows were
repaired in place, leaving {len(cleaned)} rows. Data quality issues are concentrated in the
`income` and `application_date` columns; `credit_score`, `loan_amount`, and `state` are clean.

## 2. Rule-by-Rule Findings
| Rule ID | Description | Violation Count | Affected Application IDs |
|---|---|---|---|
{chr(10).join(table_rows)}

## 3. Cleaned Dataset Summary

- Input rows: {source_rows}
- Rows dropped (R1, later duplicate occurrences): {counts["R1"]}
- Rows dropped (R2, missing income): {counts["R2"]}
- Rows dropped (R3, non-positive income): {counts["R3"]}
- Rows dropped (R5, out-of-range date): {counts["R5"]}
- Rows repaired in place (R4, date normalized to ISO 8601): {counts["R4"]}
- Rows dropped for R6/R7/R8: 0 (informational rules, no action)
- **Final row count: {len(cleaned)}**

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
"""


def main() -> None:
    manifest = load_manifest()
    source_rows = len(pd.read_csv(SOURCE_CSV, dtype=str, keep_default_na=False))

    findings = build_findings(manifest)
    cleaned = build_cleaned(manifest)

    if len(cleaned) != EXPECTED_CLEANED_ROWS:
        raise AssertionError(
            f"gold_cleaned.csv must have {EXPECTED_CLEANED_ROWS} rows, got {len(cleaned)}"
        )

    findings.to_csv(FINDINGS_CSV, index=False)
    cleaned.to_csv(CLEANED_CSV, index=False)
    REPORT_MD.write_text(build_report(findings, cleaned, source_rows), encoding="utf-8")

    print(f"wrote {FINDINGS_CSV} ({len(findings)} findings)")
    print(f"wrote {CLEANED_CSV} ({len(cleaned)} rows)")
    print(f"wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
