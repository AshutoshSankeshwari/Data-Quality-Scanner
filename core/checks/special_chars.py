"""
core/checks/special_chars.py
Special character detection per field, based on configurable regex rules and anomaly characters.
Captures row numbers and offending values for detailed reporting.
"""
from __future__ import annotations
import re
import pandas as pd
from core.models import SpecialCharResult, Severity

MAX_EXAMPLES = 20

BUILTIN_PRESETS: dict[str, str] = {
    "alpha_numeric_only": r"^[A-Za-z0-9]+$",
    "alpha_numeric_underscore": r"^[A-Za-z0-9_]+$",
    "alpha_numeric_hyphen": r"^[A-Za-z0-9\-]+$",
    "email_format": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    "numeric_only": r"^[0-9]+$",
    "alpha_only": r"^[A-Za-z]+$",
    "phone_format": r"^[\+\-\(\)0-9\s]+$",
    "alpha_numeric_with_basic_punctuation": r"^[A-Za-z0-9\s\.,\-_'\"]+$",
}


def check_special_chars(
    df: pd.DataFrame,
    field_rules: dict[str, str] | None = None,
    character_rule_presets: dict[str, str] | None = None,
    anomaly_characters: list[str] | None = None,
    dataset_name: str = "dataset",
) -> SpecialCharResult:
    """
    Detect values violating configured character rules per field or containing anomaly characters.
    """
    presets = {**BUILTIN_PRESETS, **(character_rule_presets or {})}
    per_column: list[dict] = []
    checked_columns: set[str] = set()
    all_affected: set[int] = set()

    # 1. Field-specific character rules (opt-in)
    for col, rule_name in (field_rules or {}).items():
        if col not in df.columns:
            continue
        if rule_name not in presets:
            continue

        checked_columns.add(col)
        pattern = re.compile(presets[rule_name])
        series = df[col].dropna().astype(str)
        series = series[series.str.strip() != ""]

        if len(series) == 0:
            continue

        violation_mask = ~series.str.match(pattern.pattern)
        violation_count = int(violation_mask.sum())
        violation_pct = round(100.0 * violation_count / len(df), 2)

        if violation_count == 0:
            continue

        all_affected.update(int(idx + 1) for idx in series[violation_mask].index)
        sample_indices = series[violation_mask].index[:MAX_EXAMPLES]
        sample_violations = []
        for idx in sample_indices:
            val = str(series.loc[idx])
            sample_violations.append({
                "row_number": int(idx + 1),
                "value": val,
                "rule": rule_name,
            })

        severity = (
            Severity.HIGH if violation_pct > 10
            else Severity.MEDIUM if violation_pct > 2
            else Severity.LOW
        )

        per_column.append({
            "column": col,
            "rule_name": rule_name,
            "pattern": presets[rule_name],
            "violation_count": violation_count,
            "violation_pct": violation_pct,
            "sample_offenders": list(series[violation_mask].head(5)),
            "sample_violations": sample_violations,
            "sample_rows": [int(idx + 1) for idx in sample_indices],
            "severity": severity.value,
        })

    # 2. Dataset-wide anomaly character scanning across text columns
    if anomaly_characters:
        escaped_chars = "".join(re.escape(c) for c in anomaly_characters)
        anomaly_pattern = re.compile(f"[{escaped_chars}]")

        for col in df.columns:
            if col in checked_columns:
                continue

            if not (pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col])):
                continue

            series = df[col].dropna().astype(str)
            series = series[series.str.strip() != ""]
            if len(series) == 0:
                continue

            violation_mask = series.str.contains(anomaly_pattern, regex=True)
            violation_count = int(violation_mask.sum())
            violation_pct = round(100.0 * violation_count / len(df), 2)

            if violation_count == 0:
                continue

            all_affected.update(int(idx + 1) for idx in series[violation_mask].index)
            sample_indices = series[violation_mask].index[:MAX_EXAMPLES]
            sample_violations = []
            for idx in sample_indices:
                val = str(series.loc[idx])
                found_chars = sorted(list(set(anomaly_pattern.findall(val))))
                sample_violations.append({
                    "row_number": int(idx + 1),
                    "value": val,
                    "offending_chars": ", ".join(found_chars),
                    "rule": f"anomaly_character ({', '.join(found_chars)})",
                })

            severity = (
                Severity.HIGH if violation_pct > 10
                else Severity.MEDIUM if violation_pct > 2
                else Severity.LOW
            )

            per_column.append({
                "column": col,
                "rule_name": "anomaly_characters",
                "rule_display": f"Anomaly Characters ({', '.join(anomaly_characters)})",
                "pattern": f"[{''.join(anomaly_characters)}]",
                "violation_count": violation_count,
                "violation_pct": violation_pct,
                "sample_offenders": list(series[violation_mask].head(5)),
                "sample_violations": sample_violations,
                "sample_rows": [int(idx + 1) for idx in sample_indices],
                "severity": severity.value,
            })

    return SpecialCharResult(
        dataset_name=dataset_name,
        per_column=per_column,
        affected_row_indices=sorted(all_affected),
    )
