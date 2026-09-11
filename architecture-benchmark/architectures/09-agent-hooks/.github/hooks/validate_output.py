#!/usr/bin/env python3
"""Post-session hook: mechanically verify the agent's output.

Checks two things and nothing else:

  1. ``output/report.md`` contains all four required section headers verbatim.
  2. ``output/cleaned_loan_applications.csv`` has no duplicate ``application_id``.

Exits 0 when both pass, 1 otherwise. A non-zero exit fails the agent session.

This is a structural gate, not a correctness oracle -- it deliberately knows
nothing about the expected violation counts, so it cannot leak the answer key.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REPORT = WORKSPACE / "output" / "report.md"
CLEANED = WORKSPACE / "output" / "cleaned_loan_applications.csv"

REQUIRED_HEADERS = [
    "# Data Quality & Segment Report",
    "## 1. Summary",
    "## 2. Rule-by-Rule Findings",
    "## 3. Cleaned Dataset Summary",
    "## 4. Recommendations",
]


def check_report(failures: list[str]) -> None:
    if not REPORT.exists():
        failures.append(f"missing file: {REPORT.relative_to(WORKSPACE)}")
        return

    lines = {line.strip() for line in REPORT.read_text(encoding="utf-8").splitlines()}
    for header in REQUIRED_HEADERS:
        if header not in lines:
            failures.append(f"report.md is missing the required header line: {header!r}")


def check_cleaned(failures: list[str]) -> None:
    if not CLEANED.exists():
        failures.append(f"missing file: {CLEANED.relative_to(WORKSPACE)}")
        return

    with CLEANED.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "application_id" not in reader.fieldnames:
            failures.append("cleaned_loan_applications.csv has no application_id column")
            return
        counts = Counter(row["application_id"] for row in reader)

    duplicates = sorted(value for value, count in counts.items() if count > 1)
    if duplicates:
        shown = ", ".join(duplicates[:10])
        suffix = f" (and {len(duplicates) - 10} more)" if len(duplicates) > 10 else ""
        failures.append(f"duplicate application_id values in cleaned CSV: {shown}{suffix}")


def main() -> int:
    failures: list[str] = []
    check_report(failures)
    check_cleaned(failures)

    if failures:
        print("validate_output: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("validate_output: PASS (4/4 headers present, no duplicate application_id)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
