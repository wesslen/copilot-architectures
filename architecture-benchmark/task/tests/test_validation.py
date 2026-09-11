"""Structural sanity checks for the agent's own cleaned dataset.

These tests deliberately do NOT compare against the gold standard -- that would
leak the answer key into the agent's workspace. They only assert that whatever
the agent produced is internally consistent with the remediation rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

CLEANED_PATH = Path(__file__).resolve().parents[1] / "output" / "cleaned_loan_applications.csv"

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MIN_ROWS = 900
MAX_ROWS = 1000


@pytest.fixture(scope="module")
def cleaned() -> pd.DataFrame:
    if not CLEANED_PATH.exists():
        pytest.fail(f"cleaned dataset not found at {CLEANED_PATH}")
    return pd.read_csv(CLEANED_PATH)


def test_no_duplicate_application_ids(cleaned: pd.DataFrame) -> None:
    duplicated = cleaned.loc[cleaned["application_id"].duplicated(keep=False), "application_id"]
    assert duplicated.empty, f"duplicate application_id values remain: {sorted(set(duplicated))}"


def test_income_has_no_nulls(cleaned: pd.DataFrame) -> None:
    missing = cleaned.loc[cleaned["income"].isna(), "application_id"]
    assert missing.empty, f"rows with missing income remain: {sorted(missing)}"


def test_income_is_positive(cleaned: pd.DataFrame) -> None:
    income = pd.to_numeric(cleaned["income"], errors="coerce")
    non_positive = cleaned.loc[income <= 0, "application_id"]
    assert non_positive.empty, f"rows with income <= 0 remain: {sorted(non_positive)}"


def test_application_dates_are_iso_8601(cleaned: pd.DataFrame) -> None:
    values = cleaned["application_date"].astype(str)
    bad = cleaned.loc[~values.str.match(ISO_DATE), "application_id"]
    assert bad.empty, f"non-ISO application_date values remain: {sorted(bad)}"

    for value in values:
        try:
            pd.Timestamp(value)
        except ValueError:  # pragma: no cover - defensive
            pytest.fail(f"application_date is not a parseable date: {value}")


def test_row_count_within_expected_bounds(cleaned: pd.DataFrame) -> None:
    assert MIN_ROWS <= len(cleaned) <= MAX_ROWS, (
        f"cleaned row count {len(cleaned)} outside expected range [{MIN_ROWS}, {MAX_ROWS}]"
    )
