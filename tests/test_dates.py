"""
Tests for core/checks/dates.py
"""
import pytest
import pandas as pd

from core.checks.dates import check_dates, _is_impossible_date
from core.models import Severity


def test_is_impossible_date():
    assert _is_impossible_date("2026-02-30") is True
    assert _is_impossible_date("13/40/2026") is True
    assert _is_impossible_date("2026-13-45") is True
    assert _is_impossible_date("2026-01-15") is False
    assert _is_impossible_date("15/01/2026") is False


def test_dates_clean():
    df = pd.DataFrame({
        "Created_Date": ["2025-01-10", "2025-02-15", "2025-03-20"],
    })
    res = check_dates(df, dataset_name="clean")
    assert not res.has_issues()
    assert len(res.per_column) == 1
    d_res = res.per_column[0]
    assert d_res["invalid_count"] == 0
    assert d_res["has_inconsistency"] is False
    assert d_res["dominant_format"] == "%Y-%m-%d"


def test_dates_mixed_formats_and_invalid():
    df = pd.DataFrame({
        "Order_Date": [
            "2025-01-10", "2025-02-15",       # %Y-%m-%d
            "05/20/2025",                     # %m/%d/%Y
            "not-a-date",                     # invalid
            "2025-02-30",                     # impossible date
        ],
    })
    res = check_dates(df, dataset_name="dirty")
    assert res.has_issues()
    assert len(res.per_column) == 1
    d_res = res.per_column[0]
    assert d_res["valid_count"] == 3
    assert d_res["invalid_count"] == 2
    assert d_res["impossible_date_count"] >= 1
    assert d_res["has_inconsistency"] is True
    assert d_res["severity"] == Severity.HIGH.value
