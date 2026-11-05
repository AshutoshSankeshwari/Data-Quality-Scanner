"""
Tests for core/checks/nulls.py
"""
import pytest
import pandas as pd
import numpy as np

from core.checks.nulls import check_nulls_and_blanks
from core.models import Severity


def test_nulls_and_blanks_detection():
    df = pd.DataFrame({
        "ColA": ["A", None, "", "   ", "B"],
        "ColB": [1, 2, 3, 4, 5],
    })
    res = check_nulls_and_blanks(df, dataset_name="test_data", mandatory_fields=["ColA"])

    assert res.has_issues()
    assert len(res.per_column) == 2

    col_a = next(c for c in res.per_column if c["column"] == "ColA")
    assert col_a["null_count"] == 1
    assert col_a["blank_count"] == 1
    assert col_a["whitespace_only_count"] == 1
    assert col_a["null_pct"] == 20.0
    assert col_a["blank_pct"] == 20.0
    assert col_a["whitespace_only_pct"] == 20.0
    assert col_a["is_mandatory"] is True
    assert col_a["severity"] == Severity.CRITICAL.value

    col_b = next(c for c in res.per_column if c["column"] == "ColB")
    assert col_b["null_count"] == 0
    assert col_b["blank_count"] == 0
    assert col_b["whitespace_only_count"] == 0
    assert col_b["severity"] == Severity.INFO.value
