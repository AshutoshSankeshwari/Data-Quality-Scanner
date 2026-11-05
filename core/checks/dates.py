"""
core/checks/dates.py
Date validation — invalid dates, format inconsistencies, impossible dates.
Captures row numbers and invalid values for detailed reporting.
"""
from __future__ import annotations
from datetime import datetime
import calendar
import re
import pandas as pd
from core.models import DateResult, Severity

MAX_EXAMPLES = 20

_IMPOSSIBLE_PATTERNS = [
    re.compile(r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-\.](1[3-9]|[2-9][0-9])\b"),
]


def _try_formats(value: str, formats: list[str]) -> tuple[bool, str | None]:
    for fmt in formats:
        try:
            datetime.strptime(value.strip(), fmt)
            return True, fmt
        except ValueError:
            continue
    return False, None


def _is_impossible_date(value: str) -> bool:
    val = value.strip()
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
        try:
            datetime.strptime(val, fmt)
            return False
        except ValueError as e:
            msg = str(e).lower()
            if "day is out of range" in msg or "month must be in" in msg:
                return True

    match = re.match(r"^(\d{1,4})[\/\-\.](\d{1,4})[\/\-\.](\d{1,4})$", val)
    if match:
        parts = [int(p) for p in match.groups()]
        year_idx = None
        for i, p in enumerate(parts):
            if p >= 1000 and p <= 9999:
                year_idx = i
                break

        if year_idx is not None:
            other_parts = [parts[i] for i in range(3) if i != year_idx]
            p1, p2 = other_parts[0], other_parts[1]
            if p1 > 12 and p2 > 12:
                return True
            if p1 > 31 or p2 > 31 or p1 == 0 or p2 == 0:
                return True
            year = parts[year_idx]
            if year_idx == 0 and 1 <= p1 <= 12:
                max_days = calendar.monthrange(year, p1)[1]
                if p2 > max_days:
                    return True
            elif year_idx == 2:
                if 1 <= p2 <= 12 and (p1 > 12 or p1 <= 31):
                    max_days = calendar.monthrange(year, p2)[1]
                    if p1 > max_days:
                        return True
                elif 1 <= p1 <= 12 and (p2 > 12 or p2 <= 31):
                    max_days = calendar.monthrange(year, p1)[1]
                    if p2 > max_days:
                        return True
    return False


def _date_column_heuristic(col_name: str, hints: list[str]) -> bool:
    col_lower = col_name.lower()
    return any(h.lower() in col_lower for h in hints)


def check_dates(
    df: pd.DataFrame,
    date_columns: list[str] | None = None,
    accepted_formats: list[str] | None = None,
    date_column_hints: list[str] | None = None,
    dataset_name: str = "dataset",
) -> DateResult:
    default_formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y",
        "%d %b %Y", "%d-%b-%Y", "%Y/%m/%d", "%m-%d-%Y",
    ]
    formats = accepted_formats or default_formats
    hints = date_column_hints or ["date", "_dt", "_at", "_on", "created", "updated",
                                   "modified", "birth", "expiry", "expire", "timestamp"]

    if date_columns:
        cols_to_check = [c for c in date_columns if c in df.columns]
    else:
        cols_to_check = [c for c in df.columns if _date_column_heuristic(c, hints)]

    per_column: list[dict] = []
    all_affected: set[int] = set()

    for col in cols_to_check:
        series = df[col].dropna().astype(str)
        series = series[series.str.strip() != ""]
        n = len(series)
        if n == 0:
            continue

        valid_count = 0
        invalid_count = 0
        impossible_count = 0
        format_hits: dict[str, int] = {}
        invalid_samples: list[str] = []
        sample_invalid_details: list[dict] = []

        for idx, val in series.items():
            is_valid, matched_fmt = _try_formats(val, formats)
            if is_valid and matched_fmt:
                valid_count += 1
                format_hits[matched_fmt] = format_hits.get(matched_fmt, 0) + 1
            else:
                is_impossible = _is_impossible_date(val)
                if is_impossible:
                    impossible_count += 1
                invalid_count += 1
                all_affected.add(int(idx + 1))
                
                if len(sample_invalid_details) < MAX_EXAMPLES:
                    sample_invalid_details.append({
                        "row_number": int(idx + 1),
                        "value": str(val),
                        "reason": "Impossible calendar date" if is_impossible else "Unrecognized date format",
                    })
                if len(invalid_samples) < 5:
                    invalid_samples.append(str(val))

        invalid_pct = round(100.0 * invalid_count / n, 2) if n > 0 else 0.0
        has_inconsistency = len(format_hits) > 1

        format_clusters = [
            {"format": fmt, "count": cnt, "pct": round(100.0 * cnt / n, 2)}
            for fmt, cnt in sorted(format_hits.items(), key=lambda x: -x[1])
        ]
        dominant_format = format_clusters[0]["format"] if format_clusters else None

        if invalid_count == 0 and not has_inconsistency:
            severity = Severity.INFO
        elif impossible_count > 0 or invalid_pct > 10:
            severity = Severity.HIGH
        elif has_inconsistency:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        per_column.append({
            "column": col,
            "total_checked": n,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "invalid_pct": invalid_pct,
            "impossible_date_count": impossible_count,
            "format_clusters": format_clusters,
            "dominant_format": dominant_format,
            "has_inconsistency": has_inconsistency,
            "invalid_samples": invalid_samples,
            "sample_invalid_details": sample_invalid_details,
            "sample_rows": [d["row_number"] for d in sample_invalid_details],
            "severity": severity.value,
        })

    return DateResult(
        dataset_name=dataset_name,
        per_column=per_column,
        affected_row_indices=sorted(all_affected),
    )
