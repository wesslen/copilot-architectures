"""Generate the deterministic loan-application dataset used by the benchmark.

Running this script produces two files next to it:

  * ``loan_applications.csv``  -- 1000 rows handed to every agent run.
  * ``defect_manifest.json``   -- ground truth listing the exact
    ``application_id`` values affected by each validation rule.

The manifest is the single source of truth for what "correct" looks like.
It must NEVER be copied into ``architectures/`` or ``runs/`` -- doing so
leaks the answer key into the agent's workspace and invalidates the
experiment.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent
CSV_PATH = DATA_DIR / "loan_applications.csv"
MANIFEST_PATH = DATA_DIR / "defect_manifest.json"

SEED = 42

N_BASE_ROWS = 997
N_DUPLICATE_SOURCE = 3
N_MISSING_INCOME = 20
N_NEGATIVE_INCOME = 2
N_NON_ISO_DATE = 50
N_OUT_OF_RANGE_DATE = 1

DATE_START = date(2018, 1, 1)
DATE_END = date(2026, 8, 1)

# R5 bounds -- an out-of-range date must fall strictly outside this window.
VALID_DATE_MIN = date(2015, 1, 1)
VALID_DATE_MAX = date(2026, 9, 11)

INCOME_MEAN = 65000
INCOME_STD = 20000
INCOME_FLOOR = 1000

LOAN_MIN = 5000
LOAN_MAX = 500000

CREDIT_SCORE_MIN = 580
CREDIT_SCORE_MAX = 820

EMPLOYMENT_STATUSES = ["employed", "self-employed", "unemployed", "retired"]

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

FIRST_NAMES = [
    "Avery", "Blake", "Casey", "Dakota", "Emerson", "Finley", "Greer",
    "Harper", "Indigo", "Jordan", "Kendall", "Logan", "Marlowe", "Noel",
    "Oakley", "Payton", "Quinn", "Reese", "Sawyer", "Tatum", "Urban",
    "Vaughn", "Wren", "Xavi", "Yuri", "Zion",
]

LAST_NAMES = [
    "Alvarez", "Bennett", "Castillo", "Donnelly", "Eriksen", "Fontaine",
    "Gallagher", "Hollis", "Ibarra", "Jennings", "Kowalski", "Lindqvist",
    "Mercado", "Nakamura", "Okafor", "Pettersson", "Quintero", "Rasmussen",
    "Sandoval", "Thibodeaux", "Ueda", "Vasquez", "Whitfield", "Xiong",
    "Yamamoto", "Zielinski",
]


def build_base_frame() -> pd.DataFrame:
    """Build the 997 clean base rows."""
    application_ids = [f"APP-{i:06d}" for i in range(1, N_BASE_ROWS + 1)]

    first = np.random.choice(FIRST_NAMES, size=N_BASE_ROWS)
    last = np.random.choice(LAST_NAMES, size=N_BASE_ROWS)
    applicant_name = [f"{f} {l}" for f, l in zip(first, last)]

    raw_income = np.random.normal(INCOME_MEAN, INCOME_STD, size=N_BASE_ROWS)
    income = np.maximum(np.round(raw_income), INCOME_FLOOR).astype(np.int64)

    span_days = (DATE_END - DATE_START).days
    offsets = np.random.randint(0, span_days + 1, size=N_BASE_ROWS)
    application_date = [(DATE_START + timedelta(days=int(o))).isoformat() for o in offsets]

    loan_amount = np.round(np.random.uniform(LOAN_MIN, LOAN_MAX, size=N_BASE_ROWS), 2)
    credit_score = np.random.randint(CREDIT_SCORE_MIN, CREDIT_SCORE_MAX + 1, size=N_BASE_ROWS)
    state = np.random.choice(US_STATES, size=N_BASE_ROWS)
    employment_status = np.random.choice(EMPLOYMENT_STATUSES, size=N_BASE_ROWS)

    return pd.DataFrame(
        {
            "application_id": application_ids,
            "applicant_name": applicant_name,
            "income": income.astype(float),
            "application_date": application_date,
            "loan_amount": loan_amount,
            "credit_score": credit_score,
            "state": state,
            "employment_status": employment_status,
        }
    )


def select_defect_indices() -> dict[str, list[int]]:
    """Pick five mutually exclusive sets of base-row indices."""
    total = (
        N_DUPLICATE_SOURCE
        + N_MISSING_INCOME
        + N_NEGATIVE_INCOME
        + N_NON_ISO_DATE
        + N_OUT_OF_RANGE_DATE
    )
    picked = np.random.choice(N_BASE_ROWS, size=total, replace=False)

    cursor = 0

    def take(n: int) -> list[int]:
        nonlocal cursor
        chunk = sorted(int(i) for i in picked[cursor : cursor + n])
        cursor += n
        return chunk

    selection = {
        "duplicate_source": take(N_DUPLICATE_SOURCE),
        "missing_income": take(N_MISSING_INCOME),
        "negative_income": take(N_NEGATIVE_INCOME),
        "non_iso_date": take(N_NON_ISO_DATE),
        "out_of_range_date": take(N_OUT_OF_RANGE_DATE),
    }

    names = list(selection)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            overlap = set(selection[a]) & set(selection[b])
            if overlap:
                raise AssertionError(f"defect index sets {a} and {b} overlap: {sorted(overlap)}")

    return selection


def apply_defects(df: pd.DataFrame, selection: dict[str, list[int]]) -> pd.DataFrame:
    """Mutate the base frame in place and append the duplicate rows."""
    # R2 -- missing income.
    df.loc[selection["missing_income"], "income"] = np.nan

    # R3 -- negative income.
    for idx in selection["negative_income"]:
        df.at[idx, "income"] = -abs(float(df.at[idx, "income"]))

    # R4 -- same calendar date, non-ISO MM/DD/YYYY string.
    for idx in selection["non_iso_date"]:
        iso = date.fromisoformat(df.at[idx, "application_date"])
        df.at[idx, "application_date"] = f"{iso.month:02d}/{iso.day:02d}/{iso.year:04d}"

    # R5 -- ISO formatted (so it is not also an R4 violation) but outside the
    # allowed window.
    for idx in selection["out_of_range_date"]:
        if np.random.rand() < 0.5:
            bad = VALID_DATE_MIN - timedelta(days=int(np.random.randint(1, 2000)))
        else:
            bad = VALID_DATE_MAX + timedelta(days=int(np.random.randint(1, 2000)))
        df.at[idx, "application_date"] = bad.isoformat()

    # R1 -- exact copies of three existing rows appended at the end.
    duplicates = df.loc[selection["duplicate_source"]].copy()
    df = pd.concat([df, duplicates], ignore_index=True)

    return df


def format_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Render income as whole dollars (blank when missing) before writing."""
    out = df.copy()
    out["income"] = out["income"].map(lambda v: "" if pd.isna(v) else str(int(v)))
    return out


def build_manifest(df: pd.DataFrame, selection: dict[str, list[int]]) -> dict[str, list[str]]:
    ids = df["application_id"]

    def ids_for(key: str) -> list[str]:
        return sorted(str(ids.iat[i]) for i in selection[key])

    return {
        "R1_duplicate_ids": ids_for("duplicate_source"),
        "R2_missing_income_ids": ids_for("missing_income"),
        "R3_negative_income_ids": ids_for("negative_income"),
        "R4_nonISO_date_ids": ids_for("non_iso_date"),
        "R5_out_of_range_date_ids": ids_for("out_of_range_date"),
        # R6-R8 are controls: no violations are injected for them.
        "R6_credit_score_violations": [],
        "R7_loan_amount_violations": [],
        "R8_state_violations": [],
    }


def main() -> None:
    np.random.seed(SEED)

    df = build_base_frame()
    selection = select_defect_indices()
    manifest = build_manifest(df, selection)
    df = apply_defects(df, selection)

    expected_rows = N_BASE_ROWS + N_DUPLICATE_SOURCE
    if len(df) != expected_rows:
        raise AssertionError(f"expected {expected_rows} rows, got {len(df)}")

    format_for_csv(df).to_csv(CSV_PATH, index=False)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {CSV_PATH} ({len(df)} rows)")
    print(f"wrote {MANIFEST_PATH}")
    for rule, affected in manifest.items():
        print(f"  {rule}: {len(affected)}")


if __name__ == "__main__":
    main()
