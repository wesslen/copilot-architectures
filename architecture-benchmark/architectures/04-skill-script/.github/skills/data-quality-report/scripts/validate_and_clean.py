#!/usr/bin/env python3
"""Deterministic implementation of validation rules R1-R8 and the remediation table.

This script derives every finding from the input file itself -- it has no
knowledge of how the data was produced. Run it, then transcribe its output into
the report; do not re-implement the rule logic by hand.

Usage:
    python .github/skills/data-quality-report/scripts/validate_and_clean.py \
        --input data/loan_applications.csv \
        --outdir output

Writes:
    <outdir>/cleaned_loan_applications.csv   remediated dataset
    <outdir>/findings.json                   machine-readable findings
    <outdir>/findings.csv                    one row per (rule_id, application_id)

Also prints a human-readable summary to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
US_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")

NULL_TOKENS = {"", "na", "n/a", "nan", "null", "none", "-"}

DATE_MIN = date(2015, 1, 1)
DATE_MAX = date(2026, 9, 11)

CREDIT_SCORE_MIN = 300
CREDIT_SCORE_MAX = 850

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}

RULES = [
    ("R1", "application_id must be unique", "Keep first occurrence; drop later duplicates"),
    ("R2", "income must not be null or missing", "Drop the row"),
    ("R3", "income must be greater than 0", "Drop the row"),
    ("R4", "application_date must be stored in ISO 8601 (YYYY-MM-DD) format", "Normalize to ISO 8601 in place"),
    ("R5", "application_date must fall between 2015-01-01 and 2026-09-11 inclusive", "Drop the row"),
    ("R6", "credit_score must be between 300 and 850 inclusive", "No action (informational)"),
    ("R7", "loan_amount must be greater than 0", "No action (informational)"),
    ("R8", "state must be a valid two-letter US state abbreviation", "No action (informational)"),
]

RULE_DESCRIPTIONS = {rule_id: description for rule_id, description, _ in RULES}
RULE_REMEDIATIONS = {rule_id: remediation for rule_id, _, remediation in RULES}

DROP_RULES = ("R2", "R3", "R5")


def is_missing(value: str) -> bool:
    return str(value).strip().lower() in NULL_TOKENS


def parse_number(value: str) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(str(value).strip().replace(",", ""))
    except ValueError:
        return None


def parse_date(value: str) -> date | None:
    """Parse an ISO or MM/DD/YYYY date string. Returns None if unparseable."""
    text = str(value).strip()
    if ISO_DATE_RE.match(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    match = US_DATE_RE.match(text)
    if match:
        month, day, year = (int(part) for part in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def evaluate_rules(df: pd.DataFrame) -> dict[str, list[str]]:
    """Return {rule_id: sorted distinct application_ids violating it}."""
    ids = df["application_id"].astype(str)
    findings: dict[str, list[str]] = {rule_id: [] for rule_id, _, _ in RULES}

    # R1 -- application_id appears more than once.
    findings["R1"] = sorted(set(ids[ids.duplicated(keep=False)]))

    r2: set[str] = set()
    r3: set[str] = set()
    r4: set[str] = set()
    r5: set[str] = set()
    r6: set[str] = set()
    r7: set[str] = set()
    r8: set[str] = set()

    for _, row in df.iterrows():
        application_id = str(row["application_id"])

        income_raw = row["income"]
        if is_missing(income_raw):
            r2.add(application_id)
        else:
            income = parse_number(income_raw)
            if income is None or income <= 0:
                r3.add(application_id)

        date_raw = str(row["application_date"]).strip()
        if not ISO_DATE_RE.match(date_raw):
            r4.add(application_id)
        parsed = parse_date(date_raw)
        if parsed is not None and not (DATE_MIN <= parsed <= DATE_MAX):
            r5.add(application_id)

        score = parse_number(row["credit_score"])
        if score is None or not (CREDIT_SCORE_MIN <= score <= CREDIT_SCORE_MAX):
            r6.add(application_id)

        loan_amount = parse_number(row["loan_amount"])
        if loan_amount is None or loan_amount <= 0:
            r7.add(application_id)

        if str(row["state"]).strip().upper() not in US_STATES:
            r8.add(application_id)

    for rule_id, values in (
        ("R2", r2), ("R3", r3), ("R4", r4), ("R5", r5),
        ("R6", r6), ("R7", r7), ("R8", r8),
    ):
        findings[rule_id] = sorted(values)

    return findings


def remediate(df: pd.DataFrame, findings: dict[str, list[str]]) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply the remediation table. Returns (cleaned frame, per-rule drop counts)."""
    counts: dict[str, int] = {}

    before = len(df)
    df = df.drop_duplicates(subset="application_id", keep="first")
    counts["R1"] = before - len(df)

    for rule_id in DROP_RULES:
        targets = set(findings[rule_id])
        before = len(df)
        df = df[~df["application_id"].astype(str).isin(targets)]
        counts[rule_id] = before - len(df)

    # R4 -- normalize the rows that survived the drops.
    non_iso = set(findings["R4"])
    mask = df["application_id"].astype(str).isin(non_iso)
    repaired = 0
    if mask.any():
        def to_iso(value: str) -> str:
            parsed = parse_date(value)
            return parsed.isoformat() if parsed else str(value)

        df.loc[mask, "application_date"] = df.loc[mask, "application_date"].map(to_iso)
        repaired = int(mask.sum())
    counts["R4_repaired"] = repaired

    for rule_id in ("R6", "R7", "R8"):
        counts[rule_id] = 0

    return df.reset_index(drop=True), counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/loan_applications.csv")
    parser.add_argument("--outdir", default="output")
    args = parser.parse_args()

    source = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Read as text so untouched values round-trip exactly.
    df = pd.read_csv(source, dtype=str, keep_default_na=False)
    input_rows = len(df)

    findings = evaluate_rules(df)
    cleaned, counts = remediate(df.copy(), findings)

    cleaned_path = outdir / "cleaned_loan_applications.csv"
    cleaned.to_csv(cleaned_path, index=False)

    rows = []
    for rule_id, description, remediation_action in RULES:
        rows.append(
            {
                "rule_id": rule_id,
                "description": description,
                "remediation": remediation_action,
                "violation_count": len(findings[rule_id]),
                "application_ids": findings[rule_id],
            }
        )

    payload = {
        "input_file": str(source),
        "input_rows": input_rows,
        "output_file": str(cleaned_path),
        "output_rows": len(cleaned),
        "total_violations": sum(len(v) for v in findings.values()),
        "rows_dropped": {
            "R1": counts["R1"],
            "R2": counts["R2"],
            "R3": counts["R3"],
            "R5": counts["R5"],
        },
        "rows_repaired": {"R4": counts["R4_repaired"]},
        "rules": rows,
    }

    (outdir / "findings.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    flat = [
        {"rule_id": rule_id, "description": RULE_DESCRIPTIONS[rule_id], "application_id": application_id}
        for rule_id, _, _ in RULES
        for application_id in findings[rule_id]
    ]
    pd.DataFrame(flat, columns=["rule_id", "description", "application_id"]).to_csv(
        outdir / "findings.csv", index=False
    )

    print(f"input_rows={input_rows}")
    print(f"output_rows={len(cleaned)}")
    print(f"total_violations={payload['total_violations']}")
    print()
    print("| Rule ID | Description | Violation Count | Affected Application IDs |")
    print("|---|---|---|---|")
    for row in rows:
        ids = ", ".join(row["application_ids"]) if row["application_ids"] else ""
        print(f"| {row['rule_id']} | {row['description']} | {row['violation_count']} | {ids} |")
    print()
    print("rows_dropped:", payload["rows_dropped"])
    print("rows_repaired:", payload["rows_repaired"])
    print(f"wrote {cleaned_path}, {outdir / 'findings.json'}, {outdir / 'findings.csv'}")


if __name__ == "__main__":
    main()
