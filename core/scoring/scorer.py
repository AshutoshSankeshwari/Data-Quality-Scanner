"""
core/scoring/scorer.py
Deterministic Issue-Driven Quality & Migration Readiness Scoring.

The overall score is calculated directly from all detected logical quality issues
accounting for their severity and affected record volume. Clean datasets with zero
issues receive an exact score of 100.0. Quality dimensions provide independent
diagnostic metrics (0-100) and no longer drive the overall score through weights.
"""
from __future__ import annotations
from dataclasses import dataclass

from core.models import (
    AnalysisResult, DimensionScore, ReadinessScore, ReadinessCategory,
    Severity, ScoreBreakdownItem, ScoreBreakdown,
)

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_SEVERITY_WEIGHTS = {
    "critical": 15.0,
    "high": 8.0,
    "medium": 3.0,
    "low": 1.0,
    "info": 0.0,
}

DEFAULT_THRESHOLDS = {
    "ready": 90,
    "minor_cleansing": 75,
    "needs_cleansing": 50,
}

BASE_VOLUME_IMPACT = 0.05  # Minimum base impact for any detected issue


# ---------------------------------------------------------------------------
# Helpers & Logical Issue Extraction
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class _LogicalIssue:
    category: str
    dataset_name: str
    target: str           # column name, key set, or relationship pair
    severity: str
    affected_count: int
    total_records: int
    affected_ratio: float


def _extract_logical_issues(result: AnalysisResult) -> list[_LogicalIssue]:
    """
    Extract all distinct logical quality issues detected across datasets.
    Ensures exact integer counts, appropriate per-dataset/check denominators,
    and prevents double-counting of overlapping defects.
    """
    issues: list[_LogicalIssue] = []
    dataset_row_map = {ds.name: ds.row_count for ds in result.datasets}
    primary = result.primary_dataset()
    primary_name = primary.name if primary else "dataset"
    primary_rows = primary.row_count if primary and primary.row_count > 0 else 1

    penalized_mandatory_fields: set[tuple[str, str]] = set()

    # 1. Mandatory Fields
    for mf in result.mandatory_field_results:
        ds_name = mf.dataset_name or primary_name
        ds_rows = dataset_row_map.get(ds_name, primary_rows) or 1
        for pf in mf.per_field:
            cnt = pf.get("missing_count", 0)
            col_name = pf.get("field", "")
            if cnt > 0:
                sev_str = mf.severity.value if hasattr(mf.severity, "value") else str(mf.severity)
                ratio = cnt / ds_rows
                issues.append(_LogicalIssue(
                    category="Mandatory Fields",
                    dataset_name=ds_name,
                    target=col_name,
                    severity=sev_str,
                    affected_count=cnt,
                    total_records=ds_rows,
                    affected_ratio=ratio,
                ))
                penalized_mandatory_fields.add((ds_name, col_name))

    # 2. Nulls and Blanks (Deduplicated against Mandatory Fields & grouped per column)
    for nr in result.null_blank_results:
        ds_name = nr.dataset_name or primary_name
        ds_rows = dataset_row_map.get(ds_name, primary_rows) or 1
        for col in nr.per_column:
            col_name = col.get("column", "")
            # Skip if this column defect was already penalized under Mandatory Fields
            if (ds_name, col_name) in penalized_mandatory_fields:
                continue

            total_missing = (
                col.get("null_count", 0)
                + col.get("blank_count", 0)
                + col.get("whitespace_only_count", 0)
            )
            if total_missing > 0:
                sev = col.get("severity", "Info")
                ratio = total_missing / ds_rows
                issues.append(_LogicalIssue(
                    category="Nulls",
                    dataset_name=ds_name,
                    target=col_name,
                    severity=sev,
                    affected_count=total_missing,
                    total_records=ds_rows,
                    affected_ratio=ratio,
                ))

    # 3. Duplicates (Key-based priority with full-row fallback)
    for dr in result.duplicate_results:
        ds_name = dr.dataset_name or primary_name
        ds_rows = dataset_row_map.get(ds_name, primary_rows) or 1
        if dr.key_based_results:
            for kb in dr.key_based_results:
                cnt = kb.get("duplicate_count", 0)
                if cnt > 0:
                    keys_str = ", ".join(kb.get("key_columns", []))
                    issues.append(_LogicalIssue(
                        category="Duplicates",
                        dataset_name=ds_name,
                        target=f"Key: [{keys_str}]",
                        severity=kb.get("severity", "High"),
                        affected_count=cnt,
                        total_records=ds_rows,
                        affected_ratio=cnt / ds_rows,
                    ))
        elif dr.full_row_duplicate_count > 0:
            sev_str = dr.severity.value if hasattr(dr.severity, "value") else str(dr.severity)
            issues.append(_LogicalIssue(
                category="Duplicates",
                dataset_name=ds_name,
                target="Full Row",
                severity=sev_str,
                affected_count=dr.full_row_duplicate_count,
                total_records=ds_rows,
                affected_ratio=dr.full_row_duplicate_count / ds_rows,
            ))

    # 4. Whitespace Anomalies (Distinct affected row count per text column)
    for wr in result.whitespace_results:
        ds_name = wr.dataset_name or primary_name
        ds_rows = dataset_row_map.get(ds_name, primary_rows) or 1
        for col in wr.per_column:
            col_name = col.get("column", "")
            affected_rows = col.get("affected_rows") or col.get("total_affected", 0)
            if affected_rows > 0:
                sev_str = col.get("severity", wr.severity.value if hasattr(wr, "severity") and hasattr(wr.severity, "value") else "Low")
                issues.append(_LogicalIssue(
                    category="Whitespace",
                    dataset_name=ds_name,
                    target=col_name,
                    severity=sev_str,
                    affected_count=affected_rows,
                    total_records=ds_rows,
                    affected_ratio=affected_rows / ds_rows,
                ))

    # 5. Special Character Violations
    for sc in result.special_char_results:
        ds_name = sc.dataset_name or primary_name
        ds_rows = dataset_row_map.get(ds_name, primary_rows) or 1
        for col in sc.per_column:
            col_name = col.get("column", "")
            cnt = col.get("violation_count", 0)
            if cnt > 0:
                issues.append(_LogicalIssue(
                    category="Special Characters",
                    dataset_name=ds_name,
                    target=col_name,
                    severity=col.get("severity", "Medium"),
                    affected_count=cnt,
                    total_records=ds_rows,
                    affected_ratio=cnt / ds_rows,
                ))

    # 6. Date Invalidities & Inconsistencies
    for dr in result.date_results:
        ds_name = dr.dataset_name or primary_name
        ds_rows = dataset_row_map.get(ds_name, primary_rows) or 1
        for col in dr.per_column:
            col_name = col.get("column", "")
            cnt = col.get("invalid_count", 0)
            has_incons = col.get("has_inconsistency", False)
            if cnt > 0:
                issues.append(_LogicalIssue(
                    category="Dates",
                    dataset_name=ds_name,
                    target=col_name,
                    severity=col.get("severity", "High"),
                    affected_count=cnt,
                    total_records=ds_rows,
                    affected_ratio=cnt / ds_rows,
                ))
            if has_incons and col.get("format_clusters"):
                dominant_count = col["format_clusters"][0].get("count", 0)
                incons_cnt = col.get("total_checked", ds_rows) - dominant_count
                if incons_cnt > 0:
                    issues.append(_LogicalIssue(
                        category="Date Formats",
                        dataset_name=ds_name,
                        target=col_name,
                        severity="Low",
                        affected_count=incons_cnt,
                        total_records=ds_rows,
                        affected_ratio=incons_cnt / ds_rows,
                    ))

    # 7. Pattern Inconsistencies
    for pr in result.pattern_results:
        ds_name = pr.dataset_name or primary_name
        ds_rows = dataset_row_map.get(ds_name, primary_rows) or 1
        for col in pr.per_column:
            col_name = col.get("column", "")
            clusters = col.get("clusters", [])
            dominant_count = max(
                (c.get("count", 0) for c in clusters if c.get("is_dominant")),
                default=col.get("total_analyzed", ds_rows),
            )
            incons_cnt = col.get("total_analyzed", ds_rows) - dominant_count
            if incons_cnt > 0:
                sev_str = col.get("severity", pr.severity.value if hasattr(pr, "severity") and hasattr(pr.severity, "value") else "Low")
                issues.append(_LogicalIssue(
                    category="Patterns",
                    dataset_name=ds_name,
                    target=col_name,
                    severity=sev_str,
                    affected_count=incons_cnt,
                    total_records=ds_rows,
                    affected_ratio=incons_cnt / ds_rows,
                ))

    # 8. Relationship Referential Integrity (Child Population Denominator)
    for rr in result.relationship_results:
        if rr.orphan_count > 0:
            sev_str = rr.severity.value if hasattr(rr.severity, "value") else str(rr.severity)
            child_total = rr.total_child_records if rr.total_child_records > 0 else dataset_row_map.get(rr.child_dataset, 1) or 1
            issues.append(_LogicalIssue(
                category="Relationships",
                dataset_name=rr.child_dataset,
                target=f"{rr.child_dataset}.{rr.child_key} -> {rr.parent_dataset}.{rr.parent_key}",
                severity=sev_str,
                affected_count=rr.orphan_count,
                total_records=child_total,
                affected_ratio=rr.orphan_count / child_total,
            ))

    # Deduplicate strictly by (dataset, category, target)
    deduped: list[_LogicalIssue] = []
    seen: set[tuple[str, str, str]] = set()
    for iss in issues:
        key = (iss.dataset_name, iss.category, iss.target)
        if key not in seen:
            seen.add(key)
            deduped.append(iss)

    return deduped


def _severity_counts(result: AnalysisResult) -> dict[str, int]:
    """Count issues by severity across all check results."""
    counts = {s.value: 0 for s in Severity}

    def _tally(items: list[dict], key: str = "severity"):
        for item in items:
            sev = item.get(key)
            if sev in counts:
                counts[sev] += 1

    for r in result.null_blank_results:
        _tally(r.per_column)
    for r in result.special_char_results:
        _tally(r.per_column)
    for r in result.date_results:
        _tally(r.per_column)
    for r in result.whitespace_results:
        _tally(r.per_column)
    for r in result.pattern_results:
        _tally(r.per_column)
    for r in result.duplicate_results:
        if r.severity.value in counts:
            counts[r.severity.value] += 1
    for r in result.mandatory_field_results:
        if r.severity.value in counts:
            counts[r.severity.value] += 1
    for r in result.relationship_results:
        if r.severity.value in counts:
            counts[r.severity.value] += 1

    return counts


# ---------------------------------------------------------------------------
# Independent Diagnostic Dimension Scorers (0-100)
# ---------------------------------------------------------------------------

def _score_completeness(result: AnalysisResult) -> float:
    """Completeness = 100 - average missing value percentage across columns."""
    penalties = []
    for nb_result in result.null_blank_results:
        for col_info in nb_result.per_column:
            combined_pct = (
                col_info.get("null_pct", 0.0)
                + col_info.get("blank_pct", 0.0)
                + col_info.get("whitespace_only_pct", 0.0)
            )
            penalties.append(combined_pct)

    if not penalties:
        return 100.0
    avg_penalty = sum(penalties) / len(penalties)
    return round(_clamp(100.0 - avg_penalty), 1)


def _score_uniqueness(result: AnalysisResult) -> float:
    """Uniqueness = 100 - average duplicate percentage across duplicate checks."""
    penalties = []
    for dr in result.duplicate_results:
        penalties.append(dr.full_row_duplicate_pct)
        for kb in dr.key_based_results:
            penalties.append(kb.get("duplicate_pct", 0.0))

    if not penalties:
        return 100.0
    avg_penalty = sum(penalties) / len(penalties)
    return round(_clamp(100.0 - avg_penalty * 2), 1)


def _score_validity(result: AnalysisResult) -> float:
    """Validity = 100 - average date invalidity and special-character violation rates."""
    penalties = []
    for dr in result.date_results:
        for col in dr.per_column:
            penalties.append(col.get("invalid_pct", 0.0))

    for sc in result.special_char_results:
        for col in sc.per_column:
            penalties.append(col.get("violation_pct", 0.0))

    for mfr in result.mandatory_field_results:
        penalties.append(mfr.failing_pct)

    if not penalties:
        return 100.0
    avg_penalty = sum(penalties) / len(penalties)
    return round(_clamp(100.0 - avg_penalty), 1)


def _score_consistency(result: AnalysisResult) -> float:
    """Consistency = 100 - average pattern and date format deviations."""
    penalties = []
    for pr in result.pattern_results:
        for col in pr.per_column:
            dominant_pct = max(
                (c["pct"] for c in col.get("clusters", []) if c.get("is_dominant")),
                default=100.0,
            )
            penalties.append(100.0 - dominant_pct)

    for dr in result.date_results:
        for col in dr.per_column:
            if col.get("has_inconsistency") and col.get("format_clusters"):
                dominant_pct = col["format_clusters"][0].get("pct", 100.0)
                penalties.append(100.0 - dominant_pct)

    if not penalties:
        return 100.0
    avg_penalty = sum(penalties) / len(penalties)
    return round(_clamp(100.0 - avg_penalty), 1)


def _score_integrity(result: AnalysisResult) -> float:
    """Integrity = 100 - average orphan rate across relationships."""
    if not result.relationship_results:
        return 100.0
    penalties = [r.orphan_pct for r in result.relationship_results]
    avg_penalty = sum(penalties) / len(penalties)
    return round(_clamp(100.0 - avg_penalty * 3), 1)


def _score_cleanliness(result: AnalysisResult) -> float:
    """Cleanliness = 100 - whitespace anomaly rate."""
    penalties = []
    total_rows = result.primary_dataset().row_count if result.primary_dataset() else 1
    for wr in result.whitespace_results:
        for col in wr.per_column:
            affected = col.get("total_affected", 0)
            pct = 100.0 * affected / total_rows if total_rows > 0 else 0.0
            penalties.append(pct)

    if not penalties:
        return 100.0
    avg_penalty = sum(penalties) / len(penalties)
    return round(_clamp(100.0 - avg_penalty * 0.5), 1)


# ---------------------------------------------------------------------------
# Main scoring function (Issue-Driven Calculation)
# ---------------------------------------------------------------------------

def calculate_score(
    result: AnalysisResult,
    severity_weights: dict[str, float] | None = None,
    thresholds: dict[str, int] | None = None,
    **_kwargs,  # Gracefully accept legacy kwargs if passed
) -> ReadinessScore:
    """
    Calculate a deterministic Issue-Driven Quality & Migration Readiness Score.

    The score starts at 100.0 and decreases based on all detected logical quality issues,
    scaling with both severity (Critical, High, Medium, Low) and affected record volume.
    Clean datasets with 0 issues produce an exact score of 100.0.

    Formula:
        For each logical quality issue i:
            affected_ratio = affected_pct / 100.0 (or affected_count / total_rows)
            volume_scaling = BASE_VOLUME_IMPACT + (1.0 - BASE_VOLUME_IMPACT) * affected_ratio
            penalty_i = severity_weight * volume_scaling

        Overall Score = clamp(100.0 - sum(penalty_i), 0.0, 100.0)

    Args:
        result: Populated AnalysisResult from the engine.
        severity_weights: Dict of severity_name -> penalty points (default: critical=15, high=8, med=3, low=1).
        thresholds: Dict of readiness_category -> minimum overall score.

    Returns:
        ReadinessScore containing overall score, readiness category, and diagnostic dimension scores.
    """
    weights = severity_weights or DEFAULT_SEVERITY_WEIGHTS
    t = thresholds or DEFAULT_THRESHOLDS

    # 1. Extract all logical issues detected across checks
    issues = _extract_logical_issues(result)

    # 2. Calculate cumulative issue penalty with full floating-point precision
    breakdown_items: list[ScoreBreakdownItem] = []
    total_penalty = 0.0

    for issue in issues:
        sev_key = issue.severity.lower()
        base_weight = weights.get(sev_key, 0.0)
        if base_weight <= 0.0:
            continue

        # Ratio of dataset volume affected: 0.0 to 1.0 (exact integer ratio)
        affected_ratio = min(1.0, max(0.0, issue.affected_ratio))
        volume_scaling = BASE_VOLUME_IMPACT + (1.0 - BASE_VOLUME_IMPACT) * affected_ratio
        issue_penalty = base_weight * volume_scaling
        total_penalty += issue_penalty

        breakdown_items.append(ScoreBreakdownItem(
            category=issue.category,
            dataset_name=issue.dataset_name,
            target=issue.target,
            severity=issue.severity,
            weight=base_weight,
            affected_count=issue.affected_count,
            total_records=issue.total_records,
            affected_ratio=affected_ratio,
            volume_scaler=volume_scaling,
            penalty=issue_penalty,
        ))

    # 3. Derive raw and display scores
    raw_score = _clamp(100.0 - total_penalty, 0.0, 100.0)
    display_score = round(raw_score, 1)

    # Explicit reconciliation assertion: verify returned score equals 100 - sum(penalties)
    expected_raw = _clamp(100.0 - sum(item.penalty for item in breakdown_items), 0.0, 100.0)
    assert abs(raw_score - expected_raw) < 1e-9, f"Score reconciliation mismatch: {raw_score} vs {expected_raw}"

    breakdown = ScoreBreakdown(
        items=breakdown_items,
        total_penalty=total_penalty,
        raw_score=raw_score,
        display_score=display_score,
    )

    # 4. Compute independent diagnostic dimension scores (0-100, unweighted)
    dimensions: list[DimensionScore] = [
        DimensionScore(name="Completeness", score=_score_completeness(result), weight=0.0, weighted=0.0, explanation=""),
        DimensionScore(name="Uniqueness", score=_score_uniqueness(result), weight=0.0, weighted=0.0, explanation=""),
        DimensionScore(name="Validity", score=_score_validity(result), weight=0.0, weighted=0.0, explanation=""),
        DimensionScore(name="Consistency", score=_score_consistency(result), weight=0.0, weighted=0.0, explanation=""),
        DimensionScore(name="Integrity", score=_score_integrity(result), weight=0.0, weighted=0.0, explanation=""),
        DimensionScore(name="Cleanliness", score=_score_cleanliness(result), weight=0.0, weighted=0.0, explanation=""),
    ]

    # 5. Determine readiness category
    if display_score >= t.get("ready", 90):
        category = ReadinessCategory.READY
    elif display_score >= t.get("minor_cleansing", 75):
        category = ReadinessCategory.MINOR_CLEANSING
    elif display_score >= t.get("needs_cleansing", 50):
        category = ReadinessCategory.NEEDS_CLEANSING
    else:
        category = ReadinessCategory.NOT_READY

    # 6. Count severity issues
    sev_counts = _severity_counts(result)

    return ReadinessScore(
        overall=display_score,
        category=category,
        dimensions=dimensions,
        blocker_count=sev_counts.get(Severity.CRITICAL.value, 0),
        high_count=sev_counts.get(Severity.HIGH.value, 0),
        medium_count=sev_counts.get(Severity.MEDIUM.value, 0),
        low_count=sev_counts.get(Severity.LOW.value, 0),
        raw_score=raw_score,
        breakdown=breakdown,
    )


