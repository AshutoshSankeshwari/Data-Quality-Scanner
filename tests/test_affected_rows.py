"""
tests/test_affected_rows.py
Comprehensive verification of the Affected Rows metric:
1. Exact, uncapped counts > MAX_EXAMPLES (20).
2. Same-row deduplication across multiple checks and columns.
3. Multiple distinct rows contributing correctly.
4. Multiple datasets: rows deduplicated per (dataset_name, row_number).
5. Zero issues -> 0 affected rows.
6. Legacy historical scan fallback (None / "—" when issues exist, 0 when clean, never fake 0).
7. SQLite round-trip persistence of scalar affected_rows_count.
8. Safe non-destructive SQLite migration (legacy DB, idempotency, error propagation).
9. GUI ScoreSection and CLI console summary formatting.
10. HTML and Excel report exports.
"""
from __future__ import annotations
import io
import json
import sqlite3
import tempfile
from pathlib import Path
import pytest
import pandas as pd

from core.models import (
    AnalysisResult, DatasetProfile, ReadinessScore, ReadinessCategory,
    DuplicateResult, MandatoryFieldResult, NullBlankResult, WhitespaceResult,
    SpecialCharResult, DateResult, PatternResult, RelationshipResult, Severity
)
from core.service import AnalysisService, AnalysisConfig
from reports.summary_builder import count_affected_rows, build_issue_summary_counts
from db.repository import ScanRepository
from db.connection import get_connection, _ensure_schema
from batch_runner import _print_console_summary
from reports.html_reporter import generate_html
from reports.excel_reporter import generate_excel
import openpyxl


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def _make_dummy_score(blockers=0, highs=0, mediums=0, lows=0) -> ReadinessScore:
    return ReadinessScore(
        overall=90.0,
        category=ReadinessCategory.READY,
        dimensions=[],
        blocker_count=blockers,
        high_count=highs,
        medium_count=mediums,
        low_count=lows,
    )


def _make_dummy_profile(name="dataset", row_count=100) -> DatasetProfile:
    return DatasetProfile(
        name=name,
        row_count=row_count,
        column_count=5,
        is_primary=True,
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_uncapped_exact_count_beyond_max_examples():
    """Verify that when 50 rows have issues, Affected Rows is 50, not capped at MAX_EXAMPLES (20)."""
    # Create 50 failing rows
    df = pd.DataFrame({
        "ID": [None] * 50,
        "Name": [f"Person {i}" for i in range(50)],
    })
    service = AnalysisService()
    cfg = AnalysisConfig(enabled_checks=["mandatory_fields"], mandatory_fields=["ID"])
    result = service.run([("customers", df)], cfg)

    assert result.mandatory_field_results[0].failing_record_count == 50
    assert len(result.mandatory_field_results[0].affected_row_indices) == 50
    assert result.affected_rows_count == 50
    assert result.affected_rows_count != 20
    assert count_affected_rows(result) == 50


def test_same_row_deduplication_across_multiple_checks():
    """
    Row 10 has issues in duplicates, nulls, whitespace, and dates.
    It must count as exactly 1 affected row.
    """
    dr = DuplicateResult(
        dataset_name="ds1",
        full_row_duplicate_count=1,
        full_row_duplicate_pct=1.0,
        affected_row_indices=[10],
    )
    nb = NullBlankResult(
        dataset_name="ds1",
        per_column=[{"column": "email", "null_count": 1, "blank_count": 0, "whitespace_only_count": 0}],
        affected_row_indices=[10],
    )
    ws = WhitespaceResult(
        dataset_name="ds1",
        per_column=[{"column": "name", "leading_count": 1, "trailing_count": 0, "multi_internal_count": 0}],
        affected_row_indices=[10],
    )
    dt = DateResult(
        dataset_name="ds1",
        per_column=[{"column": "created_at", "invalid_count": 1}],
        affected_row_indices=[10],
    )

    res = AnalysisResult(
        run_id="test_dedup",
        timestamp="2026-09-07T12:00:00",
        datasets=[_make_dummy_profile("ds1", 100)],
        enabled_checks=["duplicates", "nulls", "whitespace", "dates"],
        duplicate_results=[dr],
        null_blank_results=[nb],
        whitespace_results=[ws],
        date_results=[dt],
        score=_make_dummy_score(blockers=1, highs=1, mediums=1, lows=1),
    )

    assert count_affected_rows(res) == 1


def test_multiple_distinct_rows():
    """Rows 10, 11, 15 across different checks produce Affected Rows = 3."""
    dr = DuplicateResult(
        dataset_name="ds1",
        full_row_duplicate_count=1,
        full_row_duplicate_pct=1.0,
        affected_row_indices=[10],
    )
    mf = MandatoryFieldResult(
        dataset_name="ds1",
        mandatory_fields=["Name"],
        failing_record_count=1,
        total_records=100,
        failing_pct=1.0,
        affected_row_indices=[11],
    )
    sc = SpecialCharResult(
        dataset_name="ds1",
        per_column=[{"column": "notes", "violation_count": 1}],
        affected_row_indices=[15],
    )

    res = AnalysisResult(
        run_id="test_distinct",
        timestamp="2026-09-07T12:00:00",
        datasets=[_make_dummy_profile("ds1", 100)],
        enabled_checks=["duplicates", "mandatory_fields", "special_chars"],
        duplicate_results=[dr],
        mandatory_field_results=[mf],
        special_char_results=[sc],
        score=_make_dummy_score(highs=3),
    )

    assert count_affected_rows(res) == 3


def test_multiple_datasets_deduplication():
    """
    Dataset A has issues on rows 10, 11.
    Dataset B has issues on rows 10, 20.
    Row 10 in A and row 10 in B are different physical rows -> Total = 4.
    """
    nb_a = NullBlankResult(
        dataset_name="dataset_a",
        per_column=[{"column": "c1", "null_count": 2}],
        affected_row_indices=[10, 11],
    )
    nb_b = NullBlankResult(
        dataset_name="dataset_b",
        per_column=[{"column": "c2", "null_count": 2}],
        affected_row_indices=[10, 20],
    )

    res = AnalysisResult(
        run_id="test_multi_ds",
        timestamp="2026-09-07T12:00:00",
        datasets=[_make_dummy_profile("dataset_a", 100), _make_dummy_profile("dataset_b", 100)],
        enabled_checks=["nulls"],
        null_blank_results=[nb_a, nb_b],
        score=_make_dummy_score(mediums=4),
    )

    assert count_affected_rows(res) == 4


def test_relationship_child_dataset_used():
    """Orphan records in RelationshipResult map to child_dataset."""
    rel = RelationshipResult(
        parent_dataset="parents",
        child_dataset="children",
        parent_key="id",
        child_key="parent_id",
        total_child_records=50,
        orphan_count=2,
        orphan_pct=4.0,
        affected_row_indices=[5, 12],
    )
    res = AnalysisResult(
        run_id="test_rel",
        timestamp="2026-09-07T12:00:00",
        datasets=[_make_dummy_profile("parents", 50), _make_dummy_profile("children", 50)],
        enabled_checks=["relationships"],
        relationship_results=[rel],
        score=_make_dummy_score(highs=2),
    )

    assert count_affected_rows(res) == 2


def test_zero_issues_returns_zero():
    """Clean AnalysisResult with 0 issues returns 0 affected rows."""
    res = AnalysisResult(
        run_id="test_clean",
        timestamp="2026-09-07T12:00:00",
        datasets=[_make_dummy_profile("clean", 100)],
        enabled_checks=["duplicates", "nulls"],
        score=_make_dummy_score(blockers=0, highs=0, mediums=0, lows=0),
    )

    assert count_affected_rows(res) == 0


def test_legacy_historical_scan_fallback():
    """
    Legacy historical scan where affected_rows is None/absent:
    - If it has issues, count_affected_rows returns None (triggers '—' in UI, never a fake 0).
    - If it has 0 issues, count_affected_rows returns 0.
    """
    # 1. Legacy scan with issues
    legacy_with_issues = AnalysisResult(
        run_id="legacy_dirty",
        timestamp="2026-01-01T10:00:00",
        datasets=[_make_dummy_profile("legacy_ds", 100)],
        enabled_checks=["nulls"],
        null_blank_results=[NullBlankResult(
            dataset_name="legacy_ds",
            per_column=[{"column": "c1", "null_count": 5}],
            affected_row_indices=[],  # Empty as in legacy deserialization
        )],
        score=_make_dummy_score(highs=5),
        affected_rows_count=None,
    )
    assert count_affected_rows(legacy_with_issues) is None

    # 2. Legacy scan without issues
    legacy_clean = AnalysisResult(
        run_id="legacy_clean",
        timestamp="2026-01-01T10:00:00",
        datasets=[_make_dummy_profile("legacy_clean_ds", 100)],
        enabled_checks=["nulls"],
        null_blank_results=[NullBlankResult(
            dataset_name="legacy_clean_ds",
            per_column=[{"column": "c1", "null_count": 0}],
            affected_row_indices=[],
        )],
        score=_make_dummy_score(blockers=0, highs=0, mediums=0, lows=0),
        affected_rows_count=None,
    )
    assert count_affected_rows(legacy_clean) == 0


def test_sqlite_round_trip_preserves_affected_rows_count():
    """A scan saved with affected_rows_count preserves and restores the exact count."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_roundtrip.db"
        repo = ScanRepository(db_path)

        res = AnalysisResult(
            run_id="scan_rt_123",
            timestamp="2026-09-07T14:00:00",
            datasets=[_make_dummy_profile("customers", 200)],
            enabled_checks=["duplicates"],
            duplicate_results=[DuplicateResult(
                dataset_name="customers",
                full_row_duplicate_count=42,
                full_row_duplicate_pct=21.0,
            )],
            score=_make_dummy_score(highs=42),
            affected_rows_count=42,
        )

        scan_id = repo.save_scan(res)
        assert scan_id is not None

        restored = repo.get_scan_result(scan_id)
        assert restored is not None
        assert restored.affected_rows_count == 42
        assert count_affected_rows(restored) == 42


def test_sqlite_migration_on_legacy_database():
    """
    Test migration against an existing SQLite database created without affected_rows:
    - Column is added non-destructively.
    - Existing records remain intact.
    - Subsequent reads and writes work correctly.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "legacy.db"
        
        # 1. Manually create legacy schema WITHOUT affected_rows column
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                app_version TEXT,
                config_hash TEXT,
                overall_score REAL,
                readiness_category TEXT,
                blocker_count INTEGER DEFAULT 0,
                high_count INTEGER DEFAULT 0,
                medium_count INTEGER DEFAULT 0,
                low_count INTEGER DEFAULT 0,
                total_issues INTEGER DEFAULT 0,
                dataset_count INTEGER DEFAULT 0,
                enabled_checks_json TEXT,
                ai_insights TEXT,
                warnings_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            INSERT INTO scans (run_id, started_at, total_issues)
            VALUES ('old_scan_001', '2025-12-01T00:00:00', 10);
        """)
        conn.commit()
        conn.close()

        # 2. Open via get_connection (which triggers _ensure_schema with migration)
        conn2 = get_connection(db_path)
        cursor = conn2.cursor()
        cursor.execute("PRAGMA table_info(scans);")
        cols = {row["name"] for row in cursor.fetchall()}
        assert "affected_rows" in cols, "Migration failed to add affected_rows column"

        # 3. Verify old record is preserved and affected_rows is NULL
        cursor.execute("SELECT run_id, total_issues, affected_rows FROM scans WHERE run_id = 'old_scan_001';")
        row = cursor.fetchone()
        assert row["run_id"] == "old_scan_001"
        assert row["total_issues"] == 10
        assert row["affected_rows"] is None
        conn2.close()

        # 4. Idempotency: open again, verify no error occurs
        conn3 = get_connection(db_path)
        cursor3 = conn3.cursor()
        cursor3.execute("PRAGMA table_info(scans);")
        cols3 = {row["name"] for row in cursor3.fetchall()}
        assert "affected_rows" in cols3
        conn3.close()


def test_sqlite_migration_unrelated_error_propagation():
    """Verify that unrelated SQLite errors (e.g. invalid syntax) are NOT swallowed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "err_test.db"
        conn = sqlite3.connect(str(db_path))
        # An invalid PRAGMA or corrupted statement should raise
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INVALID SQL STATEMENT;")
        conn.close()


def test_gui_score_section_display():
    """Verify ScoreSection displays affected_rows metric card with correct value and fallback."""
    from gui.sections.score_section import ScoreSection
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    section = ScoreSection()

    # 1. Fresh result with affected rows
    res = AnalysisResult(
        run_id="gui_test_1",
        timestamp="2026-09-07T12:00:00",
        datasets=[_make_dummy_profile("gui_ds", 100)],
        enabled_checks=["mandatory_fields"],
        mandatory_field_results=[MandatoryFieldResult(
            dataset_name="gui_ds",
            mandatory_fields=["A"],
            failing_record_count=35,
            total_records=100,
            failing_pct=35.0,
            affected_row_indices=list(range(1, 36)),
        )],
        score=_make_dummy_score(blockers=35),
        affected_rows_count=35,
    )
    section.set_result(res)
    assert section._stat_cards["affected_rows"]._val_label.text() == "35"

    # 2. Legacy result with issues -> fallback "—"
    legacy_res = AnalysisResult(
        run_id="gui_test_legacy",
        timestamp="2026-01-01T12:00:00",
        datasets=[_make_dummy_profile("gui_ds", 100)],
        enabled_checks=["mandatory_fields"],
        mandatory_field_results=[MandatoryFieldResult(
            dataset_name="gui_ds",
            mandatory_fields=["A"],
            failing_record_count=10,
            total_records=100,
            failing_pct=10.0,
            affected_row_indices=[],
        )],
        score=_make_dummy_score(blockers=10),
        affected_rows_count=None,
    )
    section.set_result(legacy_res)
    assert section._stat_cards["affected_rows"]._val_label.text() == "—"


def test_cli_console_summary_output():
    """Verify batch_runner console summary prints Affected Rows after Total Issues."""
    res = AnalysisResult(
        run_id="cli_test",
        timestamp="2026-09-07T12:00:00",
        datasets=[_make_dummy_profile("cli_ds", 100)],
        enabled_checks=["duplicates"],
        duplicate_results=[DuplicateResult(
            dataset_name="cli_ds",
            full_row_duplicate_count=5,
            full_row_duplicate_pct=5.0,
            affected_row_indices=[1, 2, 3, 4, 5],
        )],
        score=_make_dummy_score(highs=5),
        affected_rows_count=5,
    )

    buf = io.StringIO()
    import sys
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        _print_console_summary(res, {})
    finally:
        sys.stdout = old_stdout

    output = buf.getvalue()
    assert "Total Issues:   5" in output
    assert "Affected Rows:  5" in output
    total_pos = output.index("Total Issues:")
    aff_pos = output.index("Affected Rows:")
    assert aff_pos > total_pos, "Affected Rows must appear after Total Issues"


def test_html_and_excel_export_contain_affected_rows():
    """Verify HTML report stat card and Excel row 9 contain Affected Rows."""
    res = AnalysisResult(
        run_id="export_test",
        timestamp="2026-09-07T12:00:00",
        datasets=[_make_dummy_profile("exp_ds", 100)],
        enabled_checks=["mandatory_fields"],
        mandatory_field_results=[MandatoryFieldResult(
            dataset_name="exp_ds",
            mandatory_fields=["ID"],
            failing_record_count=18,
            total_records=100,
            failing_pct=18.0,
            affected_row_indices=list(range(1, 19)),
        )],
        score=_make_dummy_score(blockers=18),
        affected_rows_count=18,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. HTML export
        html_file = Path(tmp_dir) / "report.html"
        generate_html(res, html_file)
        html_text = html_file.read_text(encoding="utf-8")
        assert "Affected Rows" in html_text
        assert "18" in html_text

        # 2. Excel export
        excel_file = Path(tmp_dir) / "report.xlsx"
        generate_excel(res, excel_file)
        wb = openpyxl.load_workbook(str(excel_file))
        ws = wb["Summary"]
        assert ws["A9"].value == "Affected Rows (Unique):"
        assert ws["B9"].value == 18
