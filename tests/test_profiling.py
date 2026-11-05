"""
Tests for core/profiling/profiler.py
"""
import pytest
import pandas as pd
import numpy as np

from core.profiling.profiler import profile_dataset, profile_column
from core.models import ColumnType


def test_profile_column_numeric():
    series = pd.Series([10, 20, 30, 40, 50], name="Amount")
    prof = profile_column(series)

    assert prof.name == "Amount"
    assert prof.inferred_type == ColumnType.INTEGER
    assert prof.total_count == 5
    assert prof.null_count == 0
    assert prof.numeric_min == 10.0
    assert prof.numeric_max == 50.0
    assert prof.numeric_mean == 30.0


def test_profile_column_nulls_and_blanks():
    series = pd.Series(["Hello", "", "   ", None, "World"], name="TextCol")
    prof = profile_column(series)

    assert prof.name == "TextCol"
    assert prof.total_count == 5
    assert prof.null_count == 1
    assert prof.blank_count == 1
    assert prof.whitespace_only_count == 1
    assert prof.str_min_len == 0  # empty string has len 0
    assert prof.str_max_len == 5


def test_profile_column_date():
    series = pd.Series(["2025-01-01", "2025-06-15", "2025-12-31"], name="OrderDate")
    prof = profile_column(series)

    assert prof.name == "OrderDate"
    assert prof.inferred_type == ColumnType.DATE
    assert prof.date_min == "2025-01-01"
    assert prof.date_max == "2025-12-31"


def test_profile_dataset():
    df = pd.DataFrame({
        "ID": [1, 2, 3, 3],
        "Name": ["Alice", "Bob", "Charlie", "Charlie"],
        "Score": [90.5, 80.0, None, None],
    })
    prof = profile_dataset(df, name="TestDataset")

    assert prof.name == "TestDataset"
    assert prof.row_count == 4
    assert prof.column_count == 3
    assert len(prof.columns) == 3
    assert prof.duplicate_row_count == 1  # row 3 and 4 are identical
    assert prof.duplicate_row_pct == 25.0
    assert prof.overall_null_pct == round(100.0 * 2 / 12, 2)
