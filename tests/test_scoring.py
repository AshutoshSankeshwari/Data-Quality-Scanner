"""
Tests for core/scoring/scorer.py (Issue-Driven Quality Scoring)
Verifies exact issue extraction, proper denominators, full precision,
double-counting prevention, and transparent reconciliation breakdown.
"""
import pytest

from core.models import (
    AnalysisResult, DatasetProfile, ReadinessCategory,
    DuplicateResult, NullBlankResult, MandatoryFieldResult,
    WhitespaceResult, SpecialCharResult, DateResult,
    RelationshipResult, Severity,
)
from core.scoring.scorer import calculate_score


def _make_base_result(name="test_ds", row_count=200):
    profile = DatasetProfile(
        name=name,
        row_count=row_count,
        column_count=5,
        columns=[],
        duplicate_row_count=0,
        duplicate_row_pct=0.0,
        overall_null_pct=0.0,
    )
    return AnalysisResult(
        run_id="test_run",
        timestamp="2026-08-26T10:00:00",
        datasets=[profile],
        enabled_checks=["duplicates", "nulls", "mandatory_fields", "whitespace", "special_chars", "dates", "patterns", "relationships"],
    )


# ---------------------------------------------------------------------------
# Core Scenario Tests
# ---------------------------------------------------------------------------

def test_scoring_clean_dataset_is_exact_100():
    """1. Clean dataset with zero issues produces an exact score of 100.0."""
    result = _make_base_result()
    score = calculate_score(result)
    assert score.overall == 100.0
    assert score.raw_score == 100.0
    assert score.category == ReadinessCategory.READY
    assert score.blocker_count == 0
    assert score.high_count == 0
    assert score.medium_count == 0
    assert score.low_count == 0
    assert len(score.dimensions) == 6
    assert score.breakdown is not None
    assert len(score.breakdown.items) == 0
    assert score.breakdown.total_penalty == 0.0
    for dim in score.dimensions:
        assert dim.score == 100.0
        assert dim.weight == 0.0


def test_scoring_single_low_severity_exact_penalty():
    """2. One low-severity issue (Weight=1.0) with exact expected penalty."""
    result = _make_base_result(row_count=200)
    result.whitespace_results = [
        WhitespaceResult(
            dataset_name="test_ds",
            per_column=[{
                "column": "Name",
                "leading_count": 1,
                "trailing_count": 0,
                "multi_internal_count": 0,
                "total_affected": 1,
                "affected_rows": 1,
                "sample_issues": [],
                "sample_rows": [5],
            }],
        )
    ]
    score = calculate_score(result)
    # affected_ratio = 1 / 200 = 0.005
    # scaler = 0.05 + 0.95 * 0.005 = 0.05475
    # penalty = 1.0 * 0.05475 = 0.05475
    # raw_score = 100 - 0.05475 = 99.94525 -> 99.9
    assert abs(score.raw_score - 99.94525) < 1e-6
    assert score.overall == 99.9
    assert score.category == ReadinessCategory.READY


def test_scoring_single_high_severity_exact_penalty():
    """3. One high-severity issue (Weight=8.0) with exact expected penalty."""
    result = _make_base_result(row_count=200)
    result.date_results = [
        DateResult(
            dataset_name="test_ds",
            per_column=[{
                "column": "Created_Date",
                "invalid_count": 10,
                "invalid_pct": 5.0,
                "severity": "High",
                "sample_invalid_details": [],
                "sample_rows": list(range(1, 11)),
                "format_clusters": [],
                "dominant_format": "%Y-%m-%d",
                "has_inconsistency": False,
            }],
        )
    ]
    score = calculate_score(result)
    # affected_ratio = 10 / 200 = 0.05
    # scaler = 0.05 + 0.95 * 0.05 = 0.0975
    # penalty = 8.0 * 0.0975 = 0.78
    # raw_score = 100 - 0.78 = 99.22 -> 99.2
    assert abs(score.raw_score - 99.22) < 1e-6
    assert score.overall == 99.2
    assert score.category == ReadinessCategory.READY


def test_scoring_same_severity_volume_scaling():
    """4. Confirm 1% affected < 50% affected < 100% affected in penalty magnitude."""
    def _run_with_missing(cnt, total=100):
        res = _make_base_result(row_count=total)
        res.null_blank_results = [
            NullBlankResult(
                dataset_name="test_ds",
                per_column=[{
                    "column": "Notes",
                    "null_count": cnt,
                    "blank_count": 0,
                    "whitespace_only_count": 0,
                    "severity": "High",
                }],
            )
        ]
        return calculate_score(res)

    s_1pct = _run_with_missing(1, 100)
    s_50pct = _run_with_missing(50, 100)
    s_100pct = _run_with_missing(100, 100)

    # 1% penalty: 8 * (0.05 + 0.95 * 0.01) = 8 * 0.0595 = 0.476 -> score 99.524
    # 50% penalty: 8 * (0.05 + 0.95 * 0.50) = 8 * 0.525 = 4.20 -> score 95.800
    # 100% penalty: 8 * (0.05 + 0.95 * 1.00) = 8 * 1.00 = 8.00 -> score 92.000
    assert s_1pct.raw_score > s_50pct.raw_score > s_100pct.raw_score
    assert abs(s_1pct.raw_score - 99.524) < 1e-6
    assert abs(s_50pct.raw_score - 95.8) < 1e-6
    assert abs(s_100pct.raw_score - 92.0) < 1e-6


def test_scoring_multiple_issues_additive_once():
    """5. Multiple distinct issues accumulate penalties exactly once."""
    result = _make_base_result(row_count=100)
    result.whitespace_results = [
        WhitespaceResult(
            dataset_name="test_ds",
            per_column=[{
                "column": "Name",
                "leading_count": 10,
                "trailing_count": 0,
                "multi_internal_count": 0,
                "total_affected": 10,
                "affected_rows": 10,
                "severity": "Low",
            }],
        )
    ]
    result.special_char_results = [
        SpecialCharResult(
            dataset_name="test_ds",
            per_column=[{
                "column": "Code",
                "violation_count": 10,
                "severity": "Medium",
            }],
        )
    ]
    # Whitespace: 1.0 * (0.05 + 0.95 * 0.10) = 0.145
    # SpecialChar: 3.0 * (0.05 + 0.95 * 0.10) = 0.435
    # Total Penalty: 0.58
    # Raw Score: 99.42 -> 99.4
    score = calculate_score(result)
    assert abs(score.raw_score - 99.42) < 1e-6
    assert score.overall == 99.4
    assert len(score.breakdown.items) == 2


# ---------------------------------------------------------------------------
# Deduplication & Overlap Tests
# ---------------------------------------------------------------------------

def test_prevent_double_counting_mandatory_and_null_overlap():
    """6. Mandatory field failure is penalized as Critical, and not penalized again under Nulls."""
    result = _make_base_result(row_count=100)
    # Customer_ID missing 10 records
    result.mandatory_field_results = [
        MandatoryFieldResult(
            dataset_name="test_ds",
            mandatory_fields=["Customer_ID"],
            failing_record_count=10,
            total_records=100,
            failing_pct=10.0,
            per_field=[{"field": "Customer_ID", "missing_count": 10, "missing_pct": 10.0}],
            severity=Severity.CRITICAL,
        )
    ]
    # Null check also reports Customer_ID missing 10 records
    result.null_blank_results = [
        NullBlankResult(
            dataset_name="test_ds",
            per_column=[{
                "column": "Customer_ID",
                "null_count": 10,
                "blank_count": 0,
                "whitespace_only_count": 0,
                "is_mandatory": True,
                "severity": "Critical",
            }],
        )
    ]

    score = calculate_score(result)
    # Expected: ONLY 1 issue in breakdown (Mandatory Fields), Customer_ID not duplicated in Nulls
    assert len(score.breakdown.items) == 1
    item = score.breakdown.items[0]
    assert item.category == "Mandatory Fields"
    assert item.target == "Customer_ID"
    assert item.weight == 15.0
    # Penalty = 15 * (0.05 + 0.95 * 0.10) = 15 * 0.145 = 2.175
    assert abs(score.raw_score - (100.0 - 2.175)) < 1e-6


def test_prevent_double_counting_duplicate_key_and_full_row():
    """7. When key-based duplicates are checked, full-row duplicates do not double-penalize."""
    result = _make_base_result(row_count=100)
    result.duplicate_results = [
        DuplicateResult(
            dataset_name="test_ds",
            full_row_duplicate_count=5,
            full_row_duplicate_pct=5.0,
            key_based_results=[{
                "key_columns": ["Customer_ID"],
                "duplicate_count": 5,
                "duplicate_pct": 5.0,
                "severity": "High",
            }],
            severity=Severity.HIGH,
        )
    ]
    score = calculate_score(result)
    assert len(score.breakdown.items) == 1
    assert score.breakdown.items[0].target == "Key: [Customer_ID]"


def test_nulls_blanks_whitespace_only_grouped_per_column():
    """8. A single column with nulls, blanks, and whitespace-only is penalized once for its total missing count."""
    result = _make_base_result(row_count=100)
    result.null_blank_results = [
        NullBlankResult(
            dataset_name="test_ds",
            per_column=[{
                "column": "Address",
                "null_count": 4,
                "blank_count": 3,
                "whitespace_only_count": 3,
                "severity": "High",
            }],
        )
    ]
    score = calculate_score(result)
    assert len(score.breakdown.items) == 1
    item = score.breakdown.items[0]
    assert item.affected_count == 10  # 4 + 3 + 3 = 10
    assert abs(item.affected_ratio - 0.10) < 1e-6
    # Penalty: 8.0 * (0.05 + 0.95 * 0.10) = 8.0 * 0.145 = 1.16
    assert abs(item.penalty - 1.16) < 1e-6


# ---------------------------------------------------------------------------
# Denominators & Cross-Dataset Tests
# ---------------------------------------------------------------------------

def test_relationship_uses_child_dataset_denominator():
    """9. Relationship referential integrity uses total_child_records as the denominator."""
    parent_prof = DatasetProfile(name="parent_ds", row_count=1000, column_count=2, columns=[])
    child_prof = DatasetProfile(name="child_ds", row_count=100, column_count=3, columns=[])

    result = AnalysisResult(
        run_id="rel_run",
        timestamp="2026-08-26T10:00:00",
        datasets=[parent_prof, child_prof],
        enabled_checks=["relationships"],
    )
    result.relationship_results = [
        RelationshipResult(
            parent_dataset="parent_ds",
            child_dataset="child_ds",
            parent_key="Cust_ID",
            child_key="Cust_ID",
            total_child_records=100,  # Denominator is 100, NOT 1000!
            orphan_count=10,
            orphan_pct=10.0,
            severity=Severity.CRITICAL,
        )
    ]

    score = calculate_score(result)
    assert len(score.breakdown.items) == 1
    item = score.breakdown.items[0]
    assert item.total_records == 100
    assert item.affected_count == 10
    assert abs(item.affected_ratio - 0.10) < 1e-6
    # Penalty = 15.0 * (0.05 + 0.95 * 0.10) = 15 * 0.145 = 2.175
    assert abs(score.raw_score - (100.0 - 2.175)) < 1e-6


def test_multi_dataset_scan_independent_denominators():
    """10. In a multi-dataset scan, each dataset issue uses its own dataset row count."""
    ds1_prof = DatasetProfile(name="dataset_A", row_count=50, column_count=2, columns=[])
    ds2_prof = DatasetProfile(name="dataset_B", row_count=500, column_count=2, columns=[])

    result = AnalysisResult(
        run_id="multi_run",
        timestamp="2026-08-26T10:00:00",
        datasets=[ds1_prof, ds2_prof],
        enabled_checks=["whitespace"],
    )
    result.whitespace_results = [
        WhitespaceResult(
            dataset_name="dataset_A",
            per_column=[{"column": "ColA", "total_affected": 5, "affected_rows": 5, "severity": "Low"}],
        ),
        WhitespaceResult(
            dataset_name="dataset_B",
            per_column=[{"column": "ColB", "total_affected": 5, "affected_rows": 5, "severity": "Low"}],
        ),
    ]

    score = calculate_score(result)
    assert len(score.breakdown.items) == 2
    itemA = next(i for i in score.breakdown.items if i.dataset_name == "dataset_A")
    itemB = next(i for i in score.breakdown.items if i.dataset_name == "dataset_B")

    assert itemA.total_records == 50
    assert abs(itemA.affected_ratio - (5 / 50)) < 1e-6  # 10% affected
    assert itemB.total_records == 500
    assert abs(itemB.affected_ratio - (5 / 500)) < 1e-6  # 1% affected

    # Item A has higher penalty than Item B because volume affected ratio is 10% vs 1%
    assert itemA.penalty > itemB.penalty


# ---------------------------------------------------------------------------
# Boundary & Precision Tests
# ---------------------------------------------------------------------------

def test_score_lower_bound_clamped_at_zero():
    """11. Total penalties exceeding 100 clamp the score at 0.0."""
    result = _make_base_result(row_count=100)
    result.mandatory_field_results = [
        MandatoryFieldResult(
            dataset_name="test_ds",
            mandatory_fields=[f"Field_{i}" for i in range(10)],
            failing_record_count=100,
            total_records=100,
            failing_pct=100.0,
            per_field=[{"field": f"Field_{i}", "missing_count": 100, "missing_pct": 100.0} for i in range(10)],
            severity=Severity.CRITICAL,
        )
    ]
    # 10 Critical issues with 100% volume = 10 * 15.0 = 150 penalty points
    score = calculate_score(result)
    assert score.raw_score == 0.0
    assert score.overall == 0.0
    assert score.category == ReadinessCategory.NOT_READY
    assert score.breakdown.total_penalty == 150.0


def test_score_reconciliation_breakdown_helper():
    """12. score.breakdown provides explicit transparent penalty breakdown."""
    result = _make_base_result(row_count=200)
    result.date_results = [
        DateResult(
            dataset_name="test_ds",
            per_column=[{
                "column": "Date1",
                "invalid_count": 4,
                "severity": "High",
            }],
        )
    ]
    score = calculate_score(result)

    assert score.breakdown is not None
    assert len(score.breakdown.items) == 1
    item = score.breakdown.items[0]
    assert item.category == "Dates"
    assert item.target == "Date1"
    assert item.severity == "High"
    assert abs(score.raw_score - (100.0 - score.breakdown.total_penalty)) < 1e-9
