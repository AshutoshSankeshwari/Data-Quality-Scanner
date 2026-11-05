"""
reports/summary_builder.py
Shared issue aggregation and detailed problem extractor for HTML, Excel, and JSON reporters.
Provides both rich technical issue details and concise human-readable executive summary text.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Any, Optional
import pandas as pd
from core.models import AnalysisResult

MAX_REPORT_EXAMPLES = 20
MAX_SUMMARY_CONCISE_EXAMPLES = 5


@dataclass
class NormalizedIssueRecord:
    """Shared normalized representation of a single problematic row-level record/value."""
    row_number: int | None
    field: str
    value: Any
    issue: str
    dataset: str = ""
    duplicate_of_row: int | None = None
    key_columns: list[str] = field(default_factory=list)
    key_values: dict[str, Any] = field(default_factory=dict)
    pattern: str | None = None
    dominant_pattern: str | None = None
    character: str | None = None
    reason: str | None = None
    record_data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "row_number": self.row_number,
            "field": self.field,
            "value": self.value,
            "issue": self.issue,
        }
        if self.dataset:
            d["dataset"] = self.dataset
        if self.duplicate_of_row is not None:
            d["duplicate_of_row"] = self.duplicate_of_row
        if self.key_columns:
            d["key_columns"] = self.key_columns
        if self.key_values:
            d["key_values"] = self.key_values
        if self.pattern is not None:
            d["pattern"] = self.pattern
        if self.dominant_pattern is not None:
            d["dominant_pattern"] = self.dominant_pattern
        if self.character is not None:
            d["character"] = self.character
        if self.reason is not None:
            d["reason"] = self.reason
        if self.record_data is not None:
            d["record_data"] = self.record_data
        return d


def _normalize_datasets(
    datasets: list[tuple[str, Any]] | dict[str, Any] | pd.DataFrame | None,
    result: AnalysisResult | None = None,
) -> dict[str, pd.DataFrame]:
    """Convert input datasets into a name -> DataFrame dictionary."""
    dfs: dict[str, pd.DataFrame] = {}
    if datasets is None:
        return dfs
    if isinstance(datasets, pd.DataFrame):
        primary_name = result.primary_dataset().name if result and result.primary_dataset() else "dataset"
        dfs[primary_name] = datasets
        return dfs
    if isinstance(datasets, dict):
        for k, v in datasets.items():
            if isinstance(v, pd.DataFrame):
                dfs[k] = v
        return dfs
    if isinstance(datasets, (list, tuple)):
        for item in datasets:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                name, df = item
                if isinstance(df, pd.DataFrame):
                    dfs[str(name)] = df
    return dfs


def _get_df_for_dataset(dfs: dict[str, pd.DataFrame], dataset_name: str) -> pd.DataFrame | None:
    """Retrieve DataFrame for a dataset name, with single-dataset fallback."""
    if dataset_name in dfs:
        return dfs[dataset_name]
    if len(dfs) == 1:
        return next(iter(dfs.values()))
    return None


def _resolve_verified_source_record(
    df: pd.DataFrame | None,
    row_number: int | None,
    field_name: str | None = None,
    is_missing_check: bool = False,
) -> tuple[Any, dict[str, Any] | None]:
    """
    Unambiguously resolve a source record from df using exact check semantics.
    All checks define row_number = int(idx + 1) where idx is from df.index.
    If is_missing_check is True, verifies that df.loc[idx, field_name] is actually null/blank.
    Does NOT guess with arbitrary heuristic fallback.
    Returns: (raw_value, record_dict)
    """
    if df is None or row_number is None or not isinstance(row_number, int):
        return None, None

    expected_idx = row_number - 1

    # 1. Exact unique match in df.index
    if expected_idx in df.index and not df.index.has_duplicates:
        try:
            row = df.loc[expected_idx]
            if isinstance(row, pd.Series):
                val = row[field_name] if (field_name and field_name in row) else None
                if is_missing_check and field_name and field_name in row:
                    if not (pd.isna(val) or str(val).strip() == ""):
                        return None, None
                raw_val = None if pd.isna(val) else val
                rec_dict = {str(k): (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
                return raw_val, rec_dict
        except Exception:
            return None, None

    # 2. Positional lookup ONLY if df.index is a standard 0-based RangeIndex
    if isinstance(df.index, pd.RangeIndex) and df.index.start == 0 and df.index.step == 1:
        if 0 <= expected_idx < len(df):
            try:
                row = df.iloc[expected_idx]
                val = row[field_name] if (field_name and field_name in row) else None
                if is_missing_check and field_name and field_name in row:
                    if not (pd.isna(val) or str(val).strip() == ""):
                        return None, None
                raw_val = None if pd.isna(val) else val
                rec_dict = {str(k): (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
                return raw_val, rec_dict
            except Exception:
                return None, None

    return None, None


def _format_example_entry(rec: dict[str, Any]) -> str:
    """Format a single issue record into a standardized presentation string."""
    r = f"Row {rec['row_number']}" if rec.get("row_number") is not None else "Row ?"
    f = str(rec.get("field", ""))
    val = rec.get("value")
    if val is None:
        v_str = '""' if rec.get("issue") == 'Empty string value ("")' else "NULL"
    elif isinstance(val, str):
        v_str = f'"{val}"'
    else:
        v_str = str(val)
    iss = str(rec.get("issue", ""))
    parts = [r]
    if f:
        parts.append(f)
    parts.append(v_str)
    if iss:
        parts.append(iss)
    return " | ".join(parts)


def build_issue_summary_counts(result: AnalysisResult) -> dict[str, int]:
    """Calculate exact problem counts by check category and total."""
    dup_count = sum(
        dr.full_row_duplicate_count + sum(kb.get("duplicate_count", 0) for kb in dr.key_based_results)
        for dr in result.duplicate_results
    )
    
    null_blank_count = sum(
        sum(c.get("null_count", 0) + c.get("blank_count", 0) + c.get("whitespace_only_count", 0) for c in nr.per_column)
        for nr in result.null_blank_results
    )
    
    mandatory_count = sum(
        mf.failing_record_count for mf in result.mandatory_field_results
    )
    
    whitespace_count = sum(
        sum(c.get("leading_count", 0) + c.get("trailing_count", 0) + c.get("multi_internal_count", 0) for c in wr.per_column)
        for wr in result.whitespace_results
    )
    
    special_char_count = sum(
        sum(c.get("violation_count", 0) for c in sc.per_column)
        for sc in result.special_char_results
    )
    
    date_count = sum(
        sum(c.get("invalid_count", 0) for c in dr.per_column)
        for dr in result.date_results
    )
    
    pattern_count = sum(
        sum(c.get("inconsistent_count", len(c.get("sample_inconsistencies", []))) for c in pr.per_column)
        for pr in result.pattern_results
    )
    
    relationship_count = sum(
        rr.orphan_count for rr in result.relationship_results
    )
    
    total_problems = (
        dup_count + null_blank_count + mandatory_count + whitespace_count
        + special_char_count + date_count + pattern_count + relationship_count
    )
    
    return {
        "total_problems": total_problems,
        "duplicates": dup_count,
        "nulls_and_blanks": null_blank_count,
        "mandatory_fields": mandatory_count,
        "whitespace": whitespace_count,
        "special_chars": special_char_count,
        "dates": date_count,
        "patterns": pattern_count,
        "relationships": relationship_count,
    }


def count_affected_rows(result: AnalysisResult) -> Optional[int]:
    """
    Return exact unique input rows affected by at least one data-quality issue.

    1. If result.affected_rows_count is already set, returns it directly (O(1)).
    2. Otherwise, calculates the union of (dataset_name, row_number) pairs from in-memory
       check results with complete affected_row_indices.
    3. For legacy scans restored from SQLite where affected_rows_count is absent:
       - Returns 0 if total issues == 0.
       - Returns None if total issues > 0 (prevents misleading 0, triggers '—' fallback).
    """
    if getattr(result, "affected_rows_count", None) is not None:
        return result.affected_rows_count

    seen: set[tuple[str, int]] = set()
    has_any_source = False

    for dr in getattr(result, "duplicate_results", []):
        indices = getattr(dr, "affected_row_indices", [])
        if indices:
            has_any_source = True
            ds = getattr(dr, "dataset_name", "dataset")
            for r in indices:
                if r is not None and r > 0:
                    seen.add((ds, int(r)))

    for mf in getattr(result, "mandatory_field_results", []):
        indices = getattr(mf, "affected_row_indices", [])
        if indices:
            has_any_source = True
            ds = getattr(mf, "dataset_name", "dataset")
            for r in indices:
                if r is not None and r > 0:
                    seen.add((ds, int(r)))

    for nr in getattr(result, "null_blank_results", []):
        indices = getattr(nr, "affected_row_indices", [])
        if indices:
            has_any_source = True
            ds = getattr(nr, "dataset_name", "dataset")
            for r in indices:
                if r is not None and r > 0:
                    seen.add((ds, int(r)))

    for wr in getattr(result, "whitespace_results", []):
        indices = getattr(wr, "affected_row_indices", [])
        if indices:
            has_any_source = True
            ds = getattr(wr, "dataset_name", "dataset")
            for r in indices:
                if r is not None and r > 0:
                    seen.add((ds, int(r)))

    for sc in getattr(result, "special_char_results", []):
        indices = getattr(sc, "affected_row_indices", [])
        if indices:
            has_any_source = True
            ds = getattr(sc, "dataset_name", "dataset")
            for r in indices:
                if r is not None and r > 0:
                    seen.add((ds, int(r)))

    for pr in getattr(result, "pattern_results", []):
        indices = getattr(pr, "affected_row_indices", [])
        if indices:
            has_any_source = True
            ds = getattr(pr, "dataset_name", "dataset")
            for r in indices:
                if r is not None and r > 0:
                    seen.add((ds, int(r)))

    for dt in getattr(result, "date_results", []):
        indices = getattr(dt, "affected_row_indices", [])
        if indices:
            has_any_source = True
            ds = getattr(dt, "dataset_name", "dataset")
            for r in indices:
                if r is not None and r > 0:
                    seen.add((ds, int(r)))

    for rr in getattr(result, "relationship_results", []):
        indices = getattr(rr, "affected_row_indices", [])
        if indices:
            has_any_source = True
            ds = getattr(rr, "child_dataset", "dataset")
            for r in indices:
                if r is not None and r > 0:
                    seen.add((ds, int(r)))

    if has_any_source:
        return len(seen)

    # Check if scan had any issues at all
    has_issues = False
    if getattr(result, "score", None):
        sc = result.score
        total_score_issues = (
            getattr(sc, "blocker_count", 0)
            + getattr(sc, "high_count", 0)
            + getattr(sc, "medium_count", 0)
            + getattr(sc, "low_count", 0)
        )
        if total_score_issues > 0:
            has_issues = True

    if not has_issues:
        for cr_list_attr in [
            "duplicate_results", "mandatory_field_results", "null_blank_results",
            "whitespace_results", "special_char_results", "pattern_results",
            "date_results", "relationship_results",
        ]:
            for check_res in getattr(result, cr_list_attr, []):
                if hasattr(check_res, "has_issues") and check_res.has_issues():
                    has_issues = True
                    break
            if has_issues:
                break

    if has_issues:
        return None

    return 0


def _format_row_range(row_list: list[int], max_items: int = 5) -> str:
    """Format a list of row numbers into a concise string."""
    if not row_list:
        return ""
    if len(row_list) <= max_items:
        return f"Rows {', '.join(str(r) for r in row_list)}"
    return f"Rows {', '.join(str(r) for r in row_list[:max_items])}..."


def extract_detailed_issues(
    result: AnalysisResult,
    datasets: list[tuple[str, Any]] | dict[str, Any] | pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """
    Extract flat, structured issue details across all check types
    with row numbers, sample values, and truncation info.
    Resolves verified source records when datasets are provided.
    """
    dfs = _normalize_datasets(datasets, result)
    issues: list[dict[str, Any]] = []

    # 1. Duplicates
    for dr in result.duplicate_results:
        ds_df = _get_df_for_dataset(dfs, dr.dataset_name)

        if dr.full_row_duplicate_count > 0:
            sample_rows = [d.get("row_number") for d in dr.sample_duplicates if d.get("row_number")]
            details: list[dict[str, Any]] = []
            for d in dr.sample_duplicates[:MAX_REPORT_EXAMPLES]:
                r = d.get("row_number")
                dup_of = d.get("duplicate_of_row")
                _, rec_dict = _resolve_verified_source_record(ds_df, r)
                carried_vals = d.get("values", {})
                val_summary = ", ".join(f"{k}={v}" for k, v in list(carried_vals.items())[:3]) if carried_vals else f"Duplicate of row {dup_of}"
                rec = {
                    "row_number": r,
                    "field": "All Columns",
                    "value": val_summary,
                    "issue": f"Duplicate of row {dup_of}",
                    "dataset": dr.dataset_name,
                    "duplicate_of_row": dup_of,
                }
                if rec_dict:
                    rec["record_data"] = rec_dict
                details.append(rec)

            examples_str = "; ".join(_format_example_entry(d) for d in details)
            if details:
                summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
            else:
                summary_ex = f"{dr.full_row_duplicate_count} duplicate rows detected"

            issues.append({
                "category": "Duplicates",
                "dataset": dr.dataset_name,
                "column": "All Columns (Full Row)",
                "issue_type": "Full-row duplicate records",
                "severity": dr.severity.value if hasattr(dr.severity, "value") else str(dr.severity),
                "affected_count": dr.full_row_duplicate_count,
                "affected_pct": dr.full_row_duplicate_pct,
                "sample_rows": sample_rows,
                "examples_text": examples_str,
                "summary_examples_text": summary_ex,
                "truncation_note": f"Showing first {min(len(sample_rows), MAX_REPORT_EXAMPLES)} of {dr.full_row_duplicate_count} records" if dr.full_row_duplicate_count > MAX_REPORT_EXAMPLES else "",
                "details": details,
            })
            
        for kb in dr.key_based_results:
            cnt = kb.get("duplicate_count", 0)
            if cnt > 0:
                cols = ", ".join(kb.get("key_columns", []))
                key_cols = kb.get("key_columns", [])
                samples = kb.get("samples", [])
                sample_rows = [s.get("row_number") for s in samples if s.get("row_number")]

                details = []
                for s in samples[:MAX_REPORT_EXAMPLES]:
                    r = s.get("row_number")
                    dup_of = s.get("duplicate_of_row")
                    key_vals = s.get("key_values", {})
                    field_name = key_cols[0] if len(key_cols) == 1 else cols
                    val = key_vals.get(field_name) if len(key_cols) == 1 else ", ".join(f"{k}={v}" for k, v in key_vals.items())
                    _, rec_dict = _resolve_verified_source_record(ds_df, r)
                    rec = {
                        "row_number": r,
                        "field": field_name,
                        "value": val,
                        "issue": f"Duplicate of row {dup_of}",
                        "dataset": dr.dataset_name,
                        "duplicate_of_row": dup_of,
                        "key_columns": key_cols,
                        "key_values": key_vals,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    summary_ex = f"{cnt} duplicate {cols} records detected"

                issues.append({
                    "category": "Duplicates",
                    "dataset": dr.dataset_name,
                    "column": cols,
                    "issue_type": f"Key-based duplicates ({cols})",
                    "severity": kb.get("severity", "Info"),
                    "affected_count": cnt,
                    "affected_pct": kb.get("duplicate_pct", 0.0),
                    "sample_rows": sample_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(samples), MAX_REPORT_EXAMPLES)} of {cnt} records" if cnt > MAX_REPORT_EXAMPLES else "",
                    "details": details,
                })

    # 2. Mandatory Fields
    for mf in result.mandatory_field_results:
        ds_df = _get_df_for_dataset(dfs, mf.dataset_name)
        for pf in mf.per_field:
            cnt = pf.get("missing_count", 0)
            if cnt > 0:
                col = pf.get("field", "")
                s_rows = pf.get("sample_rows", [])
                details = []
                for r in s_rows[:MAX_REPORT_EXAMPLES]:
                    raw_val, rec_dict = _resolve_verified_source_record(ds_df, r, field_name=col, is_missing_check=True)
                    if rec_dict is not None:
                        val = raw_val
                        if val is None:
                            iss_desc = "Mandatory field is blank"
                        elif val == "":
                            iss_desc = "Mandatory field is blank"
                        elif isinstance(val, str) and val.strip() == "":
                            iss_desc = "Mandatory field is whitespace-only"
                        else:
                            iss_desc = "Mandatory field is blank"
                    else:
                        val = ""
                        iss_desc = "Mandatory field is blank"

                    rec = {
                        "row_number": r,
                        "field": col,
                        "value": val,
                        "issue": iss_desc,
                        "dataset": mf.dataset_name,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    concise_rows = _format_row_range(s_rows, MAX_SUMMARY_CONCISE_EXAMPLES)
                    summary_ex = f"{concise_rows}: missing mandatory value" if concise_rows else f"{cnt} records missing mandatory value"

                issues.append({
                    "category": "Mandatory Fields",
                    "dataset": mf.dataset_name,
                    "column": col,
                    "issue_type": "Missing mandatory field value",
                    "severity": mf.severity.value if hasattr(mf.severity, "value") else str(mf.severity),
                    "affected_count": cnt,
                    "affected_pct": pf.get("missing_pct", 0.0),
                    "sample_rows": s_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(s_rows), MAX_REPORT_EXAMPLES)} of {cnt} records" if cnt > MAX_REPORT_EXAMPLES else "",
                    "details": details,
                })

    # 3. Nulls and Blanks
    for nr in result.null_blank_results:
        ds_df = _get_df_for_dataset(dfs, nr.dataset_name)
        for col_info in nr.per_column:
            col_name = col_info.get("column", "")
            null_c = col_info.get("null_count", 0)
            blank_c = col_info.get("blank_count", 0)
            ws_c = col_info.get("whitespace_only_count", 0)
            sev = col_info.get("severity", "Info")
            
            if null_c > 0:
                s_rows = col_info.get("sample_null_rows", [])
                details = []
                for r in s_rows[:MAX_REPORT_EXAMPLES]:
                    _, rec_dict = _resolve_verified_source_record(ds_df, r, field_name=col_name, is_missing_check=True)
                    rec = {
                        "row_number": r,
                        "field": col_name,
                        "value": None,
                        "issue": "Null / missing value",
                        "dataset": nr.dataset_name,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    concise_rows = _format_row_range(s_rows, MAX_SUMMARY_CONCISE_EXAMPLES)
                    summary_ex = concise_rows if concise_rows else f"{null_c} null rows"

                issues.append({
                    "category": "Null / Blank Values",
                    "dataset": nr.dataset_name,
                    "column": col_name,
                    "issue_type": "Null / Missing value",
                    "severity": sev,
                    "affected_count": null_c,
                    "affected_pct": col_info.get("null_pct", 0.0),
                    "sample_rows": s_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(s_rows), MAX_REPORT_EXAMPLES)} of {null_c} records" if null_c > MAX_REPORT_EXAMPLES else "",
                    "details": details,
                })

            if blank_c > 0:
                s_rows = col_info.get("sample_blank_rows", [])
                details = []
                for r in s_rows[:MAX_REPORT_EXAMPLES]:
                    raw_val, rec_dict = _resolve_verified_source_record(ds_df, r, field_name=col_name, is_missing_check=True)
                    val = "" if raw_val is None else raw_val
                    rec = {
                        "row_number": r,
                        "field": col_name,
                        "value": val,
                        "issue": 'Empty string value ("")',
                        "dataset": nr.dataset_name,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    concise_rows = _format_row_range(s_rows, MAX_SUMMARY_CONCISE_EXAMPLES)
                    summary_ex = f"{concise_rows}: empty strings (\"\")" if concise_rows else f"{blank_c} empty strings"

                issues.append({
                    "category": "Null / Blank Values",
                    "dataset": nr.dataset_name,
                    "column": col_name,
                    "issue_type": "Empty string value (\"\")",
                    "severity": sev,
                    "affected_count": blank_c,
                    "affected_pct": col_info.get("blank_pct", 0.0),
                    "sample_rows": s_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(s_rows), MAX_REPORT_EXAMPLES)} of {blank_c} records" if blank_c > MAX_REPORT_EXAMPLES else "",
                    "details": details,
                })

            if ws_c > 0:
                s_rows = col_info.get("sample_ws_rows", [])
                details = []
                for r in s_rows[:MAX_REPORT_EXAMPLES]:
                    raw_val, rec_dict = _resolve_verified_source_record(ds_df, r, field_name=col_name, is_missing_check=True)
                    val = raw_val if (raw_val is not None and str(raw_val).strip() == "") else "   "
                    rec = {
                        "row_number": r,
                        "field": col_name,
                        "value": val,
                        "issue": "Whitespace-only string",
                        "dataset": nr.dataset_name,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    concise_rows = _format_row_range(s_rows, MAX_SUMMARY_CONCISE_EXAMPLES)
                    summary_ex = f"{concise_rows}: whitespace-only" if concise_rows else f"{ws_c} whitespace-only strings"

                issues.append({
                    "category": "Null / Blank Values",
                    "dataset": nr.dataset_name,
                    "column": col_name,
                    "issue_type": "Whitespace-only string",
                    "severity": sev,
                    "affected_count": ws_c,
                    "affected_pct": col_info.get("whitespace_only_pct", 0.0),
                    "sample_rows": s_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(s_rows), MAX_REPORT_EXAMPLES)} of {ws_c} records" if ws_c > MAX_REPORT_EXAMPLES else "",
                    "details": details,
                })

    # 4. Whitespace
    for wr in result.whitespace_results:
        ds_df = _get_df_for_dataset(dfs, wr.dataset_name)
        for col_info in wr.per_column:
            tot = col_info.get("total_affected", 0)
            if tot > 0:
                samples = col_info.get("sample_issues", [])
                s_rows = col_info.get("sample_rows", [])
                col = col_info.get("column", "")
                types = []
                if col_info.get("leading_count", 0) > 0:
                    types.append(f"Leading ({col_info['leading_count']})")
                if col_info.get("trailing_count", 0) > 0:
                    types.append(f"Trailing ({col_info['trailing_count']})")
                if col_info.get("multi_internal_count", 0) > 0:
                    types.append(f"Multiple internal ({col_info['multi_internal_count']})")

                details = []
                for s in samples[:MAX_REPORT_EXAMPLES]:
                    r = s.get("row_number")
                    carried_val = s.get("value")
                    issue_type = s.get("issue_type", "Whitespace anomaly")
                    raw_val, rec_dict = _resolve_verified_source_record(ds_df, r, field_name=col)
                    val = raw_val if raw_val is not None else carried_val
                    if isinstance(val, str) and len(val) >= 2 and val[0] in ("'", '"') and val[-1] == val[0]:
                        val = val[1:-1]

                    rec = {
                        "row_number": r,
                        "field": col,
                        "value": val,
                        "issue": f"Whitespace anomaly: {issue_type}",
                        "dataset": wr.dataset_name,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    concise_rows = _format_row_range(s_rows, MAX_SUMMARY_CONCISE_EXAMPLES)
                    summary_ex = f"{concise_rows}: leading/trailing whitespace" if concise_rows else f"{tot} rows with whitespace noise"

                sev_val = col_info.get("severity", wr.severity.value if hasattr(wr, "severity") and hasattr(wr.severity, "value") else "Low")
                if hasattr(sev_val, "value"):
                    sev_val = sev_val.value

                issues.append({
                    "category": "Whitespace Issues",
                    "dataset": wr.dataset_name,
                    "column": col,
                    "issue_type": f"Whitespace anomalies: {', '.join(types)}",
                    "severity": str(sev_val),
                    "affected_count": tot,
                    "affected_pct": 0.0,
                    "sample_rows": s_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(samples), MAX_REPORT_EXAMPLES)} of {tot} records" if tot > MAX_REPORT_EXAMPLES else "",
                    "details": details,
                })

    # 5. Special Characters
    for sc in result.special_char_results:
        ds_df = _get_df_for_dataset(dfs, sc.dataset_name)
        for col_info in sc.per_column:
            cnt = col_info.get("violation_count", 0)
            if cnt > 0:
                samples = col_info.get("sample_violations", [])
                s_rows = col_info.get("sample_rows", [])
                col = col_info.get("column", "")

                details = []
                for s in samples[:MAX_REPORT_EXAMPLES]:
                    r = s.get("row_number")
                    val = s.get("value")
                    rule = s.get("rule", col_info.get("rule_name", ""))
                    offenders = s.get("offending_chars", "")
                    if not offenders and isinstance(val, str):
                        extracted = sorted(set(re.findall(r"[^A-Za-z0-9\s]", val)))
                        if extracted:
                            offenders = ", ".join(extracted)
                    iss_desc = f"Invalid character: {offenders}" if offenders else f"Character rule violation ({rule})"
                    _, rec_dict = _resolve_verified_source_record(ds_df, r, field_name=col)
                    rec = {
                        "row_number": r,
                        "field": col,
                        "value": val,
                        "issue": iss_desc,
                        "character": offenders or rule,
                        "rule": rule,
                        "dataset": sc.dataset_name,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    concise_rows = _format_row_range(s_rows, MAX_SUMMARY_CONCISE_EXAMPLES)
                    summary_ex = f"{concise_rows}: character violations" if concise_rows else f"{cnt} character violations"

                issues.append({
                    "category": "Special Character Issues",
                    "dataset": sc.dataset_name,
                    "column": col,
                    "issue_type": f"Character rule violation ({col_info.get('rule_name')})",
                    "severity": col_info.get("severity", "Medium"),
                    "affected_count": cnt,
                    "affected_pct": col_info.get("violation_pct", 0.0),
                    "sample_rows": s_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(samples), MAX_REPORT_EXAMPLES)} of {cnt} records" if cnt > MAX_REPORT_EXAMPLES else "",
                    "details": details,
                })

    # 6. Dates
    for dr in result.date_results:
        ds_df = _get_df_for_dataset(dfs, dr.dataset_name)
        for col_info in dr.per_column:
            cnt = col_info.get("invalid_count", 0)
            has_incons = col_info.get("has_inconsistency", False)
            if cnt > 0 or has_incons:
                samples = col_info.get("sample_invalid_details", [])
                s_rows = col_info.get("sample_rows", [])
                col = col_info.get("column", "")
                desc_parts = []
                if cnt > 0:
                    desc_parts.append(f"{cnt} invalid/impossible dates")
                if has_incons:
                    desc_parts.append(f"Inconsistent date formats (dominant: {col_info.get('dominant_format')})")

                details = []
                for s in samples[:MAX_REPORT_EXAMPLES]:
                    r = s.get("row_number")
                    val = s.get("value")
                    reason = s.get("reason", "Invalid date")
                    _, rec_dict = _resolve_verified_source_record(ds_df, r, field_name=col)
                    rec = {
                        "row_number": r,
                        "field": col,
                        "value": val,
                        "issue": reason,
                        "reason": reason,
                        "dataset": dr.dataset_name,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    concise_rows = _format_row_range(s_rows, MAX_SUMMARY_CONCISE_EXAMPLES)
                    summary_ex = f"{concise_rows}: invalid date format/values" if concise_rows else f"{cnt} date errors"

                issues.append({
                    "category": "Date Issues",
                    "dataset": dr.dataset_name,
                    "column": col,
                    "issue_type": "; ".join(desc_parts),
                    "severity": col_info.get("severity", "Medium"),
                    "affected_count": cnt,
                    "affected_pct": col_info.get("invalid_pct", 0.0),
                    "sample_rows": s_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(samples), MAX_REPORT_EXAMPLES)} of {cnt} records" if cnt > MAX_REPORT_EXAMPLES else "",
                    "details": details,
                })

    # 7. Patterns
    for pr in result.pattern_results:
        ds_df = _get_df_for_dataset(dfs, pr.dataset_name)
        for col_info in pr.per_column:
            samples = col_info.get("sample_inconsistencies", [])
            s_rows = col_info.get("sample_rows", [])
            col = col_info.get("column", "")
            dom_pattern = col_info.get("dominant_pattern", "")

            if samples:
                details = []
                for s in samples[:MAX_REPORT_EXAMPLES]:
                    r = s.get("row_number")
                    val = s.get("value")
                    pat = s.get("pattern", "")
                    dom = s.get("dominant_pattern", dom_pattern)
                    iss_desc = f"Pattern mismatch (expected {dom})" if dom else "Invalid pattern format"
                    _, rec_dict = _resolve_verified_source_record(ds_df, r, field_name=col)
                    rec = {
                        "row_number": r,
                        "field": col,
                        "value": val,
                        "issue": iss_desc,
                        "pattern": pat,
                        "dominant_pattern": dom,
                        "dataset": pr.dataset_name,
                    }
                    if rec_dict:
                        rec["record_data"] = rec_dict
                    details.append(rec)

                examples_str = "; ".join(_format_example_entry(d) for d in details)
                if details:
                    summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
                else:
                    concise_rows = _format_row_range(s_rows, MAX_SUMMARY_CONCISE_EXAMPLES)
                    summary_ex = f"{concise_rows}: inconsistent pattern (expected {dom_pattern})" if concise_rows else f"{len(samples)} pattern inconsistencies"

                sev_val = col_info.get("severity", pr.severity.value if hasattr(pr, "severity") and hasattr(pr.severity, "value") else "Low")
                if hasattr(sev_val, "value"):
                    sev_val = sev_val.value

                issues.append({
                    "category": "Pattern / Naming Issues",
                    "dataset": pr.dataset_name,
                    "column": col,
                    "issue_type": f"Pattern inconsistency (dominant mask: {dom_pattern})",
                    "severity": str(sev_val),
                    "affected_count": len(samples),
                    "affected_pct": 0.0,
                    "sample_rows": s_rows,
                    "examples_text": examples_str,
                    "summary_examples_text": summary_ex,
                    "truncation_note": f"Showing first {min(len(samples), MAX_REPORT_EXAMPLES)} of {len(samples)} records",
                    "details": details,
                })

    # 8. Relationships
    for rr in result.relationship_results:
        if rr.orphan_count > 0:
            samples = rr.sample_orphan_records
            sample_rows = [s.get("row_number") for s in samples if s.get("row_number")]
            c_ds = rr.child_dataset
            p_ds = rr.parent_dataset
            c_key = ", ".join(rr.child_key) if isinstance(rr.child_key, list) else str(rr.child_key)
            p_key = ", ".join(rr.parent_key) if isinstance(rr.parent_key, list) else str(rr.parent_key)
            child_df = _get_df_for_dataset(dfs, c_ds)

            details = []
            for s in samples[:MAX_REPORT_EXAMPLES]:
                r = s.get("row_number")
                key_val = s.get("key_value")
                iss_desc = f"Orphan key: '{key_val}' missing in {p_ds}"
                _, rec_dict = _resolve_verified_source_record(child_df, r, field_name=c_key)
                rec = {
                    "row_number": r,
                    "field": f"{c_ds}.{c_key}",
                    "value": key_val,
                    "issue": iss_desc,
                    "dataset": c_ds,
                    "parent_dataset": p_ds,
                    "parent_key": p_key,
                }
                if rec_dict:
                    rec["record_data"] = rec_dict
                details.append(rec)

            examples_str = "; ".join(_format_example_entry(d) for d in details)
            if details:
                summary_ex = "; ".join(_format_example_entry(d) for d in details[:MAX_SUMMARY_CONCISE_EXAMPLES])
            else:
                summary_ex = f"{rr.orphan_count} orphan records missing in parent ({p_ds})"

            issues.append({
                "category": "Relationship Integrity",
                "dataset": c_ds,
                "column": f"{c_ds}.{c_key} -> {p_ds}.{rr.parent_key}",
                "issue_type": f"Orphan records missing in parent ({p_ds})",
                "severity": rr.severity.value if hasattr(rr.severity, "value") else str(rr.severity),
                "affected_count": rr.orphan_count,
                "affected_pct": rr.orphan_pct,
                "sample_rows": sample_rows,
                "examples_text": examples_str,
                "summary_examples_text": summary_ex,
                "truncation_note": f"Showing first {min(len(samples), MAX_REPORT_EXAMPLES)} of {rr.orphan_count} records" if rr.orphan_count > MAX_REPORT_EXAMPLES else "",
                "details": details,
            })

    return issues
