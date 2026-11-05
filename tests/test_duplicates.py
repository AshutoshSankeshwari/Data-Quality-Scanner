"""
Tests for core/checks/duplicates.py
"""
import pytest
import pandas as pd

from core.checks.duplicates import (
    check_full_row_duplicates,
    check_key_based_duplicates,
)
from core.models import Severity


def test_full_row_duplicates_none():
    df = pd.DataFrame({
        "A": [1, 2, 3],
        "B": ["x", "y", "z"],
    })
    res = check_full_row_duplicates(df, "clean_df")
    assert res.full_row_duplicate_count == 0
    assert res.full_row_duplicate_pct == 0.0
    assert res.severity == Severity.INFO
    assert not res.has_issues()


def test_full_row_duplicates_detected():
    df = pd.DataFrame({
        "A": [1, 2, 2, 3],
        "B": ["x", "y", "y", "z"],
    })
    res = check_full_row_duplicates(df, "dirty_df")
    assert res.full_row_duplicate_count == 1
    assert res.full_row_duplicate_pct == 25.0
    assert res.severity == Severity.HIGH  # > 5%
    assert res.has_issues()


def test_key_based_duplicates():
    df = pd.DataFrame({
        "ID": ["C1", "C2", "C2", "C3"],
        "Name": ["Alice", "Bob", "Robert", "Charlie"],
    })
    res = check_key_based_duplicates(df, key_columns=[["ID"]], dataset_name="customers")
    assert res.has_issues()
    assert len(res.key_based_results) == 1
    kb = res.key_based_results[0]
    assert kb["key_columns"] == ["ID"]
    assert kb["duplicate_count"] == 1
    assert kb["duplicate_pct"] == 25.0


def test_duplicate_severity_tiers_full_row():
    # 0% -> INFO
    df_0 = pd.DataFrame({"id": list(range(100)), "val": ["x"] * 100})
    res_0 = check_full_row_duplicates(df_0)
    assert res_0.severity == Severity.INFO

    # 0.99% (<=1.0%) -> LOW
    df_low = pd.DataFrame({"id": list(range(100)) + [1], "val": ["x"] * 101})
    res_low = check_full_row_duplicates(df_low)
    assert res_low.severity == Severity.LOW

    # 2.9% (1.0% < x <= 5.0%) -> MEDIUM
    df_med = pd.DataFrame({"id": list(range(100)) + [1, 2, 3], "val": ["x"] * 103})
    res_med = check_full_row_duplicates(df_med)
    assert res_med.severity == Severity.MEDIUM

    # 9.1% (>5.0%) -> HIGH
    df_high = pd.DataFrame({"id": list(range(100)) + [1] * 10, "val": ["x"] * 110})
    res_high = check_full_row_duplicates(df_high)
    assert res_high.severity == Severity.HIGH


def test_duplicate_severity_tiers_key_based():
    # 0% -> INFO
    df_0 = pd.DataFrame({"id": list(range(100)), "val": list(range(100))})
    res_0 = check_key_based_duplicates(df_0, key_columns=[["id"]])
    assert res_0.severity == Severity.INFO

    # 0.99% (<=1.0%) -> LOW
    df_low = pd.DataFrame({"id": list(range(100)) + [1], "val": list(range(101))})
    res_low = check_key_based_duplicates(df_low, key_columns=[["id"]])
    assert res_low.severity == Severity.LOW

    # 2.9% (1.0% < x <= 5.0%) -> MEDIUM
    df_med = pd.DataFrame({"id": list(range(100)) + [1, 2, 3], "val": list(range(103))})
    res_med = check_key_based_duplicates(df_med, key_columns=[["id"]])
    assert res_med.severity == Severity.MEDIUM

    # 9.1% (>5.0%) -> HIGH
    df_high = pd.DataFrame({"id": list(range(100)) + [1] * 10, "val": list(range(110))})
    res_high = check_key_based_duplicates(df_high, key_columns=[["id"]])
    assert res_high.severity == Severity.HIGH


def test_duplicate_thresholds_configured_via_analysis_config():
    from core.service import AnalysisService, AnalysisConfig
    # 20% duplicates: default config (high=5.0) yields HIGH
    df = pd.DataFrame({"id": [1, 2, 3, 4, 4], "val": ["a", "b", "c", "d", "d"]}) # 1 dup out of 5 = 20%
    
    srv = AnalysisService()
    res_default = srv.run([("test_ds", df)], config=AnalysisConfig())
    assert res_default.duplicate_results[0].severity == Severity.HIGH

    # Custom config: high=30.0, medium=10.0 -> 20% is now MEDIUM
    cfg_custom = AnalysisConfig(duplicate_high_threshold=30.0, duplicate_medium_threshold=10.0)
    res_custom = srv.run([("test_ds", df)], config=cfg_custom)
    assert res_custom.duplicate_results[0].severity == Severity.MEDIUM

