"""
core/checks/mandatory_fields.py
Mandatory field validation — detects records missing required fields.
Captures row numbers of failing records for detailed reporting.
"""
from __future__ import annotations
import pandas as pd
from core.models import MandatoryFieldResult, Severity

MAX_EXAMPLES = 20


def check_mandatory_fields(
    df: pd.DataFrame,
    mandatory_fields: list[str],
    dataset_name: str = "dataset",
) -> MandatoryFieldResult:
    """
    Identify records where one or more mandatory fields are null or blank.
    """
    total = len(df)
    existing_fields = [f for f in mandatory_fields if f in df.columns]
    missing_columns = [f for f in mandatory_fields if f not in df.columns]

    per_field: list[dict] = []
    any_fail_mask = pd.Series([False] * total, index=df.index)

    for field in existing_fields:
        series = df[field]
        null_mask = series.isna()
        blank_mask = (~null_mask) & (series.astype(str).str.strip() == "")
        fail_mask = null_mask | blank_mask
        any_fail_mask = any_fail_mask | fail_mask

        missing_count = int(fail_mask.sum())
        missing_pct = round(100.0 * missing_count / total, 2) if total > 0 else 0.0
        sample_rows = [int(idx + 1) for idx in df[fail_mask].index[:MAX_EXAMPLES]]

        per_field.append({
            "field": field,
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "sample_rows": sample_rows,
        })

    for field in missing_columns:
        per_field.append({
            "field": field,
            "missing_count": -1,
            "missing_pct": -1.0,
            "sample_rows": [],
            "warning": f"Column '{field}' not found in dataset — check skipped.",
        })

    failing_record_count = int(any_fail_mask.sum())
    failing_pct = round(100.0 * failing_record_count / total, 2) if total > 0 else 0.0

    severity = (
        Severity.CRITICAL if failing_record_count > 0
        else Severity.INFO
    )

    affected = [int(idx + 1) for idx in df[any_fail_mask].index]

    return MandatoryFieldResult(
        dataset_name=dataset_name,
        mandatory_fields=mandatory_fields,
        failing_record_count=failing_record_count,
        total_records=total,
        failing_pct=failing_pct,
        per_field=per_field,
        severity=severity,
        affected_row_indices=affected,
    )
