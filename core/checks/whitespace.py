"""
core/checks/whitespace.py
Detect leading, trailing, and multiple internal spaces per text column.
Captures row numbers and problematic values for detailed reporting.
"""
from __future__ import annotations
import pandas as pd
from core.models import WhitespaceResult, Severity

MAX_EXAMPLES = 20


def _is_text_column(series: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)


def check_whitespace(
    df: pd.DataFrame,
    dataset_name: str = "dataset",
) -> WhitespaceResult:
    """
    Detect whitespace anomalies in every text column:
    - Leading spaces
    - Trailing spaces
    - Multiple consecutive internal spaces
    """
    per_column: list[dict] = []
    all_affected: set[int] = set()

    for col in df.columns:
        series = df[col]
        if not _is_text_column(series):
            continue

        str_vals = series.dropna().astype(str)
        str_vals = str_vals[str_vals != ""]
        n = len(str_vals)
        if n == 0:
            continue

        leading_mask = str_vals.str.startswith(" ") | str_vals.str.startswith("\t")
        trailing_mask = str_vals.str.endswith(" ") | str_vals.str.endswith("\t")
        multi_internal_mask = str_vals.str.contains(r"  +", regex=True)

        leading_count = int(leading_mask.sum())
        trailing_count = int(trailing_mask.sum())
        multi_internal_count = int(multi_internal_mask.sum())

        if leading_count + trailing_count + multi_internal_count == 0:
            continue

        sample_mask = leading_mask | trailing_mask | multi_internal_mask
        all_affected.update(int(idx + 1) for idx in str_vals[sample_mask].index)
        sample_indices = str_vals[sample_mask].index[:MAX_EXAMPLES]
        
        sample_issues = []
        for idx in sample_indices:
            val = str(str_vals.loc[idx])
            issues = []
            if leading_mask.loc[idx]:
                issues.append("Leading whitespace")
            if trailing_mask.loc[idx]:
                issues.append("Trailing whitespace")
            if multi_internal_mask.loc[idx]:
                issues.append("Multiple internal spaces")
            
            sample_issues.append({
                "row_number": int(idx + 1),
                "value": repr(val),
                "issue_type": ", ".join(issues),
            })

        per_column.append({
            "column": col,
            "leading_count": leading_count,
            "trailing_count": trailing_count,
            "multi_internal_count": multi_internal_count,
            "total_affected": leading_count + trailing_count + multi_internal_count,
            "affected_rows": int(sample_mask.sum()),
            "sample_values": list(str_vals[sample_mask].head(5)),
            "sample_issues": sample_issues,
            "sample_rows": [int(idx + 1) for idx in sample_indices],
            "severity": Severity.LOW.value,
        })

    severity = Severity.LOW if per_column else Severity.INFO
    return WhitespaceResult(
        dataset_name=dataset_name,
        per_column=per_column,
        severity=severity,
        affected_row_indices=sorted(all_affected),
    )
