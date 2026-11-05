"""
tests/test_service_inference_resolution.py
Comprehensive automated test suite for V2.5 Rule Resolution Architecture:
"Always honor the rules explicitly defined in config.yaml, then use the automatic
analyzer to discover additional high-confidence rules that are not already defined."

Tests:
1. Mandatory Fields: Config + High-Confidence Inference combination.
2. Duplicate Keys: Config + High-Confidence Inference coexistence.
3. Config vs Inference overlap deduplication (one logical rule).
4. Medium / Low / Uncertain inference not automatically activated.
5. Explicit config retention (even if inference gave low/omitted).
6. Config-free execution with autonomous high-confidence activation.
7. Scoring deduplication (no duplicate penalties).
8. Wide dataset evaluation (retaining config, filling gaps, rejecting categoricals).
"""
import pytest
import pandas as pd

from core.service import AnalysisService, AnalysisConfig


# ---------------------------------------------------------------------------
# 1. Mandatory Fields Resolution (Config + High-Confidence Inferred)
# ---------------------------------------------------------------------------

def test_mandatory_config_plus_inference_combination():
    """Verify that configured mandatory fields are retained AND high-confidence inferred fields are added."""
    # Dataset with Email (configured), ContractNumber (inferred High), HolderName (Medium), Notes (Low)
    df = pd.DataFrame({
        "Email": [f"user_{i}@test.com" for i in range(50)],
        "ContractNumber": [f"CTR-{i:04d}" for i in range(50)],
        "HolderName": [f"Person {i % 40}" for i in range(50)],
        "Notes": [None] * 50,
    })

    cfg = AnalysisConfig(mandatory_fields=["Email"])
    service = AnalysisService()
    result = service.run([("contracts_test", df)], config=cfg)

    # Inferred rules internally generated
    inf = result.inferred_rules[0]
    inf_mand_names = {f.column_name: f.confidence for f in inf.mandatory_fields}
    assert inf_mand_names.get("ContractNumber") == "High"

    # Mandatory field check must contain BOTH Email (configured) and ContractNumber (inferred High)
    assert len(result.mandatory_field_results) == 1
    mf = result.mandatory_field_results[0]
    assert "Email" in mf.mandatory_fields
    assert "ContractNumber" in mf.mandatory_fields
    # Medium/Low/Uncertain fields must NOT be added
    assert "Notes" not in mf.mandatory_fields


# ---------------------------------------------------------------------------
# 2. Duplicate / Identity Keys Resolution (Config + High-Confidence Inferred)
# ---------------------------------------------------------------------------

def test_duplicate_keys_config_plus_inference_coexistence():
    """Verify that configured identity keys and high-confidence inferred keys coexist as independent rules."""
    # Dataset with Email (configured duplicate key) and ContractNumber (inferred High identity key)
    # Email has 2 duplicates; ContractNumber has 2 duplicates at different rows
    emails = [f"user_{i}@test.com" for i in range(48)] + ["user_0@test.com", "user_1@test.com"]
    contracts = [f"CTR-{i:04d}" for i in range(1, 49)] + ["CTR-0001", "CTR-0002"]
    df = pd.DataFrame({
        "Email": emails,
        "ContractNumber": contracts,
        "City": ["London"] * 50,
        "Notes": ["note"] * 50,
    })

    cfg = AnalysisConfig(duplicate_key_sets=[["Email"]])
    service = AnalysisService()
    result = service.run([("accounts_test", df)], config=cfg)

    # Duplicate check must evaluate BOTH Email and ContractNumber as independent key sets
    assert len(result.duplicate_results) == 1
    dr = result.duplicate_results[0]
    assert len(dr.key_based_results) == 2

    key_sets = [r["key_columns"] for r in dr.key_based_results]
    assert ["Email"] in key_sets
    assert ["ContractNumber"] in key_sets

    # NOT merged into composite ['Email', 'ContractNumber']
    assert ["Email", "ContractNumber"] not in key_sets

    # Both independent rules detected their respective duplicates
    for kb in dr.key_based_results:
        assert kb["duplicate_count"] == 2


# ---------------------------------------------------------------------------
# 3. Config vs Inference Overlap Deduplication
# ---------------------------------------------------------------------------

def test_config_vs_inference_overlap_deduplication():
    """Verify that when a rule exists in config and is also inferred as High, it is not duplicated."""
    df = pd.DataFrame({
        "Customer_ID": [f"CUST{i:03d}" for i in range(50)],
        "City": ["Berlin"] * 50,
    })

    # Config declares Customer_ID as mandatory and duplicate key
    cfg = AnalysisConfig(
        mandatory_fields=["Customer_ID"],
        duplicate_key_sets=[["Customer_ID"]],
    )
    service = AnalysisService()
    result = service.run([("customers_test", df)], config=cfg)

    # Mandatory field check contains Customer_ID exactly once
    assert len(result.mandatory_field_results) == 1
    mf = result.mandatory_field_results[0]
    assert mf.mandatory_fields == ["Customer_ID"]
    assert len(mf.mandatory_fields) == 1

    # Duplicate check contains ['Customer_ID'] exactly once
    assert len(result.duplicate_results) == 1
    dr = result.duplicate_results[0]
    assert len(dr.key_based_results) == 1
    assert dr.key_based_results[0]["key_columns"] == ["Customer_ID"]


# ---------------------------------------------------------------------------
# 4. Medium / Low / Uncertain Inferences Not Activated
# ---------------------------------------------------------------------------

def test_medium_and_low_confidence_inferred_rules_not_automatically_activated():
    """Verify that medium/low confidence inferences do not become active duplicate keys or mandatory rules."""
    df = pd.DataFrame({
        "Client_Name": [f"Client {i}" for i in range(50)],  # Entity name (rejected as identity key)
        "City": ["London", "Paris", "Tokyo", "Berlin", "Rome"] * 10,  # Low/Categorical
        "Comments": ["Good feedback"] * 50,  # Low/Free text
    })

    service = AnalysisService()
    result = service.run([("contacts_dataset", df)], config=None)

    # Inferred rules exist in result
    inf = result.inferred_rules[0]
    assert inf.suggested_identity_key is None or inf.suggested_identity_key.confidence != "High"

    # Because no high-confidence key exists, duplicate check falls back to full-row duplicates
    dr = result.duplicate_results[0]
    assert dr.key_based_results == []
    assert dr.full_row_duplicate_count == 0

    # City and Comments are not mandatory
    if result.mandatory_field_results:
        mf = result.mandatory_field_results[0]
        assert "City" not in mf.mandatory_fields
        assert "Comments" not in mf.mandatory_fields


# ---------------------------------------------------------------------------
# 5. Explicit Config Retention (Even if Inference Did Not Flag It)
# ---------------------------------------------------------------------------

def test_explicit_config_retention_when_unflagged_by_inference():
    """Verify explicit config rule (e.g. Custom_Tag) remains active even if inference does not infer it."""
    df = pd.DataFrame({
        "User_Code": [f"CODE_{i:03d}" for i in range(50)],
        "Custom_Tag": ["TAG_A", "TAG_B"] * 25,  # Categorical: inference would NOT infer this as mandatory
    })

    # User explicitly declares Custom_Tag as mandatory
    cfg = AnalysisConfig(mandatory_fields=["Custom_Tag"])
    service = AnalysisService()
    result = service.run([("users_test", df)], config=cfg)

    # Effective mandatory fields must contain Custom_Tag (configured) + User_Code (inferred High:
    # 'code' Tier-1 token + 100% populated + high uniqueness = 0.70)
    assert len(result.mandatory_field_results) == 1
    mf = result.mandatory_field_results[0]
    assert "Custom_Tag" in mf.mandatory_fields
    assert "User_Code" in mf.mandatory_fields


# ---------------------------------------------------------------------------
# 6. Config-Free Execution
# ---------------------------------------------------------------------------

def test_config_free_autonomous_activation():
    """Verify config-free mode activates high-confidence inferred rules."""
    df = pd.DataFrame({
        "Customer_ID": [f"CUST{i:03d}" for i in range(1, 49)] + ["CUST001", "CUST002"],
        "Full_Name": [f"Person {i}" for i in range(1, 51)],
        "City": ["London"] * 50,
        "Notes": [None] * 50,
    })

    service = AnalysisService()
    result = service.run([("customers_test", df)], config=None)

    # Inferred Customer_ID activated for key duplicates
    assert len(result.duplicate_results) == 1
    dr = result.duplicate_results[0]
    assert len(dr.key_based_results) == 1
    assert dr.key_based_results[0]["key_columns"] == ["Customer_ID"]
    assert dr.key_based_results[0]["duplicate_count"] == 2

    # Inferred Customer_ID activated for mandatory (Tier-1 'id' token + high uniqueness = High)
    # Full_Name: Tier-3 name token (anchor 0.10 < 0.15 gate) → capped at Medium ceiling.
    # Under the recalibrated engine, Full_Name does NOT reach High mandatory confidence.
    assert len(result.mandatory_field_results) == 1
    mf = result.mandatory_field_results[0]
    assert "Customer_ID" in mf.mandatory_fields
    assert "Full_Name" not in mf.mandatory_fields  # name-only token does not reach High
    assert "Notes" not in mf.mandatory_fields


# ---------------------------------------------------------------------------
# 7. Duplicate Scoring Safety (No Double Penalties)
# ---------------------------------------------------------------------------

def test_overlapping_configured_and_inferred_rules_no_double_penalty():
    """Verify that when a rule is both in config and inferred, it is evaluated exactly once."""
    cust_ids = [f"C{i}" if i >= 5 else None for i in range(100)]
    df = pd.DataFrame({
        "Customer_ID": cust_ids,
        "City": ["Berlin"] * 100,
    })

    cfg = AnalysisConfig(mandatory_fields=["Customer_ID"])
    service = AnalysisService()
    result = service.run([("customers_overlap", df)], config=cfg)

    # Mandatory field check has Customer_ID
    assert len(result.mandatory_field_results) == 1
    assert result.mandatory_field_results[0].failing_record_count == 5

    # Customer_ID appears in Mandatory Fields as Critical and NOT in Nulls
    breakdown = result.score.breakdown
    assert breakdown is not None
    cust_mandatory = [item for item in breakdown.items if item.target == "Customer_ID" and item.category == "Mandatory Fields"]
    cust_null = [item for item in breakdown.items if item.target == "Customer_ID" and item.category == "Nulls"]
    assert len(cust_mandatory) == 1
    assert len(cust_null) == 0
    assert cust_mandatory[0].severity == "Critical"
    assert cust_mandatory[0].weight == 15.0


# ---------------------------------------------------------------------------
# 8. Wide Dataset Evaluation
# ---------------------------------------------------------------------------

def test_wide_dataset_combined_resolution():
    """Verify combined resolution on wide dataset with 15+ columns."""
    df = pd.DataFrame({
        "Account_Num": [f"ACC-{i:05d}" for i in range(100)],
        "National_ID": [f"NAT-{i:05d}" for i in range(100)],
        "First_Name": [f"First_{i}" for i in range(100)],
        "Last_Name": [f"Last_{i}" for i in range(100)],
        "Email_Address": [f"user_{i}@bank.com" for i in range(100)],
        "City": ["New York", "Chicago", "Boston"] * 33 + ["Miami"],
        "State": ["NY", "IL", "MA"] * 33 + ["FL"],
        "Postal_Code": ["10001", "60601", "02101"] * 33 + ["33101"],
        "Account_Status": ["Active", "Pending"] * 50,
        "Account_Type": ["Checking", "Savings"] * 50,
        "Risk_Category": ["Low", "Medium", "High", "Low"] * 25,
        "Branch_Department": ["Retail", "Commercial"] * 50,
        "Current_Balance": [1000.0 + i * 10.5 for i in range(100)],
        "Transaction_Limit": [5000.0] * 100,
        "Customer_Notes": [f"Customer relationship notes {i}" if i % 2 == 0 else None for i in range(100)],
        "Feedback_Comments": [None] * 100,
    })

    # User explicitly configured only National_ID as a duplicate key and Email_Address as mandatory
    cfg = AnalysisConfig(
        mandatory_fields=["Email_Address"],
        duplicate_key_sets=[["National_ID"]],
    )

    service = AnalysisService()
    result = service.run([("bank_accounts", df)], config=cfg)

    # 1. Mandatory Fields: Email_Address (configured) + Account_Num, National_ID (inferred High)
    mf = result.mandatory_field_results[0]
    assert "Email_Address" in mf.mandatory_fields
    assert "Account_Num" in mf.mandatory_fields
    assert "National_ID" in mf.mandatory_fields
    # Categoricals and free text must NOT be mandatory
    assert "Customer_Notes" not in mf.mandatory_fields
    assert "Feedback_Comments" not in mf.mandatory_fields

    # 2. Duplicate Keys: ['National_ID'] (configured) + ['Account_Num'] (inferred High)
    dr = result.duplicate_results[0]
    key_sets = [r["key_columns"] for r in dr.key_based_results]
    assert ["National_ID"] in key_sets
    assert ["Account_Num"] in key_sets
    # Categoricals and financial metrics must NOT be duplicate keys
    assert ["City"] not in key_sets
    assert ["Account_Status"] not in key_sets
    assert ["Current_Balance"] not in key_sets
