"""
Integration tests for the full Core Data Quality Engine pipeline.
"""
import pytest
from pathlib import Path

from core.service import AnalysisService
from core.ingestion.loader import load_csv
from rules.config_loader import build_analysis_config_from_v2
from core.models import ReadinessCategory

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
CONFIG_DIR = Path(__file__).parent.parent / "config"


def test_full_pipeline_clean_dataset():
    df_clean = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    service = AnalysisService()

    cfg = build_analysis_config_from_v2(
        config_path=CONFIG_DIR / "config.yaml",
        mandatory_fields_profile="Customer_Master",
    )

    result = service.run(
        datasets=[("customers_clean_100pct", df_clean)],
        config=cfg,
    )

    assert len(result.datasets) == 1
    assert result.score is not None
    # Clean dataset should have 100% score
    assert result.score.overall >= 99.0
    assert result.score.category == ReadinessCategory.READY
    assert result.score.blocker_count == 0


def test_full_pipeline_faulty_with_relationships():
    df_faulty = load_csv(SAMPLES_DIR / "customers_faulty.csv")
    df_orders = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")
    service = AnalysisService()

    cfg = build_analysis_config_from_v2(
        config_path=CONFIG_DIR / "config.yaml",
        mandatory_fields_profile="Customer_Master",
    )
    cfg.duplicate_key_sets = [["Customer_ID"]]
    cfg.field_character_rules = {
        "Customer_ID": "alpha_numeric_only",
        "Email": "email_format",
    }
    cfg.relationships = [{
        "parent_dataset": "customers_faulty",
        "parent_key": "Customer_ID",
        "child_dataset": "orders_related_to_customers",
        "child_key": "Customer_ID",
        "description": "Orders must reference a valid Customer",
    }]

    progress_events = []
    def on_progress(step, pct):
        progress_events.append((step, pct))

    result = service.run(
        datasets=[("customers_faulty", df_faulty), ("orders_related_to_customers", df_orders)],
        config=cfg,
        progress_callback=on_progress,
    )

    assert len(result.datasets) == 2
    assert len(progress_events) >= 5

    # Check results populated
    assert len(result.duplicate_results) >= 1
    assert result.duplicate_results[0].has_issues()

    assert len(result.null_blank_results) >= 1
    assert result.null_blank_results[0].has_issues()

    assert len(result.mandatory_field_results) >= 1
    assert result.mandatory_field_results[0].has_issues()

    assert len(result.whitespace_results) >= 1
    assert result.whitespace_results[0].has_issues()

    assert len(result.special_char_results) >= 1
    assert result.special_char_results[0].has_issues()

    assert len(result.pattern_results) >= 1

    assert len(result.date_results) >= 1
    assert result.date_results[0].has_issues()

    assert len(result.relationship_results) >= 1
    assert result.relationship_results[0].has_issues()
    assert result.relationship_results[0].orphan_count > 0

    # Score should indicate cleansing needed
    assert result.score is not None
    assert result.score.overall < 95.0

    # Recommendations generated and prioritized
    assert len(result.recommendations) > 0


def test_full_pipeline_v2_config():
    df_clean = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    df_orders = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")
    service = AnalysisService()

    cfg = build_analysis_config_from_v2(
        config_path=CONFIG_DIR / "config.yaml",
        mandatory_fields_profile="Customer_Master",
    )

    result = service.run(
        datasets=[("customers_clean_100pct", df_clean), ("orders_related_to_customers", df_orders)],
        config=cfg,
    )

    assert len(result.datasets) == 2
    # Check diagnostic dimensions are attached
    comp_dim = next(d for d in result.score.dimensions if d.name == "Completeness")
    assert comp_dim.score == 100.0
    assert len(result.relationship_results) == 1
    assert result.relationship_results[0].orphan_count == 20
    assert result.relationship_results[0].origin == "configured"
    assert result.relationship_results[0].origin_display == "Configured Rule"
    assert result.relationship_results[0].status == "FAILED"


def test_end_to_end_severity_consistency_across_layers(tmp_path):
    """
    Verify that the same logical issue retains identical severity across:
    Check result -> Scoring -> Detailed reports -> SQLite storage & restoration.
    """
    from core.models import Severity
    from reports.summary_builder import extract_detailed_issues
    from db.repository import ScanRepository

    df_faulty = load_csv(SAMPLES_DIR / "customers_faulty.csv")
    df_orders = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")
    service = AnalysisService()

    cfg = build_analysis_config_from_v2(
        config_path=CONFIG_DIR / "config.yaml",
        mandatory_fields_profile="Customer_Master",
    )
    cfg.duplicate_key_sets = [["Customer_ID"]]
    cfg.field_character_rules = {"Customer_ID": "alpha_numeric_only", "Email": "email_format"}
    cfg.relationships = [{
        "parent_dataset": "customers_faulty",
        "parent_key": "Customer_ID",
        "child_dataset": "orders_related_to_customers",
        "child_key": "Customer_ID",
    }]

    result = service.run([("customers_faulty", df_faulty), ("orders_related_to_customers", df_orders)], cfg)

    # 1. Engine check result severities
    assert result.whitespace_results[0].severity == Severity.LOW
    assert result.mandatory_field_results[0].severity == Severity.CRITICAL
    assert result.relationship_results[0].severity == Severity.CRITICAL  # 20/200 = 10%

    # 2. Report summary builder extraction
    detailed_issues = extract_detailed_issues(result)
    ws_issue = next(i for i in detailed_issues if i["category"] == "Whitespace Issues")
    assert ws_issue["severity"] == "Low"

    mand_issue = next(i for i in detailed_issues if i["category"] == "Mandatory Fields")
    assert mand_issue["severity"] == "Critical"

    rel_issue = next(i for i in detailed_issues if i["category"] == "Relationship Integrity")
    assert rel_issue["severity"] == "Critical"

    # 3. SQLite persistence & reconstruction
    db_file = str(tmp_path / "test_consistency.db")
    repo = ScanRepository(db_file)
    scan_id = repo.save_scan(result)
    restored = repo.get_scan_result(scan_id)

    assert restored.whitespace_results[0].severity == Severity.LOW
    assert restored.mandatory_field_results[0].severity == Severity.CRITICAL
    assert restored.relationship_results[0].severity == Severity.CRITICAL

