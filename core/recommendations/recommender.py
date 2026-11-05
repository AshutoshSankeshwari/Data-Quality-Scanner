"""
core/recommendations/recommender.py
Rule-based recommendation engine.
Maps detected issue types → prioritized, templated recommendations.
"""
from __future__ import annotations
from core.models import AnalysisResult, Recommendation, Severity

# Priority order for sorting (lower index = higher priority)
_SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]


def _sev_rank(sev: Severity) -> int:
    try:
        return _SEVERITY_ORDER.index(sev)
    except ValueError:
        return 99


# ---------------------------------------------------------------------------
# Recommendation templates
# ---------------------------------------------------------------------------

def _recommendations_from_duplicates(result: AnalysisResult) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for dr in result.duplicate_results:
        if dr.full_row_duplicate_count > 0:
            recs.append(Recommendation(
                title="Remove Full-Row Duplicate Records",
                description=(
                    f"Found {dr.full_row_duplicate_count} fully identical rows "
                    f"({dr.full_row_duplicate_pct:.1f}% of records) in '{dr.dataset_name}'. "
                    "Review and deduplicate records before migration; confirm the intended "
                    "survivorship rule (which duplicate copy to keep)."
                ),
                severity=dr.severity,
                affected_columns=["ALL COLUMNS"],
                issue_type="duplicates_full_row",
                dataset_name=dr.dataset_name,
            ))
        for kb in dr.key_based_results:
            if kb["duplicate_count"] > 0:
                cols = kb["key_columns"]
                recs.append(Recommendation(
                    title=f"Deduplicate Business Key: {', '.join(cols)}",
                    description=(
                        f"Found {kb['duplicate_count']} duplicate values "
                        f"({kb['duplicate_pct']:.1f}%) on key column(s) {cols} in '{dr.dataset_name}'. "
                        "Deduplicate these records before migration; confirm the survivorship rule."
                    ),
                    severity=Severity(kb["severity"]),
                    affected_columns=cols,
                    issue_type="duplicates_key_based",
                    dataset_name=dr.dataset_name,
                ))
    return recs


def _recommendations_from_mandatory_fields(result: AnalysisResult) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for mfr in result.mandatory_field_results:
        if mfr.failing_record_count > 0:
            missing_fields = [
                f["field"] for f in mfr.per_field
                if f.get("missing_count", 0) > 0
            ]
            recs.append(Recommendation(
                title="Source or Default Missing Mandatory Field Values",
                description=(
                    f"{mfr.failing_record_count} records ({mfr.failing_pct:.1f}%) in "
                    f"'{mfr.dataset_name}' are missing one or more mandatory fields: "
                    f"{', '.join(missing_fields)}. "
                    "Source or default missing mandatory values prior to migration; "
                    "confirm business rule for defaulting vs. record rejection."
                ),
                severity=Severity.CRITICAL,
                affected_columns=missing_fields,
                issue_type="mandatory_fields",
                dataset_name=mfr.dataset_name,
            ))
    return recs


def _recommendations_from_nulls(result: AnalysisResult) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for nb in result.null_blank_results:
        high_null_cols = [
            c["column"] for c in nb.per_column
            if c["null_pct"] + c["blank_pct"] + c["whitespace_only_pct"] > 20
            and not c.get("is_mandatory")
        ]
        if high_null_cols:
            recs.append(Recommendation(
                title="Address High Null/Blank Rate in Non-Mandatory Fields",
                description=(
                    f"The following non-mandatory columns in '{nb.dataset_name}' have >20% "
                    f"null/blank values: {', '.join(high_null_cols)}. "
                    "Investigate root cause and determine whether to source, default, or exclude "
                    "these fields from migration."
                ),
                severity=Severity.HIGH,
                affected_columns=high_null_cols,
                issue_type="nulls_high",
                dataset_name=nb.dataset_name,
            ))
    return recs


def _recommendations_from_whitespace(result: AnalysisResult) -> list[Recommendation]:
    recs: list[Recommendation] = []
    affected_datasets: dict[str, list[str]] = {}
    for wr in result.whitespace_results:
        if wr.per_column:
            affected_datasets[wr.dataset_name] = [c["column"] for c in wr.per_column]

    for dataset_name, cols in affected_datasets.items():
        recs.append(Recommendation(
            title="Apply Whitespace Normalization",
            description=(
                f"Leading, trailing, or multiple internal spaces detected in columns "
                f"{', '.join(cols)} of '{dataset_name}'. "
                "Apply a trim/whitespace-normalization pass prior to migration to prevent "
                "mismatches in the target system."
            ),
            severity=Severity.LOW,
            affected_columns=cols,
            issue_type="whitespace",
            dataset_name=dataset_name,
        ))
    return recs


def _recommendations_from_special_chars(result: AnalysisResult) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for sc in result.special_char_results:
        for col_info in sc.per_column:
            recs.append(Recommendation(
                title=f"Cleanse Special Characters in '{col_info['column']}'",
                description=(
                    f"{col_info['violation_count']} values ({col_info['violation_pct']:.1f}%) "
                    f"in column '{col_info['column']}' of '{sc.dataset_name}' violate the "
                    f"'{col_info['rule_name']}' character rule. "
                    "Cleanse ID/key values to conform to the expected character set before migration."
                ),
                severity=Severity(col_info["severity"]),
                affected_columns=[col_info["column"]],
                issue_type="special_chars",
                dataset_name=sc.dataset_name,
            ))
    return recs


def _recommendations_from_patterns(result: AnalysisResult) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for pr in result.pattern_results:
        for col_info in pr.per_column:
            issue_desc = []
            if col_info.get("has_structural_inconsistency"):
                issue_desc.append("structural format inconsistency")
            if col_info.get("has_case_inconsistency"):
                issue_desc.append("case inconsistency")
            if issue_desc:
                recs.append(Recommendation(
                    title=f"Standardize Pattern in '{col_info['column']}'",
                    description=(
                        f"Column '{col_info['column']}' in '{pr.dataset_name}' shows "
                        f"{' and '.join(issue_desc)} across {len(col_info.get('clusters', []))} "
                        "pattern clusters. Standardize values to a single format before migration."
                    ),
                    severity=Severity.MEDIUM,
                    affected_columns=[col_info["column"]],
                    issue_type="patterns",
                    dataset_name=pr.dataset_name,
                ))
    return recs


def _recommendations_from_dates(result: AnalysisResult) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for dr in result.date_results:
        for col_info in dr.per_column:
            if col_info["invalid_count"] > 0:
                recs.append(Recommendation(
                    title=f"Fix Invalid Dates in '{col_info['column']}'",
                    description=(
                        f"{col_info['invalid_count']} invalid date values "
                        f"({col_info['invalid_pct']:.1f}%) found in '{col_info['column']}' "
                        f"of '{dr.dataset_name}'. "
                        + (f"{col_info.get('impossible_date_count', 0)} are impossible dates "
                           "(e.g., Feb 30). " if col_info.get("impossible_date_count", 0) > 0 else "")
                        + "Correct or exclude invalid date values before migration."
                    ),
                    severity=Severity(col_info["severity"]),
                    affected_columns=[col_info["column"]],
                    issue_type="dates_invalid",
                    dataset_name=dr.dataset_name,
                ))
            if col_info.get("has_inconsistency"):
                recs.append(Recommendation(
                    title=f"Standardize Date Format in '{col_info['column']}'",
                    description=(
                        f"Multiple date formats detected in '{col_info['column']}' of "
                        f"'{dr.dataset_name}'. "
                        f"Dominant format: {col_info.get('dominant_format', 'unknown')}. "
                        "Standardize all date values to a single target format before migration."
                    ),
                    severity=Severity.MEDIUM,
                    affected_columns=[col_info["column"]],
                    issue_type="dates_format",
                    dataset_name=dr.dataset_name,
                ))
    return recs


def _recommendations_from_relationships(result: AnalysisResult) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for rr in result.relationship_results:
        if rr.orphan_count > 0:
            recs.append(Recommendation(
                title=f"Resolve Orphan Records: {rr.child_dataset} → {rr.parent_dataset}",
                description=(
                    f"{rr.orphan_count} child records ({rr.orphan_pct:.1f}%) in "
                    f"'{rr.child_dataset}' have {rr.child_key} values not present in "
                    f"'{rr.parent_dataset}' ({rr.parent_key}). "
                    "Investigate and either resolve missing parent records or "
                    "flag/exclude orphaned child records before migration."
                ),
                severity=rr.severity,
                affected_columns=[rr.child_key],
                issue_type="relationship_orphans",
                dataset_name=rr.child_dataset,
            ))
    return recs


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_recommendations(result: AnalysisResult) -> list[Recommendation]:
    """
    Generate a prioritized list of recommendations from analysis results.
    Issues are surfaced Critical first, Low last.
    """
    all_recs: list[Recommendation] = []
    all_recs.extend(_recommendations_from_mandatory_fields(result))
    all_recs.extend(_recommendations_from_relationships(result))
    all_recs.extend(_recommendations_from_duplicates(result))
    all_recs.extend(_recommendations_from_nulls(result))
    all_recs.extend(_recommendations_from_special_chars(result))
    all_recs.extend(_recommendations_from_dates(result))
    all_recs.extend(_recommendations_from_patterns(result))
    all_recs.extend(_recommendations_from_whitespace(result))

    # Sort: Critical first, then High, Medium, Low, Info
    all_recs.sort(key=lambda r: _sev_rank(r.severity))
    return all_recs
