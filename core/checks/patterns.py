"""
core/checks/patterns.py
Pattern and naming consistency detection using shape-mask clustering.
Converts values to a generalized mask (e.g. ABC-001 -> AAA-999) and
reports the distribution of pattern clusters per column with row references.
"""
from __future__ import annotations
import re
import pandas as pd
from core.models import PatternResult, Severity

MAX_EXAMPLES = 20

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"[0-9]")


def _to_structural_mask(value: str) -> str:
    if not value:
        return ""
    result = []
    for ch in value:
        if ch.isupper():
            result.append("A")
        elif ch.islower():
            result.append("a")
        elif ch.isdigit():
            result.append("9")
        else:
            result.append(ch)
    return "".join(result)


def _to_case_normalized_mask(value: str) -> str:
    if not value:
        return ""
    result = []
    for ch in value:
        if ch.isalpha():
            result.append("A")
        elif ch.isdigit():
            result.append("9")
        else:
            result.append(ch)
    return "".join(result)


_CODE_HINTS = {"id", "code", "num", "no", "key", "sku", "ref", "vin", "serial", "zip", "postal", "ssn", "ein", "account", "order", "cust"}
_TEXT_HINTS = {"name", "desc", "description", "notes", "comment", "email", "country", "city", "state", "address", "street", "status", "type", "category", "title"}


def _is_likely_code_column(col: str, series: pd.Series) -> bool:
    col_lower = col.lower()
    for th in _TEXT_HINTS:
        if th in col_lower:
            return False
    for ch in _CODE_HINTS:
        if ch in col_lower:
            return True
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return False
    avg_len = non_null.str.len().mean()
    has_spaces = non_null.str.contains(r"\s").mean()
    has_digits = non_null.str.contains(r"\d").mean()
    if avg_len <= 20 and has_spaces < 0.1 and has_digits > 0.3:
        return True
    return False


def check_patterns(
    df: pd.DataFrame,
    include_columns: list[str] | None = None,
    exclude_columns: list[str] | None = None,
    min_cluster_size: int = 2,
    max_cardinality_ratio: float = 0.95,
    dataset_name: str = "dataset",
) -> PatternResult:
    exclude = set(exclude_columns or [])
    per_column: list[dict] = []
    all_affected: set[int] = set()

    for col in df.columns:
        if col in exclude:
            continue
        if include_columns:
            if col not in include_columns:
                continue
        else:
            if not _is_likely_code_column(col, df[col]):
                continue

        series = df[col].dropna().astype(str)
        series = series[series.str.strip() != ""]
        n = len(series)
        if n < min_cluster_size:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            continue

        structural_masks = series.map(_to_structural_mask)
        case_neutral_masks = series.map(_to_case_normalized_mask)

        cluster_counts = structural_masks.value_counts()
        total = len(series)
        dominant_pattern = str(cluster_counts.index[0]) if len(cluster_counts) > 0 else ""

        clusters = []
        for pattern, count in cluster_counts.items():
            if count < min_cluster_size:
                continue
            pct = round(100.0 * count / total, 2)
            pattern_samples = [
                {"row_number": int(idx + 1), "value": str(val)}
                for idx, val in series[structural_masks == pattern].head(5).items()
            ]
            clusters.append({
                "pattern": str(pattern),
                "count": int(count),
                "pct": pct,
                "is_dominant": str(pattern) == dominant_pattern,
                "samples": pattern_samples,
            })

        if len(clusters) <= 1:
            continue

        case_clusters = case_neutral_masks.value_counts()
        has_case_inconsistency = len(case_clusters) < len(cluster_counts)
        has_structural_inconsistency = len(cluster_counts) > 1

        # Capture minority pattern samples
        minority_idx = structural_masks[structural_masks != dominant_pattern].index
        all_affected.update(int(idx + 1) for idx in minority_idx)

        minority_samples = []
        for idx, pat in structural_masks.items():
            if pat != dominant_pattern and len(minority_samples) < MAX_EXAMPLES:
                minority_samples.append({
                    "row_number": int(idx + 1),
                    "value": str(series.loc[idx]),
                    "pattern": str(pat),
                    "dominant_pattern": dominant_pattern,
                })

        dominant_count = int(cluster_counts.get(dominant_pattern, 0))
        inconsistent_count = n - dominant_count

        per_column.append({
            "column": col,
            "clusters": clusters,
            "dominant_pattern": dominant_pattern,
            "has_case_inconsistency": has_case_inconsistency,
            "has_structural_inconsistency": has_structural_inconsistency,
            "total_analyzed": n,
            "inconsistent_count": inconsistent_count,
            "sample_inconsistencies": minority_samples,
            "sample_rows": [s["row_number"] for s in minority_samples],
            "severity": Severity.LOW.value,
        })

    severity = Severity.LOW if per_column else Severity.INFO
    return PatternResult(
        dataset_name=dataset_name,
        per_column=per_column,
        severity=severity,
        affected_row_indices=sorted(all_affected),
    )
