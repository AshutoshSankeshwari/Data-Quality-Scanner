"""
core/profiling/profiler.py
Dataset- and column-level profiling engine.
"""
from __future__ import annotations
import pandas as pd

from core.models import (
    ColumnProfile, DatasetProfile, ColumnType,
)

# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------

_DATE_SAMPLE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y",
    "%d %b %Y", "%d-%b-%Y", "%Y/%m/%d",
]

TOP_N = 10  # Number of top frequent values to retain


def _infer_type(series: pd.Series) -> ColumnType:
    """Infer a high-level column type from a pandas Series."""
    # Drop nulls for type checking
    non_null = series.dropna()
    if len(non_null) == 0:
        return ColumnType.UNKNOWN

    if pd.api.types.is_bool_dtype(series):
        return ColumnType.BOOLEAN
    if pd.api.types.is_integer_dtype(series):
        return ColumnType.INTEGER
    if pd.api.types.is_float_dtype(series):
        return ColumnType.FLOAT
    if pd.api.types.is_datetime64_any_dtype(series):
        return ColumnType.DATE

    # Try numeric coercion
    numeric_attempt = pd.to_numeric(non_null, errors="coerce")
    if numeric_attempt.notna().mean() > 0.9:
        # Check if all are integers in disguise
        if (numeric_attempt.dropna() % 1 == 0).all():
            return ColumnType.INTEGER
        return ColumnType.FLOAT

    # Try date coercion on a sample
    if len(non_null) > 0:
        sample = non_null.astype(str).head(200)
        date_parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        if date_parsed.notna().mean() > 0.7:
            return ColumnType.DATE

    # String with mixed numeric / text?
    if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
        return ColumnType.STRING

    return ColumnType.UNKNOWN


# ---------------------------------------------------------------------------
# Column profiling
# ---------------------------------------------------------------------------

def profile_column(series: pd.Series) -> ColumnProfile:
    """Produce a ColumnProfile for a single pandas Series."""
    total = len(series)
    col_type = _infer_type(series)

    # Null / blank / whitespace-only
    null_mask = series.isna()
    null_count = int(null_mask.sum())

    blank_count = 0
    ws_only_count = 0
    if col_type in (ColumnType.STRING, ColumnType.UNKNOWN, ColumnType.MIXED):
        non_null = series[~null_mask].astype(str)
        blank_mask = non_null == ""
        blank_count = int(blank_mask.sum())
        ws_only_mask = (non_null.str.strip() == "") & (~blank_mask)
        ws_only_count = int(ws_only_mask.sum())

    null_pct = round(100.0 * null_count / total, 2) if total > 0 else 0.0
    blank_pct = round(100.0 * blank_count / total, 2) if total > 0 else 0.0
    ws_pct = round(100.0 * ws_only_count / total, 2) if total > 0 else 0.0

    # Unique count
    unique_count = int(series.nunique(dropna=True))
    cardinality_ratio = round(unique_count / total, 4) if total > 0 else 0.0

    # Top N values
    top_vals = (
        series.dropna()
        .value_counts()
        .head(TOP_N)
        .reset_index()
    )
    top_values = [
        {"value": str(row.iloc[0]), "count": int(row.iloc[1])}
        for _, row in top_vals.iterrows()
    ]

    # Numeric stats
    numeric_min = numeric_max = numeric_mean = numeric_median = numeric_std = None
    if col_type in (ColumnType.INTEGER, ColumnType.FLOAT):
        num = pd.to_numeric(series, errors="coerce").dropna()
        if len(num) > 0:
            numeric_min = float(num.min())
            numeric_max = float(num.max())
            numeric_mean = float(round(num.mean(), 4))
            numeric_median = float(num.median())
            numeric_std = float(round(num.std(), 4)) if len(num) > 1 else 0.0

    # String stats
    str_min_len = str_max_len = None
    if col_type in (ColumnType.STRING, ColumnType.UNKNOWN, ColumnType.MIXED):
        non_null_str = series[~null_mask].astype(str)
        if len(non_null_str) > 0:
            lengths = non_null_str.str.len()
            str_min_len = int(lengths.min())
            str_max_len = int(lengths.max())

    # Date stats
    date_min = date_max = date_invalid_count = None
    if col_type == ColumnType.DATE:
        parsed = pd.to_datetime(series, errors="coerce")
        valid = parsed.dropna()
        if len(valid) > 0:
            date_min = str(valid.min().date())
            date_max = str(valid.max().date())
        date_invalid_count = int(parsed.isna().sum() - null_count)
        date_invalid_count = max(date_invalid_count, 0)

    return ColumnProfile(
        name=str(series.name),
        inferred_type=col_type,
        total_count=total,
        null_count=null_count,
        null_pct=null_pct,
        blank_count=blank_count,
        blank_pct=blank_pct,
        whitespace_only_count=ws_only_count,
        whitespace_only_pct=ws_pct,
        unique_count=unique_count,
        cardinality_ratio=cardinality_ratio,
        top_values=top_values,
        numeric_min=numeric_min,
        numeric_max=numeric_max,
        numeric_mean=numeric_mean,
        numeric_median=numeric_median,
        numeric_std=numeric_std,
        str_min_len=str_min_len,
        str_max_len=str_max_len,
        date_min=date_min,
        date_max=date_max,
        date_invalid_count=date_invalid_count,
    )


# ---------------------------------------------------------------------------
# Dataset profiling
# ---------------------------------------------------------------------------

def profile_dataset(
    df: pd.DataFrame,
    name: str = "dataset",
    file_path: str | None = None,
    file_type: str | None = None,
    is_primary: bool = False,
) -> DatasetProfile:
    """Produce a DatasetProfile for a full DataFrame."""
    row_count = len(df)
    col_count = len(df.columns)

    # Column profiles
    columns = [profile_column(df[col]) for col in df.columns]

    # Full-row duplicates
    dup_count = int(df.duplicated().sum())
    dup_pct = round(100.0 * dup_count / row_count, 2) if row_count > 0 else 0.0

    # Overall null %
    total_cells = row_count * col_count
    total_nulls = int(df.isna().sum().sum())
    overall_null_pct = round(100.0 * total_nulls / total_cells, 2) if total_cells > 0 else 0.0

    # Memory footprint
    try:
        size_bytes = int(df.memory_usage(deep=True).sum())
    except Exception:
        size_bytes = None

    return DatasetProfile(
        name=name,
        row_count=row_count,
        column_count=col_count,
        columns=columns,
        duplicate_row_count=dup_count,
        duplicate_row_pct=dup_pct,
        overall_null_pct=overall_null_pct,
        size_bytes=size_bytes,
        file_path=file_path,
        file_type=file_type,
        is_primary=is_primary,
    )
