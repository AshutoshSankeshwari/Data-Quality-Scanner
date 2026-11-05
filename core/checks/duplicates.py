"""
core/checks/duplicates.py
Full-row and key-based duplicate detection.
Captures row-level duplicate pairs and key values for detailed reporting.
"""
from __future__ import annotations
import pandas as pd

from core.models import DuplicateResult, Severity

MAX_EXAMPLES = 20


def check_full_row_duplicates(
    df: pd.DataFrame,
    dataset_name: str = "dataset",
    high_threshold: float = 5.0,
    medium_threshold: float = 1.0,
) -> DuplicateResult:
    """Detect rows that are identical across all columns."""
    total = len(df)
    dup_mask = df.duplicated(keep="first")
    dup_count = int(dup_mask.sum())
    dup_pct = round(100.0 * dup_count / total, 2) if total > 0 else 0.0

    sample_duplicates = []
    if dup_count > 0:
        # Find first occurrences of duplicated rows
        # keep=False marks all duplicates
        all_dup_mask = df.duplicated(keep=False)
        dup_indices = df[dup_mask].index[:MAX_EXAMPLES]
        
        for idx in dup_indices:
            row_vals = df.loc[idx]
            # Find the first row matching this row
            matches = df[all_dup_mask].loc[lambda d: (d == row_vals).all(axis=1)].index
            first_occurrence = int(matches[0] + 1) if len(matches) > 0 else 1
            
            sample_duplicates.append({
                "row_number": int(idx + 1),
                "duplicate_of_row": first_occurrence,
                "type": "Full Row Duplicate",
                "key": "All Columns",
                "values": {str(k): str(v) for k, v in list(row_vals.items())[:5]},
            })

    if dup_count == 0:
        severity = Severity.INFO
    elif dup_pct > high_threshold:
        severity = Severity.HIGH
    elif dup_pct > medium_threshold:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    affected = [int(idx + 1) for idx in df[dup_mask].index]

    return DuplicateResult(
        dataset_name=dataset_name,
        full_row_duplicate_count=dup_count,
        full_row_duplicate_pct=dup_pct,
        key_based_results=[],
        severity=severity,
        sample_duplicates=sample_duplicates,
        affected_row_indices=affected,
    )


def check_key_based_duplicates(
    df: pd.DataFrame,
    key_columns: list[list[str]],
    dataset_name: str = "dataset",
    high_threshold: float = 5.0,
    medium_threshold: float = 1.0,
) -> DuplicateResult:
    """
    Detect duplicates based on one or more configured key column sets.
    """
    total = len(df)
    key_based_results: list[dict] = []
    worst_severity = Severity.INFO
    all_sample_duplicates: list[dict] = []
    all_affected_indices: set[int] = set()

    for cols in key_columns:
        valid_cols = [c for c in cols if c in df.columns]
        if not valid_cols:
            continue

        dup_mask = df.duplicated(subset=valid_cols, keep="first")
        dup_count = int(dup_mask.sum())
        all_affected_indices.update(int(idx + 1) for idx in df[dup_mask].index)
        dup_pct = round(100.0 * dup_count / total, 2) if total > 0 else 0.0

        samples = []
        if dup_count > 0:
            dup_indices = df[dup_mask].index[:MAX_EXAMPLES]
            for idx in dup_indices:
                key_vals = {c: str(df.loc[idx, c]) for c in valid_cols}
                # Find first row matching these key values
                match_cond = pd.Series(True, index=df.index)
                for c in valid_cols:
                    match_cond &= (df[c].astype(str) == key_vals[c])
                matches = df[match_cond].index
                first_occurrence = int(matches[0] + 1) if len(matches) > 0 else 1
                
                sample_item = {
                    "row_number": int(idx + 1),
                    "duplicate_of_row": first_occurrence,
                    "type": f"Key-based ({', '.join(valid_cols)})",
                    "key_columns": valid_cols,
                    "key_values": key_vals,
                }
                samples.append(sample_item)
                all_sample_duplicates.append(sample_item)

        if dup_count == 0:
            sev = Severity.INFO
        elif dup_pct > high_threshold:
            sev = Severity.HIGH
        elif dup_pct > medium_threshold:
            sev = Severity.MEDIUM
        else:
            sev = Severity.LOW

        sev_rank = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
        if sev_rank.index(sev) < sev_rank.index(worst_severity):
            worst_severity = sev

        key_based_results.append({
            "key_columns": valid_cols,
            "duplicate_count": dup_count,
            "duplicate_pct": dup_pct,
            "severity": sev.value,
            "samples": samples,
        })

    full_dup_mask = df.duplicated(keep="first")
    full_dup_count = int(full_dup_mask.sum())
    full_dup_pct = round(100.0 * full_dup_count / total, 2) if total > 0 else 0.0

    return DuplicateResult(
        dataset_name=dataset_name,
        full_row_duplicate_count=full_dup_count,
        full_row_duplicate_pct=full_dup_pct,
        key_based_results=key_based_results,
        severity=worst_severity,
        sample_duplicates=all_sample_duplicates[:MAX_EXAMPLES],
        affected_row_indices=sorted(all_affected_indices),
    )

