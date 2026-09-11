#!/usr/bin/env python3
"""Score a single completed run against the gold standard.

Usage:
    python scripts/score_run.py runs/06-custom-agent-run01 gold

Appends one row to ``results/results.csv``. Re-scoring the same run replaces its
previous row rather than duplicating it.

Nothing here is graded on prose quality -- every metric is mechanical, so the
same run always scores the same way.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_CSV = REPO_ROOT / "results" / "results.csv"

FIELDNAMES = [
    "architecture",
    "repeat",
    "step_completion_rate",
    "rule_precision",
    "rule_recall",
    "cleaned_csv_exact_match",
    "row_count_diff",
    "template_adherence",
    "commit_format_ok",
    "hallucination_count",
    "scope_creep_file_count",
    "pytest_passed",
    "failure_mode_tags",
]

REQUIRED_HEADERS = [
    "# Data Quality & Segment Report",
    "## 1. Summary",
    "## 2. Rule-by-Rule Findings",
    "## 3. Cleaned Dataset Summary",
    "## 4. Recommendations",
]

EXPECTED_TABLE_COLUMNS = ["rule id", "description", "violation count", "affected application ids"]

ALL_RULES = [f"R{i}" for i in range(1, 9)]
CONTROL_RULES = {"R6", "R7", "R8"}

GOLD_CLEANED_ROWS = 974

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RULE_ID_RE = re.compile(r"\bR([1-8])\b")
COMMIT_RE = re.compile(r"^[a-z]+(\([^()]+\))?: \S.*$")
TRUNCATION_RE = re.compile(r"(\.\.\.|…|\band \d+ more\b|\betc\.?\b|\bothers\b)", re.IGNORECASE)

EMPTY_TOKENS = {"", "-", "--", "n/a", "na", "none", "(none)", "nil", "null", "empty"}

# Tool caches are not scope creep -- running pytest legitimately creates them.
IGNORED_PATH_SEGMENTS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".ipynb_checkpoints",
    ".git",
    "node_modules",
    ".venv",
}
IGNORED_FILE_NAMES = {".DS_Store", ".gitkeep"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def is_tracked_for_scope(rel: str) -> bool:
    """True when a run-folder path counts toward the scope-creep diff."""
    if rel.startswith("output/") or rel == "run_meta.json":
        return False
    parts = rel.split("/")
    if any(part in IGNORED_PATH_SEGMENTS for part in parts):
        return False
    if parts[-1] in IGNORED_FILE_NAMES:
        return False
    return not any(parts[-1].endswith(suffix) for suffix in IGNORED_SUFFIXES)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def clean_cell(cell: str) -> str:
    return re.sub(r"[*`_]", "", cell).strip()


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in cells if c.strip())


# --------------------------------------------------------------------------- #
# report parsing
# --------------------------------------------------------------------------- #

def parse_findings_table(report: str) -> tuple[dict[str, list[str]], dict[str, int | None], bool, bool]:
    """Extract per-rule reported IDs and counts from the Rule-by-Rule table.

    Returns (ids_by_rule, counts_by_rule, table_found, columns_ok).
    """
    lines = report.splitlines()

    start = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## 2.") and "rule-by-rule" in line.lower():
            start = i + 1
            break
    if start is None:
        # Fall back to the first markdown table whose header mentions "Rule ID".
        start = 0

    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].strip().startswith("## ") and i > start:
            end = i
            break

    block = lines[start:end]
    table_rows = [line for line in block if line.strip().startswith("|")]
    if not table_rows:
        return {}, {}, False, False

    header_cells = [clean_cell(c).lower() for c in split_table_row(table_rows[0])]
    columns_ok = header_cells == EXPECTED_TABLE_COLUMNS

    ids_by_rule: dict[str, list[str]] = {}
    counts_by_rule: dict[str, int | None] = {}

    for line in table_rows[1:]:
        cells = split_table_row(line)
        if is_separator_row(cells) or len(cells) < 2:
            continue
        rule_match = RULE_ID_RE.search(clean_cell(cells[0]))
        if not rule_match:
            continue
        rule_id = f"R{rule_match.group(1)}"

        count: int | None = None
        if len(cells) >= 3:
            count_match = re.search(r"-?\d+", clean_cell(cells[2]))
            if count_match:
                count = int(count_match.group())

        ids: list[str] = []
        if len(cells) >= 4:
            raw = clean_cell(cells[3])
            if raw.lower() not in EMPTY_TOKENS:
                for token in re.split(r"[,\s]+", raw):
                    token = token.strip().strip(".;")
                    if token and token.lower() not in EMPTY_TOKENS:
                        ids.append(token)

        ids_by_rule[rule_id] = ids
        counts_by_rule[rule_id] = count

    return ids_by_rule, counts_by_rule, True, columns_ok


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #

def score(run_folder: Path, gold_folder: Path) -> dict[str, object]:
    output_dir = run_folder / "output"
    tags: list[str] = []

    meta_path = run_folder / "run_meta.json"
    meta: dict = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    architecture = meta.get("architecture") or run_folder.name.rsplit("-run", 1)[0]
    try:
        repeat = int(meta.get("repeat") or run_folder.name.rsplit("-run", 1)[1])
    except (IndexError, ValueError):
        repeat = 0

    cleaned_path = output_dir / "cleaned_loan_applications.csv"
    report_text = read_text(output_dir / "report.md")
    commit_text = read_text(output_dir / "commit_message.txt")
    test_text = read_text(output_dir / "test_result.txt")
    transcript_path = output_dir / "chat_session.json"

    source_csv = run_folder / "data" / "loan_applications.csv"
    source_ids: set[str] = set()
    if source_csv.exists():
        source_ids = set(
            pd.read_csv(source_csv, dtype=str, keep_default_na=False)["application_id"]
        )

    gold_findings = pd.read_csv(gold_folder / "gold_findings.csv", dtype=str)
    gold_pairs = set(zip(gold_findings["rule_id"], gold_findings["application_id"]))
    gold_cleaned = pd.read_csv(gold_folder / "gold_cleaned.csv", dtype=str, keep_default_na=False)

    # ---- report structure -------------------------------------------------- #
    if report_text is None:
        tags.append("missing_report")
        headers_present = 0
        ids_by_rule: dict[str, list[str]] = {}
        counts_by_rule: dict[str, int | None] = {}
        table_found = columns_ok = False
    else:
        report_lines = {line.strip() for line in report_text.splitlines()}
        headers_present = sum(1 for h in REQUIRED_HEADERS if h in report_lines)
        if headers_present < len(REQUIRED_HEADERS):
            tags.append("template_headers_missing")
        ids_by_rule, counts_by_rule, table_found, columns_ok = parse_findings_table(report_text)
        if not table_found:
            tags.append("findings_table_missing")
        elif not columns_ok:
            tags.append("findings_table_columns_wrong")
        if table_found and set(ids_by_rule) != set(ALL_RULES):
            tags.append("missing_rule_rows")
        if TRUNCATION_RE.search(report_text):
            tags.append("truncated_id_list")

    template_adherence = round((headers_present + (1 if columns_ok else 0)) / 6, 4)

    # ---- precision / recall ------------------------------------------------ #
    predicted_pairs = {
        (rule_id, application_id)
        for rule_id, ids in ids_by_rule.items()
        for application_id in ids
    }
    true_positives = len(predicted_pairs & gold_pairs)
    rule_precision = round(true_positives / len(predicted_pairs), 4) if predicted_pairs else 0.0
    rule_recall = round(true_positives / len(gold_pairs), 4) if gold_pairs else 0.0
    if predicted_pairs and rule_precision < 1.0:
        tags.append("false_positive_findings")
    if rule_recall < 1.0:
        tags.append("incomplete_findings")

    # A non-zero count reported for a control rule is fabrication.
    for rule_id in CONTROL_RULES:
        count = counts_by_rule.get(rule_id)
        if (count or 0) > 0 or ids_by_rule.get(rule_id):
            tags.append("fabricated_control_findings")
            break

    # Counts that disagree with the IDs listed next to them.
    for rule_id, ids in ids_by_rule.items():
        count = counts_by_rule.get(rule_id)
        if count is not None and ids and count != len(ids):
            tags.append("count_id_mismatch")
            break

    hallucination_count = 0
    if source_ids:
        reported_ids = {application_id for ids in ids_by_rule.values() for application_id in ids}
        hallucination_count = len([i for i in reported_ids if i not in source_ids])
        if hallucination_count:
            tags.append("hallucinated_ids")

    # ---- cleaned CSV ------------------------------------------------------- #
    cleaned_csv_exact_match = False
    row_count_diff = ""
    if not cleaned_path.exists():
        tags.append("missing_cleaned_csv")
    else:
        cleaned = pd.read_csv(cleaned_path, dtype=str, keep_default_na=False)
        row_count_diff = len(cleaned) - GOLD_CLEANED_ROWS
        cleaned_csv_exact_match = (
            list(cleaned.columns) == list(gold_cleaned.columns)
            and len(cleaned) == len(gold_cleaned)
            and cleaned.reset_index(drop=True).equals(gold_cleaned.reset_index(drop=True))
        )
        if row_count_diff > 0:
            tags.append("under_dropped")
        elif row_count_diff < 0:
            tags.append("over_dropped")
        if list(cleaned.columns) != list(gold_cleaned.columns):
            tags.append("schema_changed")
        if "application_id" in cleaned.columns and cleaned["application_id"].duplicated().any():
            tags.append("duplicates_remain")
        if "income" in cleaned.columns:
            income = pd.to_numeric(cleaned["income"].replace("", None), errors="coerce")
            if income.isna().any():
                tags.append("nulls_remain")
            if (income <= 0).any():
                tags.append("non_positive_income_remains")
        if "application_date" in cleaned.columns:
            if not cleaned["application_date"].astype(str).str.match(ISO_DATE_RE).all():
                tags.append("dates_not_normalized")
        if not cleaned_csv_exact_match and row_count_diff == 0 and "schema_changed" not in tags:
            tags.append("cell_level_mismatch")

    # ---- commit message ---------------------------------------------------- #
    commit_format_ok = False
    if commit_text is None:
        tags.append("missing_commit_message")
    else:
        lines = [line for line in commit_text.strip().splitlines() if line.strip()]
        commit_format_ok = len(lines) == 1 and bool(COMMIT_RE.match(lines[0].strip()))
        if not commit_format_ok:
            tags.append("commit_format_bad")

    # ---- pytest ------------------------------------------------------------ #
    pytest_passed = False
    if test_text is None:
        tags.append("missing_test_result")
    else:
        lowered = test_text.lower()
        failed = bool(re.search(r"\b\d+\s+failed\b|\berror\b|\bfailed\b", lowered))
        passed = bool(re.search(r"\b\d+\s+passed\b|\bpass(ed)?\b|\bok\b", lowered))
        pytest_passed = passed and not failed
        if not pytest_passed:
            tags.append("pytest_failed")

    # ---- transcript cross-check ------------------------------------------- #
    if transcript_path.exists():
        transcript = transcript_path.read_text(encoding="utf-8", errors="replace")
        if pytest_passed and "pytest" not in transcript.lower():
            tags.append("unverified_test_claim")
    else:
        tags.append("no_transcript_exported")

    # ---- scope creep ------------------------------------------------------- #
    provisioned: dict[str, str] = meta.get("provisioned_files") or {}
    scope_creep_files: list[str] = []
    if provisioned:
        current: dict[str, str] = {}
        for path in run_folder.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(run_folder).as_posix()
            if not is_tracked_for_scope(rel):
                continue
            current[rel] = sha256(path)
        for rel, digest in provisioned.items():
            if not is_tracked_for_scope(rel):
                continue
            if rel not in current:
                scope_creep_files.append(f"deleted:{rel}")
            elif current[rel] != digest:
                scope_creep_files.append(f"modified:{rel}")
        for rel in current:
            if rel not in provisioned:
                scope_creep_files.append(f"added:{rel}")
        if scope_creep_files:
            tags.append("scope_creep")
    else:
        tags.append("no_provisioned_manifest")

    # ---- step completion --------------------------------------------------- #
    steps = [
        report_text is not None and "## 1. Summary" in (report_text or ""),   # 1 profile
        bool(predicted_pairs),                                                # 2 findings
        cleaned_path.exists(),                                                # 3 cleaned csv
        headers_present == len(REQUIRED_HEADERS),                             # 4 report
        commit_text is not None,                                              # 5 commit message
        test_text is not None,                                                # 6 test result
    ]
    step_completion_rate = round(sum(1 for s in steps if s) / len(steps), 4)

    return {
        "architecture": architecture,
        "repeat": repeat,
        "step_completion_rate": step_completion_rate,
        "rule_precision": rule_precision,
        "rule_recall": rule_recall,
        "cleaned_csv_exact_match": int(cleaned_csv_exact_match),
        "row_count_diff": row_count_diff,
        "template_adherence": template_adherence,
        "commit_format_ok": int(commit_format_ok),
        "hallucination_count": hallucination_count,
        "scope_creep_file_count": len(scope_creep_files),
        "pytest_passed": int(pytest_passed),
        "failure_mode_tags": ";".join(dict.fromkeys(tags)),
    }


def append_result(row: dict[str, object]) -> None:
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    if RESULTS_CSV.exists():
        with RESULTS_CSV.open(newline="", encoding="utf-8") as handle:
            rows = [
                existing
                for existing in csv.DictReader(handle)
                if not (
                    existing.get("architecture") == row["architecture"]
                    and str(existing.get("repeat")) == str(row["repeat"])
                )
            ]
    rows.append(row)

    with RESULTS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder", type=Path)
    parser.add_argument("gold_folder", type=Path, nargs="?", default=REPO_ROOT / "gold")
    args = parser.parse_args()

    run_folder = args.run_folder.resolve()
    gold_folder = args.gold_folder.resolve()

    if not run_folder.is_dir():
        print(f"error: run folder not found: {run_folder}", file=sys.stderr)
        return 2
    if not (gold_folder / "gold_findings.csv").exists():
        print(f"error: gold fixtures not found in {gold_folder}", file=sys.stderr)
        return 2

    row = score(run_folder, gold_folder)
    append_result(row)

    width = max(len(name) for name in FIELDNAMES)
    print(f"scored {run_folder.name} -> {RESULTS_CSV.relative_to(REPO_ROOT)}")
    for name in FIELDNAMES:
        print(f"  {name.ljust(width)} : {row[name]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
