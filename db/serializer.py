"""
db/serializer.py
Serialization and deserialization helpers between AnalysisResult dataclasses
and SQLite relational table rows.
Preserves rich issue-level samples and metadata without storing raw data rows.
"""
from __future__ import annotations
import json
from typing import Any

from core.models import (
    AnalysisResult, DatasetProfile, ColumnProfile, ColumnType,
    ReadinessScore, DimensionScore, ReadinessCategory, Severity,
    Recommendation, DuplicateResult, NullBlankResult, MandatoryFieldResult,
    WhitespaceResult, SpecialCharResult, PatternResult, DateResult,
    RelationshipResult,
)


def serialize_column_profile(col: ColumnProfile) -> dict[str, Any]:
    """Serialize ColumnProfile to a compact dict (no raw cell data)."""
    return {
        "name": col.name,
        "inferred_type": col.inferred_type.value if hasattr(col.inferred_type, "value") else str(col.inferred_type),
        "total_count": col.total_count,
        "null_count": col.null_count,
        "null_pct": col.null_pct,
        "blank_count": col.blank_count,
        "blank_pct": col.blank_pct,
        "whitespace_only_count": col.whitespace_only_count,
        "whitespace_only_pct": col.whitespace_only_pct,
        "unique_count": col.unique_count,
        "cardinality_ratio": col.cardinality_ratio,
        "top_values": col.top_values[:10] if col.top_values else [],
        "numeric_min": col.numeric_min,
        "numeric_max": col.numeric_max,
        "numeric_mean": col.numeric_mean,
        "numeric_median": col.numeric_median,
        "numeric_std": col.numeric_std,
        "str_min_len": col.str_min_len,
        "str_max_len": col.str_max_len,
        "date_min": col.date_min,
        "date_max": col.date_max,
        "date_invalid_count": col.date_invalid_count,
    }


def deserialize_column_profile(data: dict[str, Any]) -> ColumnProfile:
    """Reconstruct a ColumnProfile from serialized dict."""
    try:
        col_type = ColumnType(data.get("inferred_type", "unknown"))
    except ValueError:
        col_type = ColumnType.UNKNOWN

    return ColumnProfile(
        name=data.get("name", ""),
        inferred_type=col_type,
        total_count=int(data.get("total_count", 0)),
        null_count=int(data.get("null_count", 0)),
        null_pct=float(data.get("null_pct", 0.0)),
        blank_count=int(data.get("blank_count", 0)),
        blank_pct=float(data.get("blank_pct", 0.0)),
        whitespace_only_count=int(data.get("whitespace_only_count", 0)),
        whitespace_only_pct=float(data.get("whitespace_only_pct", 0.0)),
        unique_count=int(data.get("unique_count", 0)),
        cardinality_ratio=float(data.get("cardinality_ratio", 0.0)),
        top_values=data.get("top_values", []),
        numeric_min=data.get("numeric_min"),
        numeric_max=data.get("numeric_max"),
        numeric_mean=data.get("numeric_mean"),
        numeric_median=data.get("numeric_median"),
        numeric_std=data.get("numeric_std"),
        str_min_len=data.get("str_min_len"),
        str_max_len=data.get("str_max_len"),
        date_min=data.get("date_min"),
        date_max=data.get("date_max"),
        date_invalid_count=data.get("date_invalid_count"),
    )


def extract_check_results_for_db(result: AnalysisResult) -> list[dict[str, Any]]:
    """Extract check results into rows ready for check_results table."""
    rows = []

    # 1. Duplicates
    for dr in result.duplicate_results:
        rows.append({
            "dataset_name": dr.dataset_name,
            "check_type": "duplicates",
            "severity": dr.severity.value if hasattr(dr.severity, "value") else str(dr.severity),
            "affected_count": dr.full_row_duplicate_count,
            "affected_pct": dr.full_row_duplicate_pct,
            "details_json": json.dumps({
                "full_row_duplicate_count": dr.full_row_duplicate_count,
                "full_row_duplicate_pct": dr.full_row_duplicate_pct,
                "key_based_results": dr.key_based_results,
                "sample_duplicates": dr.sample_duplicates,
                "severity": dr.severity.value if hasattr(dr.severity, "value") else str(dr.severity),
            }),
        })

    # 2. Nulls
    for nr in result.null_blank_results:
        total_null_issues = sum(c.get("null_count", 0) for c in nr.per_column)
        rows.append({
            "dataset_name": nr.dataset_name,
            "check_type": "nulls",
            "severity": "Medium" if total_null_issues > 0 else "Info",
            "affected_count": total_null_issues,
            "affected_pct": 0.0,
            "details_json": json.dumps({"per_column": nr.per_column}),
        })

    # 3. Mandatory Fields
    for mf in result.mandatory_field_results:
        rows.append({
            "dataset_name": mf.dataset_name,
            "check_type": "mandatory_fields",
            "severity": mf.severity.value if hasattr(mf.severity, "value") else str(mf.severity),
            "affected_count": mf.failing_record_count,
            "affected_pct": mf.failing_pct,
            "details_json": json.dumps({
                "mandatory_fields": mf.mandatory_fields,
                "failing_record_count": mf.failing_record_count,
                "total_records": mf.total_records,
                "failing_pct": mf.failing_pct,
                "per_field": mf.per_field,
                "severity": mf.severity.value if hasattr(mf.severity, "value") else str(mf.severity),
            }),
        })

    # 4. Whitespace
    for wr in result.whitespace_results:
        ws_count = sum(c.get("leading_count", 0) + c.get("trailing_count", 0) + c.get("multi_internal_count", 0) for c in wr.per_column)
        sev_str = wr.severity.value if hasattr(wr.severity, "value") else str(wr.severity)
        rows.append({
            "dataset_name": wr.dataset_name,
            "check_type": "whitespace",
            "severity": sev_str,
            "affected_count": ws_count,
            "affected_pct": 0.0,
            "details_json": json.dumps({"per_column": wr.per_column, "severity": sev_str}),
        })

    # 5. Special Chars
    for sc in result.special_char_results:
        sc_count = sum(c.get("violation_count", 0) for c in sc.per_column)
        rows.append({
            "dataset_name": sc.dataset_name,
            "check_type": "special_chars",
            "severity": "High" if sc_count > 0 else "Info",
            "affected_count": sc_count,
            "affected_pct": 0.0,
            "details_json": json.dumps({"per_column": sc.per_column}),
        })

    # 6. Patterns
    for pr in result.pattern_results:
        pat_count = sum(len(c.get("sample_inconsistencies", [])) for c in pr.per_column)
        sev_str = pr.severity.value if hasattr(pr.severity, "value") else str(pr.severity)
        rows.append({
            "dataset_name": pr.dataset_name,
            "check_type": "patterns",
            "severity": sev_str,
            "affected_count": pat_count,
            "affected_pct": 0.0,
            "details_json": json.dumps({"per_column": pr.per_column, "severity": sev_str}),
        })

    # 7. Dates
    for dr in result.date_results:
        date_count = sum(c.get("invalid_count", 0) for c in dr.per_column)
        rows.append({
            "dataset_name": dr.dataset_name,
            "check_type": "dates",
            "severity": "High" if date_count > 0 else "Info",
            "affected_count": date_count,
            "affected_pct": 0.0,
            "details_json": json.dumps({"per_column": dr.per_column}),
        })

    return rows


def reconstruct_analysis_result(
    scan_row: dict[str, Any],
    dataset_rows: list[dict[str, Any]],
    check_rows: list[dict[str, Any]],
    factor_rows: list[dict[str, Any]],
    relationship_rows: list[dict[str, Any]],
    recommendation_rows: list[dict[str, Any]],
) -> AnalysisResult:
    """
    Reconstruct a typed AnalysisResult instance from SQLite query rows.
    Enables re-exporting reports or loading historical scans in GUI without original data files.
    """
    # Datasets
    datasets = []
    for d in dataset_rows:
        cols = []
        if d.get("columns_summary_json"):
            try:
                cols_data = json.loads(d["columns_summary_json"])
                cols = [deserialize_column_profile(c) for c in cols_data]
            except Exception:
                cols = []

        is_prim = bool(d.get("is_primary", 0))
        datasets.append(DatasetProfile(
            name=d["dataset_name"],
            row_count=d["row_count"],
            column_count=d["column_count"],
            columns=cols,
            duplicate_row_count=d.get("duplicate_row_count", 0),
            duplicate_row_pct=d.get("duplicate_row_pct", 0.0),
            overall_null_pct=d.get("overall_null_pct", 0.0),
            size_bytes=d.get("size_bytes"),
            is_primary=is_prim,
            file_path=d.get("dataset_name"),
            file_type="CSV" if ".csv" in d.get("dataset_name", "").lower() or not ".xls" in d.get("dataset_name", "").lower() else "Excel",
        ))

    # Scoring & Dimensions
    score_obj = None
    if scan_row.get("overall_score") is not None:
        cat_str = scan_row.get("readiness_category", "READY")
        try:
            category = ReadinessCategory(cat_str)
        except ValueError:
            category = ReadinessCategory.READY

        dimensions = []
        for f in factor_rows:
            dimensions.append(DimensionScore(
                name=f["dimension_name"],
                score=f["score"],
                weight=f["weight"],
                weighted=f["weighted_score"],
                explanation=f.get("explanation", ""),
            ))

        score_obj = ReadinessScore(
            overall=scan_row["overall_score"],
            category=category,
            dimensions=dimensions,
            blocker_count=scan_row.get("blocker_count", 0),
            high_count=scan_row.get("high_count", 0),
            medium_count=scan_row.get("medium_count", 0),
            low_count=scan_row.get("low_count", 0),
        )

    # Relationships
    relationships = []
    for r in relationship_rows:
        try:
            sev = Severity(r["severity"])
        except ValueError:
            sev = Severity.INFO

        raw_desc = r.get("description", "")
        desc_text = raw_desc
        orphan_samples = []
        origin = "configured"
        auto_confirmed = False
        if raw_desc and raw_desc.startswith('{"'):
            try:
                parsed = json.loads(raw_desc)
                desc_text = parsed.get("text", "")
                orphan_samples = parsed.get("samples", [])
                origin = parsed.get("origin", "automatic" if parsed.get("is_automatically_detected", False) else "configured")
                auto_confirmed = parsed.get("automatically_confirmed", False)
            except Exception:
                pass

        relationships.append(RelationshipResult(
            parent_dataset=r["parent_dataset"],
            child_dataset=r["child_dataset"],
            parent_key=r["parent_key"],
            child_key=r["child_key"],
            total_child_records=r["total_child_records"],
            orphan_count=r["orphan_count"],
            orphan_pct=r["orphan_pct"],
            severity=sev,
            description=desc_text,
            sample_orphan_records=orphan_samples,
            origin=origin,
            automatically_confirmed=auto_confirmed,
        ))

    # Recommendations
    recommendations = []
    for rec in recommendation_rows:
        try:
            sev = Severity(rec["severity"])
        except ValueError:
            sev = Severity.INFO

        aff_cols = []
        if rec.get("affected_columns_json"):
            try:
                aff_cols = json.loads(rec["affected_columns_json"])
            except Exception:
                aff_cols = []

        recommendations.append(Recommendation(
            title=rec["title"],
            description=rec["description"],
            severity=sev,
            affected_columns=aff_cols,
            issue_type=rec["issue_type"],
            dataset_name=rec["dataset_name"],
        ))

    # Check Results reconstruction
    dup_results = []
    null_results = []
    mf_results = []
    ws_results = []
    sc_results = []
    pat_results = []
    date_results = []

    for cr in check_rows:
        ctype = cr["check_type"]
        details = {}
        if cr.get("details_json"):
            try:
                details = json.loads(cr["details_json"])
            except Exception:
                details = {}

        if ctype == "duplicates":
            try:
                sev = Severity(details.get("severity", "Info"))
            except ValueError:
                sev = Severity.INFO
            dup_results.append(DuplicateResult(
                dataset_name=cr["dataset_name"],
                full_row_duplicate_count=details.get("full_row_duplicate_count", 0),
                full_row_duplicate_pct=details.get("full_row_duplicate_pct", 0.0),
                key_based_results=details.get("key_based_results", []),
                severity=sev,
                sample_duplicates=details.get("sample_duplicates", []),
            ))
        elif ctype == "nulls":
            null_results.append(NullBlankResult(
                dataset_name=cr["dataset_name"],
                per_column=details.get("per_column", []),
            ))
        elif ctype == "mandatory_fields":
            try:
                sev = Severity(details.get("severity", "Info"))
            except ValueError:
                sev = Severity.INFO
            mf_results.append(MandatoryFieldResult(
                dataset_name=cr["dataset_name"],
                mandatory_fields=details.get("mandatory_fields", []),
                failing_record_count=details.get("failing_record_count", 0),
                total_records=details.get("total_records", 0),
                failing_pct=details.get("failing_pct", 0.0),
                per_field=details.get("per_field", []),
                severity=sev,
            ))
        elif ctype == "whitespace":
            try:
                sev = Severity(details.get("severity", cr.get("severity", "Low")))
            except ValueError:
                sev = Severity.LOW if details.get("per_column") else Severity.INFO
            ws_results.append(WhitespaceResult(
                dataset_name=cr["dataset_name"],
                per_column=details.get("per_column", []),
                severity=sev,
            ))
        elif ctype == "special_chars":
            sc_results.append(SpecialCharResult(
                dataset_name=cr["dataset_name"],
                per_column=details.get("per_column", []),
            ))
        elif ctype == "patterns":
            try:
                sev = Severity(details.get("severity", cr.get("severity", "Low")))
            except ValueError:
                sev = Severity.LOW if details.get("per_column") else Severity.INFO
            pat_results.append(PatternResult(
                dataset_name=cr["dataset_name"],
                per_column=details.get("per_column", []),
                severity=sev,
            ))
        elif ctype == "dates":
            date_results.append(DateResult(
                dataset_name=cr["dataset_name"],
                per_column=details.get("per_column", []),
            ))

    enabled_checks = []
    if scan_row.get("enabled_checks_json"):
        try:
            enabled_checks = json.loads(scan_row["enabled_checks_json"])
        except Exception:
            enabled_checks = []

    warnings = []
    if scan_row.get("warnings_json"):
        try:
            warnings = json.loads(scan_row["warnings_json"])
        except Exception:
            warnings = []

    affected_rows_val = scan_row.get("affected_rows")
    if affected_rows_val is not None:
        try:
            affected_rows_val = int(affected_rows_val)
        except (ValueError, TypeError):
            affected_rows_val = None

    return AnalysisResult(
        run_id=scan_row["run_id"],
        timestamp=scan_row["started_at"],
        datasets=datasets,
        enabled_checks=enabled_checks,
        duplicate_results=dup_results,
        null_blank_results=null_results,
        mandatory_field_results=mf_results,
        whitespace_results=ws_results,
        special_char_results=sc_results,
        pattern_results=pat_results,
        date_results=date_results,
        relationship_results=relationships,
        score=score_obj,
        recommendations=recommendations,
        ai_insights=scan_row.get("ai_insights"),
        warnings=warnings,
        affected_rows_count=affected_rows_val,
    )
