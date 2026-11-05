"""
core/checks/nulls.py
Null, empty-string, and whitespace-only value detection per column.
Captures row numbers for missing and blank values.
"""
from __future__ import annotations
import pandas as pd
from core.models import NullBlankResult, Severity

MAX_EXAMPLES = 20


def _classify_severity(
    null_pct: float,
    blank_pct: float,
    ws_pct: float,
    is_mandatory: bool,
    high_threshold: float = 20.0,
    medium_threshold: float = 5.0,
) -> Severity:
    combined = null_pct + blank_pct + ws_pct
    if is_mandatory and combined > 0:
        return Severity.CRITICAL
    if combined > high_threshold:
        return Severity.HIGH
    if combined > medium_threshold:
        return Severity.MEDIUM
    if combined > 0:
        return Severity.LOW
    return Severity.INFO


def check_nulls_and_blanks(
    df: pd.DataFrame,
    dataset_name: str = "dataset",
    mandatory_fields: list[str] | None = None,
    high_threshold: float = 20.0,
    medium_threshold: float = 5.0,
) -> NullBlankResult:
    """
    Detect NULL, empty-string, and whitespace-only values per column.
    """
    mandatory = set(mandatory_fields or [])
    total = len(df)
    per_column: list[dict] = []
    all_affected: set[int] = set()

    for col in df.columns:
        series = df[col]
        null_mask = series.isna()
        null_count = int(null_mask.sum())

        non_null = series[~null_mask].astype(str)
        blank_mask = non_null == ""
        blank_count = int(blank_mask.sum())
        ws_only_mask = (non_null.str.strip() == "") & (~blank_mask)
        ws_only_count = int(ws_only_mask.sum())

        all_affected.update(int(idx + 1) for idx in df[null_mask].index)
        all_affected.update(int(idx + 1) for idx in non_null[blank_mask].index)
        all_affected.update(int(idx + 1) for idx in non_null[ws_only_mask].index)

        null_pct = round(100.0 * null_count / total, 2) if total > 0 else 0.0
        blank_pct = round(100.0 * blank_count / total, 2) if total > 0 else 0.0
        ws_pct = round(100.0 * ws_only_count / total, 2) if total > 0 else 0.0

        # Capture sample row numbers (1-indexed)
        sample_null_rows = [int(idx + 1) for idx in df[null_mask].index[:MAX_EXAMPLES]]
        sample_blank_rows = [int(idx + 1) for idx in non_null[blank_mask].index[:MAX_EXAMPLES]]
        sample_ws_rows = [int(idx + 1) for idx in non_null[ws_only_mask].index[:MAX_EXAMPLES]]

        severity = _classify_severity(
            null_pct, blank_pct, ws_pct,
            is_mandatory=(col in mandatory),
            high_threshold=high_threshold,
            medium_threshold=medium_threshold,
        )

        per_column.append({
            "column": col,
            "null_count": null_count,
            "null_pct": null_pct,
            "blank_count": blank_count,
            "blank_pct": blank_pct,
            "whitespace_only_count": ws_only_count,
            "whitespace_only_pct": ws_pct,
            "is_mandatory": col in mandatory,
            "severity": severity.value,
            "sample_null_rows": sample_null_rows,
            "sample_blank_rows": sample_blank_rows,
            "sample_ws_rows": sample_ws_rows,
        })

    return NullBlankResult(
        dataset_name=dataset_name,
        per_column=per_column,
        affected_row_indices=sorted(all_affected),
    )
