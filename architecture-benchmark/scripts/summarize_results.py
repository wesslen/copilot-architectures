#!/usr/bin/env python3
"""Aggregate results/results.csv into results/results_summary.md.

Usage:
    python scripts/summarize_results.py [--results results/results.csv] [--out results/results_summary.md]

A run counts as a **pass** when all four of these hold:
  * the cleaned CSV matches the gold standard exactly,
  * template adherence is 1.0,
  * pytest passed,
  * no files outside output/ were touched.
"""

from __future__ import annotations

import argparse
import statistics
from collections import Counter
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = REPO_ROOT / "results" / "results.csv"
DEFAULT_OUT = REPO_ROOT / "results" / "results_summary.md"

NUMERIC_COLUMNS = [
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
]


def fmt(value: float | None, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.{digits}f}"


def mean_std(series: pd.Series) -> tuple[float, float]:
    values = [v for v in series.dropna().tolist()]
    if not values:
        return float("nan"), float("nan")
    mean = statistics.fmean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


def is_pass(row: pd.Series) -> bool:
    return bool(
        row["cleaned_csv_exact_match"] == 1
        and row["template_adherence"] == 1.0
        and row["pytest_passed"] == 1
        and row["scope_creep_file_count"] == 0
    )


def tag_counter(series: pd.Series) -> Counter:
    counter: Counter = Counter()
    for value in series.fillna(""):
        for tag in str(value).split(";"):
            tag = tag.strip()
            if tag:
                counter[tag] += 1
    return counter


def build_markdown(df: pd.DataFrame) -> str:
    parts: list[str] = ["# Benchmark Results Summary", ""]
    parts.append(f"Runs scored: **{len(df)}** across **{df['architecture'].nunique()}** architectures.")
    parts.append("")
    parts.append(
        "A run **passes** only when the cleaned CSV matches the gold standard exactly, "
        "template adherence is 1.0, pytest passed, and nothing outside `output/` was touched."
    )
    parts.append("")

    # ---- leaderboard ------------------------------------------------------- #
    parts.append("## Leaderboard")
    parts.append("")
    parts.append(
        "| Architecture | Runs | Pass Rate | Precision (mean ± sd) | Recall (mean ± sd) "
        "| Exact-Match Rate | Steps | Top Failure Mode |"
    )
    parts.append("|---|---|---|---|---|---|---|---|")

    summaries = []
    for architecture, group in df.groupby("architecture", sort=True):
        passes = group.apply(is_pass, axis=1)
        pass_rate = passes.mean()
        p_mean, p_std = mean_std(group["rule_precision"])
        r_mean, r_std = mean_std(group["rule_recall"])
        exact_rate = group["cleaned_csv_exact_match"].mean()
        steps = group["step_completion_rate"].mean()
        tags = tag_counter(group["failure_mode_tags"])
        top_tag = f"`{tags.most_common(1)[0][0]}` ({tags.most_common(1)[0][1]})" if tags else "—"
        summaries.append((architecture, group, passes, pass_rate, p_mean, p_std, r_mean, r_std, exact_rate, steps, tags))
        parts.append(
            f"| `{architecture}` | {len(group)} | {fmt(pass_rate)} "
            f"| {fmt(p_mean)} ± {fmt(p_std)} | {fmt(r_mean)} ± {fmt(r_std)} "
            f"| {fmt(exact_rate)} | {fmt(steps)} | {top_tag} |"
        )
    parts.append("")

    # ---- per-architecture -------------------------------------------------- #
    for (
        architecture, group, passes, pass_rate, p_mean, p_std, r_mean, r_std, exact_rate, steps, tags
    ) in summaries:
        parts.append(f"## `{architecture}`")
        parts.append("")
        parts.append("| Metric | Value |")
        parts.append("|---|---|")
        parts.append(f"| Runs scored | {len(group)} |")
        parts.append(f"| Pass rate | {fmt(pass_rate)} ({int(passes.sum())}/{len(group)}) |")
        parts.append(f"| Rule precision (mean ± sd) | {fmt(p_mean)} ± {fmt(p_std)} |")
        parts.append(f"| Rule recall (mean ± sd) | {fmt(r_mean)} ± {fmt(r_std)} |")
        parts.append(f"| Cleaned-CSV exact-match rate | {fmt(exact_rate)} |")
        parts.append(f"| Step completion rate (mean) | {fmt(steps)} |")
        parts.append(f"| Template adherence (mean) | {fmt(group['template_adherence'].mean())} |")
        parts.append(f"| Commit format OK rate | {fmt(group['commit_format_ok'].mean())} |")
        parts.append(f"| pytest pass rate | {fmt(group['pytest_passed'].mean())} |")
        parts.append(f"| Hallucinated IDs (mean) | {fmt(group['hallucination_count'].mean(), 2)} |")
        parts.append(f"| Scope-creep files (mean) | {fmt(group['scope_creep_file_count'].mean(), 2)} |")
        parts.append(
            f"| Row-count diff vs gold (min / median / max) | "
            f"{fmt(group['row_count_diff'].min(), 0)} / "
            f"{fmt(group['row_count_diff'].median(), 0)} / "
            f"{fmt(group['row_count_diff'].max(), 0)} |"
        )
        parts.append("")
        parts.append("**Most common failure modes**")
        parts.append("")
        if tags:
            parts.append("| Tag | Runs affected |")
            parts.append("|---|---|")
            for tag, count in tags.most_common(5):
                parts.append(f"| `{tag}` | {count} |")
        else:
            parts.append("None recorded.")
        parts.append("")

    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.results.exists():
        print(f"error: {args.results} not found -- run scripts/score_run.py first")
        return 2

    df = pd.read_csv(args.results)
    if df.empty:
        print(f"error: {args.results} has no rows")
        return 2

    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_markdown(df), encoding="utf-8")
    print(f"wrote {args.out} ({len(df)} runs, {df['architecture'].nunique()} architectures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
