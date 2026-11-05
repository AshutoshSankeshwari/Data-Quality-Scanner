"""
tests/test_timestamp_formatting.py
Unit and integration tests for human-readable timestamp display formatting across:
  1. Core format_display_timestamp utility and AnalysisResult.display_timestamp property.
  2. GUI Scan History table display.
  3. GUI RunSection analysis completion / scan time display.
  4. Generated HTML report metadata timestamp.
  5. Generated Excel report Summary and Dataset Details sheets.
  6. Machine-readable JSON preservation (protected).
"""
import tempfile
from pathlib import Path
from datetime import datetime
import json
import openpyxl
import pytest

from core.models import (
    format_display_timestamp, AnalysisResult, DatasetProfile,
    Severity, ReadinessCategory, ReadinessScore, DimensionScore,
)
from gui.sections.history_section import HistorySection
from gui.sections.run_section import RunSection
from reports.html_reporter import generate_html
from reports.excel_reporter import generate_excel
from reports.json_reporter import generate_json


# ---------------------------------------------------------------------------
# 1. Core Formatter Unit Tests
# ---------------------------------------------------------------------------

def test_format_display_timestamp_iso_strings():
    """Verify standard ISO string formats produce 'DD MMM YYYY, hh:mm AM/PM'."""
    assert format_display_timestamp("2026-09-07T16:40:28") == "07 Sep 2026, 04:40 PM"
    assert format_display_timestamp("2026-09-07T09:05:00") == "07 Sep 2026, 09:05 AM"
    assert format_display_timestamp("2026-09-07T00:00:00") == "07 Sep 2026, 12:00 AM"
    assert format_display_timestamp("2026-09-07T12:00:00") == "07 Sep 2026, 12:00 PM"


def test_format_display_timestamp_with_microseconds_and_z():
    """Verify ISO strings with fractional seconds and 'Z' suffix are handled properly."""
    assert format_display_timestamp("2026-09-07T16:40:28.123456") == "07 Sep 2026, 04:40 PM"
    assert format_display_timestamp("2026-09-07T16:40:28Z") == "07 Sep 2026, 04:40 PM"
    assert format_display_timestamp("2026-09-07T16:40:28+00:00") == "07 Sep 2026, 04:40 PM"


def test_format_display_timestamp_datetime_objects():
    """Verify datetime objects format directly."""
    dt = datetime(2026, 9, 7, 16, 40, 28)
    assert format_display_timestamp(dt) == "07 Sep 2026, 04:40 PM"

    dt_morning = datetime(2026, 1, 5, 8, 30, 0)
    assert format_display_timestamp(dt_morning) == "05 Jan 2026, 08:30 AM"


def test_format_display_timestamp_empty_and_edge_cases():
    """Verify graceful handling of None, empty, whitespace, and fallback values."""
    assert format_display_timestamp(None) == "—"
    assert format_display_timestamp("") == "—"
    assert format_display_timestamp("   ") == "—"
    assert format_display_timestamp("—") == "—"
    assert format_display_timestamp("None") == "—"
    assert format_display_timestamp("null") == "—"

    # Space-separated date time
    assert format_display_timestamp("2026-09-07 16:40:28") == "07 Sep 2026, 04:40 PM"
    # Unparseable string returns original string
    assert format_display_timestamp("NotADateString") == "NotADateString"


def test_analysis_result_display_timestamp_property():
    """Verify AnalysisResult exposes display_timestamp property with correct formatting."""
    res = AnalysisResult(
        run_id="run123",
        timestamp="2026-09-07T16:40:28",
        datasets=[],
        enabled_checks=[],
    )
    assert res.display_timestamp == "07 Sep 2026, 04:40 PM"


# ---------------------------------------------------------------------------
# 2. GUI Tests (Scan History & RunSection Completion)
# ---------------------------------------------------------------------------

def test_gui_history_section_timestamp_formatting(qtbot, tmp_path):
    """Verify Scan History table renders timestamps formatted as DD MMM YYYY, hh:mm AM/PM."""
    history = HistorySection(db_path=tmp_path / "test.db")
    qtbot.addWidget(history)

    # Mock list_scans to return test scans
    history.repo.list_scans = lambda limit=30: [
        {
            "id": 1,
            "started_at": "2026-09-07T16:40:28",
            "primary_dataset": "ds_test",
            "dataset_count": 1,
            "overall_score": 95.0,
            "readiness_category": "READY",
            "total_issues": 0,
        },
        {
            "id": 2,
            "started_at": "2026-08-26T10:00:00",
            "primary_dataset": "ds_test2",
            "dataset_count": 1,
            "overall_score": 80.0,
            "readiness_category": "READY WITH MINOR CLEANSING",
            "total_issues": 5,
        },
    ]
    history.refresh_history()

    # Column 0 is Scan Date & Time
    assert history._table.item(0, 0).text() == "07 Sep 2026, 04:40 PM"
    assert history._table.item(1, 0).text() == "26 Aug 2026, 10:00 AM"


def test_gui_run_section_completion_timestamp(qtbot):
    """Verify RunSection status label displays human-readable completion timestamp."""
    run_sec = RunSection()
    qtbot.addWidget(run_sec)
    run_sec.show()

    # When analysis completes
    run_sec.set_running(False, timestamp="2026-09-07T16:40:28")
    assert not run_sec.status_lbl.isHidden()
    assert run_sec.status_lbl.text() == "Analysis completed: 07 Sep 2026, 04:40 PM"

    # When historical scan is loaded
    run_sec.set_completed(timestamp="2026-08-26T10:00:00")
    assert not run_sec.status_lbl.isHidden()
    assert run_sec.status_lbl.text() == "Analysis completed: 26 Aug 2026, 10:00 AM"


# ---------------------------------------------------------------------------
# 3. Report Output Tests (HTML, Excel, JSON)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_result():
    ds = DatasetProfile(
        name="test_data",
        row_count=100,
        column_count=5,
        columns=[],
        is_primary=True,
        file_type="CSV",
        file_path="test_data.csv",
        overall_null_pct=0.5,
        duplicate_row_count=0,
        duplicate_row_pct=0.0,
    )
    score = ReadinessScore(
        overall=92.0,
        category=ReadinessCategory.READY,
        dimensions=[
            DimensionScore(
                name="Completeness",
                score=95.0,
                weight=0.25,
                weighted=23.75,
                explanation="High completeness",
            ),
        ],
        blocker_count=0,
        high_count=0,
        medium_count=1,
        low_count=0,
    )
    return AnalysisResult(
        run_id="run-test-01",
        timestamp="2026-09-07T16:40:28",
        datasets=[ds],
        enabled_checks=["duplicates", "null_blanks"],
        score=score,
    )


def test_html_report_timestamp_formatting(sample_result, tmp_path):
    """Verify HTML report renders human-readable timestamp in metadata card."""
    out_html = tmp_path / "report.html"
    generate_html(sample_result, out_html)
    assert out_html.exists()

    content = out_html.read_text(encoding="utf-8")
    # Human-readable timestamp must be present
    assert "07 Sep 2026, 04:40 PM" in content
    # Metadata item should have formatted timestamp
    assert '<span class="meta-value">07 Sep 2026, 04:40 PM</span>' in content


def test_excel_report_timestamp_formatting(sample_result, tmp_path):
    """Verify Excel report renders formatted timestamp in Summary and Dataset Details sheets."""
    out_xlsx = tmp_path / "report.xlsx"
    generate_excel(sample_result, out_xlsx)
    assert out_xlsx.exists()

    wb = openpyxl.load_workbook(out_xlsx)

    # 1. Summary sheet cell B4
    ws_summary = wb["Summary"]
    assert ws_summary["A4"].value == "Analysis Timestamp:"
    assert ws_summary["B4"].value == "07 Sep 2026, 04:40 PM"

    # 2. Dataset Details sheet column 10 (row 2)
    ws_ds = wb["Dataset Details"]
    assert ws_ds.cell(row=1, column=10).value == "Timestamp"
    assert ws_ds.cell(row=2, column=10).value == "07 Sep 2026, 04:40 PM"


def test_json_report_timestamp_machine_readable_preservation(sample_result, tmp_path):
    """Verify machine-readable ISO timestamp remains strictly preserved in exported JSON."""
    out_json = tmp_path / "report.json"
    generate_json(sample_result, out_json)
    assert out_json.exists()

    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Machine-readable ISO timestamp must remain unchanged
    assert data["timestamp"] == "2026-09-07T16:40:28"
