"""
Tests for core/checks/patterns.py
"""
import pytest
import pandas as pd

from core.checks.patterns import (
    check_patterns,
    _to_structural_mask,
    _to_case_normalized_mask,
)


def test_shape_mask_conversions():
    assert _to_structural_mask("ABC-001") == "AAA-999"
    assert _to_structural_mask("abc_001") == "aaa_999"
    assert _to_structural_mask("ABC001") == "AAA999"

    assert _to_case_normalized_mask("ABC-001") == "AAA-999"
    assert _to_case_normalized_mask("abc-001") == "AAA-999"


from core.models import Severity


def test_pattern_consistency_clean():
    df = pd.DataFrame({
        "Code": ["ABC-001", "DEF-002", "GHI-003", "JKL-004"],
    })
    res = check_patterns(df, min_cluster_size=1, dataset_name="clean")
    assert not res.has_issues()
    assert len(res.per_column) == 0
    assert res.severity == Severity.INFO


def test_pattern_inconsistency_structural_and_case():
    df = pd.DataFrame({
        "Code": [
            "ABC-001", "DEF-002", "GHI-003", "JKL-004",  # AAA-999 (dominant)
            "abc-005", "def-006",                        # aaa-999 (case deviation)
            "ABC007", "DEF008",                          # AAA999 (structural deviation)
        ],
    })
    res = check_patterns(df, min_cluster_size=2, dataset_name="dirty")
    assert res.has_issues()
    assert res.severity == Severity.LOW
    assert len(res.per_column) == 1

    code_res = res.per_column[0]
    assert code_res["dominant_pattern"] == "AAA-999"
    assert code_res["has_case_inconsistency"] is True
    assert code_res["has_structural_inconsistency"] is True
    assert code_res["severity"] == "Low"
    assert len(code_res["clusters"]) == 3
