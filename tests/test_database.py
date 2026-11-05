"""
tests/test_database.py
Comprehensive unit and integration tests for Phase 3 SQLite persistence layer.

Verifies:
  1. Automatic database and schema initialization.
  2. Saving single and multi-dataset scans.
  3. Strict verification that RAW dataset rows are NEVER stored.
  4. Listing scan history and order.
  5. Full reconstruction of AnalysisResult dataclasses from SQLite.
  6. Application restart simulation.
  7. Graceful error handling (non-blocking persistence).
  8. Cascade deletion.
  9. GUI integration with HistorySection.
"""
from __future__ import annotations
import os
import sqlite3
import tempfile
from pathlib import Path
import pytest
from PySide6.QtWidgets import QMessageBox

from db.connection import get_connection
from db.repository import ScanRepository
from core.models import AnalysisResult
from core.ingestion.loader import load_csv
from core.service import AnalysisService
from rules.config_loader import build_analysis_config_from_v2
from gui.main_window import MainWindow

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for isolated testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "test_scanner.db"


# ---------------------------------------------------------------------------
# 1. Database Creation & Schema Verification
# ---------------------------------------------------------------------------

def test_db_auto_initialization(temp_db_path):
    """Test that database file and star schema tables are created on first connection."""
    assert not temp_db_path.exists()
    conn = get_connection(temp_db_path)
    assert temp_db_path.exists()

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    expected_tables = [
        "check_results",
        "recommendations",
        "relationship_results",
        "scan_datasets",
        "scans",
        "scoring_factors",
    ]
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' in database"


def test_db_foreign_keys_enabled(temp_db_path):
    """Verify that foreign key enforcement is active."""
    conn = get_connection(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys;")
    fk_status = cursor.fetchone()[0]
    conn.close()
    assert fk_status == 1


# ---------------------------------------------------------------------------
# 2. Saving a Scan & Non-Persistence of Raw Data
# ---------------------------------------------------------------------------

def test_save_and_retrieve_scan(temp_db_path):
    """Test running analysis on samples and saving results to SQLite."""
    repo = ScanRepository(temp_db_path)
    cfg = build_analysis_config_from_v2(CONFIG_PATH)

    df_cust = load_csv(SAMPLES_DIR / "customers_faulty.csv")
    df_ord = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")
    datasets = [("customers_faulty", df_cust), ("orders_related_to_customers", df_ord)]

    result = AnalysisService().run(datasets, cfg)
    scan_id = repo.save_scan(result, config_hash="test_hash_123")

    assert scan_id is not None
    assert scan_id > 0
    assert repo.count_scans() == 1

    # Verify root record
    history = repo.list_scans()
    assert len(history) == 1
    scan_summary = history[0]
    assert scan_summary["run_id"] == result.run_id
    assert scan_summary["dataset_count"] == 2
    assert scan_summary["primary_dataset"] == "customers_faulty"
    assert scan_summary["overall_score"] is not None
    assert scan_summary["readiness_category"] is not None


def test_raw_dataset_rows_never_stored(temp_db_path):
    """
    CRITICAL REQUIREMENT: Verify that raw dataset records are NOT written to SQLite.
    Inspect all tables and columns to ensure only metadata and aggregated stats are stored.
    """
    repo = ScanRepository(temp_db_path)
    cfg = build_analysis_config_from_v2(CONFIG_PATH)

    df = load_csv(SAMPLES_DIR / "customers_faulty.csv")
    result = AnalysisService().run([("customers_faulty", df)], cfg)
    repo.save_scan(result)

    conn = get_connection(temp_db_path)
    cursor = conn.cursor()

    # Check scan_datasets content
    cursor.execute("SELECT * FROM scan_datasets;")
    ds_rows = [dict(r) for r in cursor.fetchall()]
    assert len(ds_rows) == 1
    row = ds_rows[0]

    # Verify columns in scan_datasets
    assert "raw_data" not in row
    assert "data" not in row
    assert "rows_json" not in row
    assert row["row_count"] == 200
    assert row["column_count"] == 7

    # Ensure no customer names or emails from raw dataset exist in any table as raw rows
    cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name LIKE '%raw%';")
    assert cursor.fetchone()[0] == 0

    conn.close()


# ---------------------------------------------------------------------------
# 3. Full Reconstruction of AnalysisResult from SQLite
# ---------------------------------------------------------------------------

def test_reconstruct_analysis_result(temp_db_path):
    """Test that a historical scan can be reconstructed as a full typed AnalysisResult."""
    repo = ScanRepository(temp_db_path)
    cfg = build_analysis_config_from_v2(CONFIG_PATH)

    df_clean = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    df_orders = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")
    original = AnalysisService().run([("customers_clean_100pct", df_clean), ("orders_related_to_customers", df_orders)], cfg)

    scan_id = repo.save_scan(original, config_hash="v2_hash")
    restored = repo.get_scan_result(scan_id)

    assert restored is not None
    assert isinstance(restored, AnalysisResult)
    assert restored.run_id == original.run_id
    assert len(restored.datasets) == 2
    assert restored.primary_dataset().name == "customers_clean_100pct"

    # Score & dimensions
    assert restored.score is not None
    assert abs(restored.score.overall - original.score.overall) < 0.01
    assert restored.score.category == original.score.category
    assert len(restored.score.dimensions) == len(original.score.dimensions)

    # Dimension explanations preserved
    for orig_dim, rest_dim in zip(original.score.dimensions, restored.score.dimensions):
        assert orig_dim.name == rest_dim.name
        assert orig_dim.explanation == rest_dim.explanation

    # Relationships preserved
    assert len(restored.relationship_results) == len(original.relationship_results)
    if original.relationship_results:
        assert restored.relationship_results[0].orphan_count == original.relationship_results[0].orphan_count
        assert restored.relationship_results[0].origin == original.relationship_results[0].origin
        assert restored.relationship_results[0].automatically_confirmed == original.relationship_results[0].automatically_confirmed
        assert len(restored.relationship_results[0].sample_orphan_records) == len(original.relationship_results[0].sample_orphan_records)

    # Recommendations preserved
    assert len(restored.recommendations) == len(original.recommendations)

    # Check results & explicit severities preserved
    if original.whitespace_results:
        assert restored.whitespace_results[0].severity == original.whitespace_results[0].severity
    if original.pattern_results:
        assert restored.pattern_results[0].severity == original.pattern_results[0].severity


# ---------------------------------------------------------------------------
# 4. Application Restart Simulation
# ---------------------------------------------------------------------------

def test_application_restart_simulation(temp_db_path):
    """Simulate app session closing and reopening against the same DB file."""
    # Session 1: Run scan and save
    repo1 = ScanRepository(temp_db_path)
    cfg = build_analysis_config_from_v2(CONFIG_PATH)
    df = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    res = AnalysisService().run([("customers_clean_100pct", df)], cfg)
    scan_id = repo1.save_scan(res)

    # Session 2: New repository instance, load scan
    repo2 = ScanRepository(temp_db_path)
    assert repo2.count_scans() == 1
    scans = repo2.list_scans()
    assert len(scans) == 1
    assert scans[0]["id"] == scan_id

    loaded_result = repo2.get_scan_result(scan_id)
    assert loaded_result is not None
    assert loaded_result.primary_dataset().name == "customers_clean_100pct"


# ---------------------------------------------------------------------------
# 5. Cascade Deletion
# ---------------------------------------------------------------------------

def test_delete_scan_cascade(temp_db_path):
    """Deleting a scan removes related records across child tables."""
    repo = ScanRepository(temp_db_path)
    cfg = build_analysis_config_from_v2(CONFIG_PATH)
    df = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    res = AnalysisService().run([("customers_clean_100pct", df)], cfg)
    scan_id = repo.save_scan(res)

    conn = get_connection(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM scan_datasets WHERE scan_id = ?;", (scan_id,))
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT count(*) FROM scoring_factors WHERE scan_id = ?;", (scan_id,))
    assert cursor.fetchone()[0] == 6
    conn.close()

    # Delete scan
    deleted = repo.delete_scan(scan_id)
    assert deleted is True
    assert repo.count_scans() == 0

    # Verify child tables are empty
    conn = get_connection(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM scan_datasets WHERE scan_id = ?;", (scan_id,))
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT count(*) FROM scoring_factors WHERE scan_id = ?;", (scan_id,))
    assert cursor.fetchone()[0] == 0
    conn.close()


# ---------------------------------------------------------------------------
# 6. Graceful Error Handling (Non-blocking)
# ---------------------------------------------------------------------------

def test_graceful_database_failure_handling():
    """Repository gracefully handles invalid/unwritable database paths."""
    invalid_path = Path("/non_existent_dir_12345/subdir/test.db")
    repo = ScanRepository(invalid_path)

    # Should not raise an unhandled exception
    scans = repo.list_scans()
    assert scans == []

    count = repo.count_scans()
    assert count == 0

    result = repo.get_scan_result(999)
    assert result is None


# ---------------------------------------------------------------------------
# 7. GUI Integration: HistorySection & Scan Loading
# ---------------------------------------------------------------------------

def test_gui_history_integration(qtbot, monkeypatch, temp_db_path):
    """Test that running analysis in MainWindow updates HistorySection and allows restoring results."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical",    lambda *a, **k: QMessageBox.Ok)

    window = MainWindow(db_path=temp_db_path)
    qtbot.addWidget(window)

    # Initially empty history
    assert not window.history_section._placeholder.isHidden()
    assert window.history_section._table.isHidden()

    # Run analysis
    df = load_csv(SAMPLES_DIR / "customers_faulty.csv")
    window.upload_section._add_dataset_entry("customers_faulty", df)

    cfg = build_analysis_config_from_v2(CONFIG_PATH)
    result = AnalysisService().run(window.current_datasets, cfg)
    window._on_analysis_finished(result)

    # History should now be populated in SQLite and UI
    assert window.history_section.repo.count_scans() == 1
    assert window.history_section._placeholder.isHidden()
    assert not window.history_section._table.isHidden()
    assert window.history_section._table.rowCount() == 1

    # Clear current view
    window._clear_results()
    assert window.score_section.isHidden()

    # Restore from history
    window.history_section._load_scan_by_id(1)
    assert not window.score_section.isHidden()
    assert window.current_result is not None
    assert window.current_result.primary_dataset().name == "customers_faulty"


def test_batch_and_gui_shared_database_history(qtbot, monkeypatch, temp_db_path):
    """Verify batch-generated scan is directly queryable and loadable in GUI history using the same database."""
    from batch_runner import run_batch
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--db", str(temp_db_path),
        "--no-reports",
    ])
    assert exit_code == 0

    window = MainWindow(db_path=temp_db_path)
    qtbot.addWidget(window)
    assert window.history_section.repo.count_scans() == 1
    scans = window.history_section.repo.list_scans()
    assert scans[0]["primary_dataset"] == "customers_clean_100pct"

    # Restore from history
    restored = window.history_section.repo.get_scan_result(scans[0]["id"])
    assert restored is not None
    assert restored.score.overall == 100.0
    assert len(restored.datasets) == 1
    assert restored.datasets[0].name == "customers_clean_100pct"
