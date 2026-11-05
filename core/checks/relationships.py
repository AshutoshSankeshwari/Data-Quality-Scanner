"""
core/checks/relationships.py
Cross-dataset referential integrity and orphan record detection.
Captures child row numbers and orphan key values for detailed reporting.
"""
from __future__ import annotations
import pandas as pd
from core.models import RelationshipResult, Severity

MAX_EXAMPLES = 20


def check_relationships(
    parent_df: pd.DataFrame,
    child_df: pd.DataFrame,
    parent_key: str | list[str],
    child_key: str | list[str],
    parent_dataset_name: str = "parent",
    child_dataset_name: str = "child",
    description: str = "",
) -> RelationshipResult:
    p_keys = [parent_key] if isinstance(parent_key, str) else list(parent_key)
    c_keys = [child_key] if isinstance(child_key, str) else list(child_key)

    missing_parent = [k for k in p_keys if k not in parent_df.columns]
    missing_child = [k for k in c_keys if k not in child_df.columns]

    total_child = len(child_df)

    if missing_parent or missing_child:
        msg_parts = []
        if missing_parent:
            msg_parts.append(f"Parent key column(s) not found: {missing_parent}")
        if missing_child:
            msg_parts.append(f"Child key column(s) not found: {missing_child}")
        return RelationshipResult(
            parent_dataset=parent_dataset_name,
            child_dataset=child_dataset_name,
            parent_key=str(p_keys),
            child_key=str(c_keys),
            total_child_records=total_child,
            orphan_count=0,
            orphan_pct=0.0,
            severity=Severity.INFO,
            description=f"Check skipped — {'; '.join(msg_parts)}",
            sample_orphan_records=[],
        )

    if len(p_keys) == 1:
        parent_set = set(parent_df[p_keys[0]].dropna().astype(str))
    else:
        parent_set = set(
            parent_df[p_keys].dropna().astype(str).agg("|".join, axis=1)
        )

    if len(c_keys) == 1:
        child_key_series = child_df[c_keys[0]].dropna().astype(str)
    else:
        child_key_series = child_df[c_keys].dropna().astype(str).agg("|".join, axis=1)

    non_null_mask = child_df[c_keys[0]].notna() if len(c_keys) == 1 else child_df[c_keys].notna().all(axis=1)
    child_non_null_keys = child_key_series[non_null_mask]

    orphan_mask = ~child_non_null_keys.isin(parent_set)
    orphan_count = int(orphan_mask.sum())
    orphan_pct = round(100.0 * orphan_count / total_child, 2) if total_child > 0 else 0.0

    sample_orphan_records = []
    if orphan_count > 0:
        orphan_indices = child_non_null_keys[orphan_mask].index[:MAX_EXAMPLES]
        for idx in orphan_indices:
            key_val = str(child_key_series.loc[idx])
            sample_orphan_records.append({
                "row_number": int(idx + 1),
                "key_value": key_val,
                "child_dataset": child_dataset_name,
                "child_key": ", ".join(c_keys),
                "parent_dataset": parent_dataset_name,
                "parent_key": ", ".join(p_keys),
            })

    if orphan_count == 0:
        severity = Severity.INFO
    elif orphan_pct > 10:
        severity = Severity.CRITICAL
    elif orphan_pct > 2:
        severity = Severity.HIGH
    else:
        severity = Severity.MEDIUM

    p_key_str = p_keys[0] if len(p_keys) == 1 else ", ".join(p_keys)
    c_key_str = c_keys[0] if len(c_keys) == 1 else ", ".join(c_keys)

    affected = [int(idx + 1) for idx in child_non_null_keys[orphan_mask].index]

    return RelationshipResult(
        parent_dataset=parent_dataset_name,
        child_dataset=child_dataset_name,
        parent_key=p_key_str,
        child_key=c_key_str,
        total_child_records=total_child,
        orphan_count=orphan_count,
        orphan_pct=orphan_pct,
        severity=severity,
        description=description or f"{child_dataset_name}.{c_key_str} → {parent_dataset_name}.{p_key_str}",
        sample_orphan_records=sample_orphan_records,
        affected_row_indices=affected,
    )
