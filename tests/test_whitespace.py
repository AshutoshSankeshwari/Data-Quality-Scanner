"""
Tests for core/checks/whitespace.py
"""
import pytest
import pandas as pd

from core.checks.whitespace import check_whitespace


from core.models import Severity


def test_whitespace_clean():
    df = pd.DataFrame({
        "Name": ["Alice", "Bob", "Charlie"],
        "City": ["New York", "London", "Paris"],
    })
    res = check_whitespace(df, "clean")
    assert not res.has_issues()
    assert len(res.per_column) == 0
    assert res.severity == Severity.INFO


def test_whitespace_anomalies_detected():
    df = pd.DataFrame({
        "Name": [" Alice", "Bob ", "Charlie   Brown", "David"],
        "Age": [20, 30, 40, 50],
    })
    res = check_whitespace(df, "dirty")
    assert res.has_issues()
    assert res.severity == Severity.LOW
    assert len(res.per_column) == 1

    name_col = res.per_column[0]
    assert name_col["column"] == "Name"
    assert name_col["leading_count"] == 1
    assert name_col["trailing_count"] == 1
    assert name_col["multi_internal_count"] == 1
    assert name_col["severity"] == "Low"
    assert len(name_col["sample_values"]) == 3
