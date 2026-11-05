"""
Tests for core/checks/relationships.py and core/checks/relationship_discovery.py
"""
import pytest
import pandas as pd
from pathlib import Path

from core.checks.relationships import check_relationships
from core.checks.relationship_discovery import detect_and_validate_relationships
from core.service import AnalysisService, AnalysisConfig
from core.ingestion.loader import load_csv
from core.models import Severity

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def test_relationships_clean():
    """1. Two datasets with a valid relationship and zero integrity errors (controlled fixture)."""
    parent_df = pd.DataFrame({"CustomerID": ["C1", "C2", "C3"]})
    child_df = pd.DataFrame({"OrderID": ["O1", "O2", "O3"], "CustomerID": ["C1", "C2", "C1"]})

    res = check_relationships(
        parent_df, child_df,
        parent_key="CustomerID", child_key="CustomerID",
        parent_dataset_name="Customers", child_dataset_name="Orders",
    )
    assert not res.has_issues()
    assert res.orphan_count == 0
    assert res.orphan_pct == 0.0
    assert res.severity == Severity.INFO
    assert res.status == "PASSED"
    assert res.origin == "configured"
    assert res.origin_display == "Configured Rule"


def test_relationships_orphans_detected():
    """2. Relationship with invalid child references."""
    parent_df = pd.DataFrame({"CustomerID": ["C1", "C2"]})
    child_df = pd.DataFrame({"OrderID": ["O1", "O2", "O3"], "CustomerID": ["C1", "C999", "C888"]})

    res = check_relationships(
        parent_df, child_df,
        parent_key="CustomerID", child_key="CustomerID",
        parent_dataset_name="Customers", child_dataset_name="Orders",
    )
    assert res.has_issues()
    assert res.orphan_count == 2
    assert res.orphan_pct == round(100.0 * 2 / 3, 2)
    assert res.severity == Severity.CRITICAL
    assert res.status == "FAILED"
    assert len(res.sample_orphan_records) == 2
    assert res.sample_orphan_records[0]["key_value"] == "C999"
    assert res.sample_orphan_records[0]["row_number"] == 2
    assert res.sample_orphan_records[1]["key_value"] == "C888"
    assert res.sample_orphan_records[1]["row_number"] == 3


def test_relationships_composite_key():
    parent_df = pd.DataFrame({
        "OrgID": ["O1", "O1", "O2"],
        "DeptID": ["D1", "D2", "D1"],
    })
    child_df = pd.DataFrame({
        "EmpID": ["E1", "E2", "E3"],
        "OrgID": ["O1", "O1", "O3"],  # O3-D1 is orphan
        "DeptID": ["D1", "D99", "D1"], # O1-D99 is orphan
    })
    res = check_relationships(
        parent_df, child_df,
        parent_key=["OrgID", "DeptID"], child_key=["OrgID", "DeptID"],
        parent_dataset_name="Depts", child_dataset_name="Employees",
    )
    assert res.has_issues()
    assert res.orphan_count == 2


# ---------------------------------------------------------------------------
# Automatic Relationship Detection & Integrity Validation Tests
# ---------------------------------------------------------------------------

def test_automatic_detection_and_integrity_orphans():
    """Automatic detection on dataset pair identifying invalid references."""
    parent_df = pd.DataFrame({
        "Customer_ID": [f"CUST{i:04d}" for i in range(1, 101)],
        "Customer_Name": [f"Customer {i}" for i in range(1, 101)],
    })
    child_df = pd.DataFrame({
        "Order_ID": [f"ORD{i:04d}" for i in range(1, 121)],
        "Customer_ID": [f"CUST{((i * 3) % 80) + 1:04d}" if i <= 100 else f"CUST99{i:02d}" for i in range(1, 121)],
    })

    results = detect_and_validate_relationships([("customers", parent_df), ("orders", child_df)])
    assert len(results) >= 1
    rel = results[0]
    assert rel.parent_dataset == "customers"
    assert rel.parent_key == "Customer_ID"
    assert rel.child_dataset == "orders"
    assert rel.child_key == "Customer_ID"
    assert rel.origin == "automatic"
    assert rel.origin_display == "Automatically Detected"
    assert rel.is_automatically_detected is True
    assert rel.orphan_count == 20
    assert rel.status == "FAILED"
    assert len(rel.sample_orphan_records) == 20
    assert rel.sample_orphan_records[0]["key_value"] == "CUST99101"
    assert rel.sample_orphan_records[0]["row_number"] == 101


def test_automatic_detection_clean_pair():
    """Automatic detection on perfectly valid parent-child dataset pair (0 invalid references)."""
    parent_df = pd.DataFrame({
        "Customer_ID": [f"CUST{i:04d}" for i in range(1, 101)],
        "Customer_Name": [f"Customer {i}" for i in range(1, 101)],
    })
    child_df = pd.DataFrame({
        "Order_ID": [f"ORD{i:04d}" for i in range(1, 101)],
        "Customer_ID": [f"CUST{((i * 3) % 40) + 1:04d}" for i in range(1, 101)],
    })

    results = detect_and_validate_relationships([("customers", parent_df), ("orders", child_df)])
    assert len(results) == 1
    rel = results[0]
    assert rel.parent_dataset == "customers"
    assert rel.child_dataset == "orders"
    assert rel.orphan_count == 0
    assert rel.status == "PASSED"
    assert rel.origin == "automatic"
    assert rel.origin_display == "Automatically Detected"
    assert rel.is_automatically_detected is True


def test_automatic_detection_filters_non_relational():
    """Categorical columns such as Country and Status must not be detected as relationships."""
    df_a = pd.DataFrame({
        "Country": ["USA", "UK", "Canada", "Germany"],
        "Status": ["Active", "Pending", "Closed", "Archived"],
    })
    df_b = pd.DataFrame({
        "Country": ["USA", "UK", "Canada", "Germany", "France"],
        "Status": ["Active", "Pending", "Closed", "Archived", "Active"],
    })

    results = detect_and_validate_relationships([("table_a", df_a), ("table_b", df_b)])
    assert len(results) == 0


def test_automatic_detection_rejects_low_parent_uniqueness():
    parent_df = pd.DataFrame({
        "Category_ID": ["CAT1", "CAT1", "CAT1", "CAT2", "CAT2"],  # Low uniqueness (0.4)
        "Item_Name": ["A", "B", "C", "D", "E"],
    })
    child_df = pd.DataFrame({
        "Item_ID": ["I1", "I2", "I3"],
        "Category_ID": ["CAT1", "CAT2", "CAT1"],
    })

    results = detect_and_validate_relationships([("catalog", parent_df), ("items", child_df)])
    assert len(results) == 0


# ---------------------------------------------------------------------------
# Origin Labeling & Deduplication Tests
# ---------------------------------------------------------------------------

def test_relationship_origin_configured_with_automatic_confirmation():
    """CASE 1 & 3: Configured relationship + automatic confirmation of the same relationship."""
    df_clean = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    df_orders = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")

    cfg = AnalysisConfig()
    cfg.relationships = [{
        "parent_dataset": "customers_clean_100pct",
        "parent_key": "Customer_ID",
        "child_dataset": "orders_related_to_customers",
        "child_key": "Customer_ID",
        "description": "Orders must reference a valid Customer",
    }]

    service = AnalysisService()
    result = service.run([("customers_clean_100pct", df_clean), ("orders_related_to_customers", df_orders)], cfg)

    # Must produce exactly ONE relationship result
    assert len(result.relationship_results) == 1
    rel = result.relationship_results[0]

    # Origin must be Configured Rule (authoritative), confirmed internally
    assert rel.origin == "configured"
    assert rel.origin_display == "Configured Rule"
    assert rel.is_automatically_detected is False
    assert rel.automatically_confirmed is True

    # Integrity verification
    assert rel.orphan_count == 20
    assert rel.status == "FAILED"
    assert round(rel.orphan_pct, 1) == 13.3

    # Recommendations must not be duplicated
    rel_recs = [r for r in result.recommendations if r.issue_type == "relationship_orphans"]
    assert len(rel_recs) == 1


def test_relationship_origin_automatic_only_without_config():
    """CASE 2: No configured relationship + automatic detection identifies relationship."""
    df_clean = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    df_orders = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")

    cfg = AnalysisConfig()
    cfg.relationships = []  # No configured relationships

    service = AnalysisService()
    result = service.run([("customers_clean_100pct", df_clean), ("orders_related_to_customers", df_orders)], cfg)

    assert len(result.relationship_results) == 1
    rel = result.relationship_results[0]

    # Origin must be Automatically Detected
    assert rel.origin == "automatic"
    assert rel.origin_display == "Automatically Detected"
    assert rel.is_automatically_detected is True
    assert rel.automatically_confirmed is False

    # Integrity verification matches configured results identically
    assert rel.orphan_count == 20
    assert rel.status == "FAILED"
    assert round(rel.orphan_pct, 1) == 13.3
    assert len(rel.sample_orphan_records) == 20
