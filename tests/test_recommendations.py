"""
Tests for core/recommendations/recommender.py
"""
import pytest

from core.models import (
    AnalysisResult, DatasetProfile,
    DuplicateResult, MandatoryFieldResult,
    Severity,
)
from core.recommendations.recommender import generate_recommendations


def test_recommendations_prioritized():
    profile = DatasetProfile(name="test", row_count=100, column_count=2, columns=[], duplicate_row_count=5, duplicate_row_pct=5.0, overall_null_pct=5.0)
    result = AnalysisResult(
        run_id="rec1",
        timestamp="2026-08-18T10:00:00",
        datasets=[profile],
        enabled_checks=["duplicates", "mandatory_fields"],
        duplicate_results=[DuplicateResult(
            dataset_name="test",
            full_row_duplicate_count=5,
            full_row_duplicate_pct=5.0,
            severity=Severity.HIGH,
        )],
        mandatory_field_results=[MandatoryFieldResult(
            dataset_name="test",
            mandatory_fields=["Name"],
            failing_record_count=10,
            total_records=100,
            failing_pct=10.0,
            per_field=[{"field": "Name", "missing_count": 10, "missing_pct": 10.0}],
            severity=Severity.CRITICAL,
        )],
    )

    recs = generate_recommendations(result)
    assert len(recs) == 2
    # Critical should be first
    assert recs[0].severity == Severity.CRITICAL
    assert recs[0].issue_type == "mandatory_fields"
    assert recs[1].severity == Severity.HIGH
    assert recs[1].issue_type == "duplicates_full_row"
