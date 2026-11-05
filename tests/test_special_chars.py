"""
Tests for core/checks/special_chars.py
"""
import pytest
import pandas as pd

from core.checks.special_chars import check_special_chars


def test_special_chars_opt_in():
    df = pd.DataFrame({
        "Customer_ID": ["CUST-100", "CUST#999!"],
        "Notes": ["Some special chars #$%^&*()", "Notes 2"],
    })
    # Field rules only apply to Customer_ID; Notes should be ignored
    field_rules = {"Customer_ID": "alpha_numeric_hyphen"}
    res = check_special_chars(df, field_rules=field_rules, dataset_name="customers")

    assert res.has_issues()
    assert len(res.per_column) == 1
    cid = res.per_column[0]
    assert cid["column"] == "Customer_ID"
    assert cid["violation_count"] == 1
    assert "CUST#999!" in cid["sample_offenders"]


def test_special_chars_email():
    df = pd.DataFrame({
        "Email": ["valid@test.com", "another.user@domain.co.uk", "bad@@domain", "no-at-sign"],
    })
    field_rules = {"Email": "email_format"}
    res = check_special_chars(df, field_rules=field_rules, dataset_name="emails")

    assert res.has_issues()
    assert len(res.per_column) == 1
    em = res.per_column[0]
    assert em["violation_count"] == 2
    assert em["violation_pct"] == 50.0


def test_special_chars_anomaly_detection():
    df = pd.DataFrame({
        "Customer_Name": ["John Doe", "Jane$Doe", "Bob@Smith", "Alice Cooper"],
        "City": ["New York", "Chicago", "Boston", "San Francisco"],
    })
    anomaly_chars = ["$", "@", "#", "%"]
    res = check_special_chars(df, anomaly_characters=anomaly_chars, dataset_name="customers")

    assert res.has_issues()
    assert len(res.per_column) == 1
    col_info = res.per_column[0]
    assert col_info["column"] == "Customer_Name"
    assert col_info["rule_name"] == "anomaly_characters"
    assert col_info["violation_count"] == 2
    assert "Jane$Doe" in col_info["sample_offenders"]
    assert "Bob@Smith" in col_info["sample_offenders"]

