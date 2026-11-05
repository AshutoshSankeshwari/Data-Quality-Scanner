"""
Tests for core/checks/mandatory_fields.py
"""
import pytest
import pandas as pd

from core.checks.mandatory_fields import check_mandatory_fields
from core.models import Severity


def test_mandatory_fields_all_present():
    df = pd.DataFrame({
        "ID": ["1", "2", "3"],
        "Name": ["Alice", "Bob", "Charlie"],
    })
    res = check_mandatory_fields(df, mandatory_fields=["ID", "Name"], dataset_name="clean")
    assert not res.has_issues()
    assert res.failing_record_count == 0
    assert res.failing_pct == 0.0
    assert res.severity == Severity.INFO


def test_mandatory_fields_failures():
    df = pd.DataFrame({
        "ID": ["1", "2", "3", "4"],
        "Name": ["Alice", None, "Charlie", "  "],
        "Email": ["a@a.com", "b@b.com", "", "d@d.com"],
    })
    res = check_mandatory_fields(df, mandatory_fields=["Name", "Email"], dataset_name="dirty")
    assert res.has_issues()
    # Row 1 (Bob): Name is None -> fails
    # Row 2 (Charlie): Email is "" -> fails
    # Row 3 (row index 3): Name is "  " -> fails
    # Row 0: passes
    assert res.failing_record_count == 3
    assert res.failing_pct == 75.0
    assert res.severity == Severity.CRITICAL


def test_mandatory_fields_missing_column():
    df = pd.DataFrame({
        "ID": ["1", "2"],
    })
    # 'Phone' is not in df
    res = check_mandatory_fields(df, mandatory_fields=["ID", "Phone"], dataset_name="missing_col")
    phone_res = next(f for f in res.per_field if f["field"] == "Phone")
    assert phone_res["missing_count"] == -1
    assert "warning" in phone_res
