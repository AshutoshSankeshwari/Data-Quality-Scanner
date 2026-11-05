"""
tests/test_gui.py
PySide6 desktop GUI tests for the V2 single-page dashboard.

V2 architecture:
  - No sidebar / QStackedWidget
  - Single scrollable page with named section widgets
  - Config loaded from config/config.yaml (no interactive editor)
  - All result sections hidden until analysis completes
"""
import pytest
from pathlib import Path
import tempfile

from PySide6.QtWidgets import QApplication, QMessageBox, QLabel

from gui.main_window import MainWindow
from core.ingestion.loader import load_csv
from core.service import AnalysisService
from core.models import (
    AnalysisResult, DatasetProfile, Severity,
    DuplicateResult, MandatoryFieldResult, NullBlankResult,
    WhitespaceResult, SpecialCharResult, PatternResult, DateResult,
    RelationshipResult, get_dimension_for_category,
)
from rules.config_loader import build_analysis_config_from_v2

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
CONFIG_DIR  = Path(__file__).parent.parent / "config"
V2_CONFIG   = CONFIG_DIR / "config.yaml"


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_gui_main_window_instantiation(qtbot):
    """V2 window: single page with named section attributes, no sidebar/stack."""
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Data Quality Scanner"

    # All V2 section widgets must exist
    assert hasattr(window, "upload_section")
    assert hasattr(window, "dataset_info")
    assert hasattr(window, "run_section")
    assert hasattr(window, "score_section")
    assert hasattr(window, "dimensions_section")
    assert hasattr(window, "issues_section")
    assert hasattr(window, "relationships_section")
    assert hasattr(window, "recommendations_section")
    assert hasattr(window, "export_section")
    assert hasattr(window, "history_section")
    assert hasattr(window, "config_info")

    # Result sections start hidden
    for attr in (
        "score_section", "dimensions_section", "issues_section",
        "relationships_section", "recommendations_section", "export_section",
    ):
        assert getattr(window, attr).isHidden(), f"{attr} should start hidden"

    # Dataset info starts hidden (no datasets loaded yet)
    assert window.dataset_info.isHidden()

    # Run button disabled (no datasets)
    assert not window.run_section.btn_run.isEnabled()


# ---------------------------------------------------------------------------
# Theme / palette
# ---------------------------------------------------------------------------

def test_gui_theme_and_contrast(qtbot):
    from gui.style import setup_theme
    app = QApplication.instance()
    setup_theme(app)

    window = MainWindow()
    qtbot.addWidget(window)

    palette = app.palette()
    assert palette.color(palette.ColorRole.WindowText).name() == "#1e293b"
    assert palette.color(palette.ColorRole.Text).name() == "#1e293b"
    assert palette.color(palette.ColorRole.ButtonText).name() == "#1e293b"
    assert palette.color(palette.ColorRole.Window).name() == "#f8fafc"
    assert palette.color(palette.ColorRole.Base).name() == "#ffffff"


# ---------------------------------------------------------------------------
# Dataset upload
# ---------------------------------------------------------------------------

def test_gui_dataset_upload(qtbot):
    """Uploading a dataset shows it in the list, enables Run, shows dataset_info."""
    window = MainWindow()
    qtbot.addWidget(window)

    df = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    window.upload_section._add_dataset_entry("customers_clean_100pct", df)

    assert len(window.current_datasets) == 1
    assert window.upload_section.dataset_list.count() == 1
    assert window.run_section.btn_run.isEnabled()

    # Dataset info section becomes visible
    assert not window.dataset_info.isHidden()

    # Preview table populated (up to 10 rows)
    assert window.upload_section.preview_table.rowCount() == 10
    assert window.upload_section.preview_table.columnCount() == 7


# ---------------------------------------------------------------------------
# End-to-end single dataset: customers_faulty.csv
# ---------------------------------------------------------------------------

def test_gui_single_dataset_flow(qtbot, monkeypatch):
    """Full analysis: customers_faulty.csv — verify score, issues, recommendations."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical",    lambda *a, **k: QMessageBox.Ok)

    window = MainWindow()
    qtbot.addWidget(window)

    df = load_csv(SAMPLES_DIR / "customers_faulty.csv")
    window.upload_section._add_dataset_entry("customers_faulty", df)

    cfg = build_analysis_config_from_v2(V2_CONFIG)
    result = AnalysisService().run(window.current_datasets, cfg)
    window._on_analysis_finished(result)

    # Result sections visible
    for attr in (
        "score_section", "dimensions_section", "issues_section",
        "relationships_section", "recommendations_section", "export_section",
    ):
        assert not getattr(window, attr).isHidden(), f"{attr} should be visible after analysis"

    # Score section
    assert result.score is not None
    sc = window.score_section._stat_cards["score"]._val_label.text()
    assert sc != "—"

    # Dimensions section: 6 dimension cards
    assert window.dimensions_section._grid.count() == 6

    # Issues section: has issues
    assert len(window.issues_section._all_issues) > 0
    assert window.issues_section._table.rowCount() > 0

    # Recommendations section: has cards
    assert window.recommendations_section._b_layout.count() > 0

    # Dataset info: shows 1 dataset, status "Analysed ✓"
    assert window.dataset_info._dataset_rows[0]._status_lbl.text() == "Analysed ✓"


# ---------------------------------------------------------------------------
# End-to-end dual dataset: customers_clean_100pct + orders_related_to_customers
# ---------------------------------------------------------------------------

def test_gui_dual_dataset_relationship_flow(qtbot, monkeypatch):
    """Full analysis with two datasets — verify relationship integrity & discovery."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical",    lambda *a, **k: QMessageBox.Ok)

    window = MainWindow()
    qtbot.addWidget(window)

    df_cust = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    df_ord  = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")
    window.upload_section._add_dataset_entry("customers_clean_100pct", df_cust)
    window.upload_section._add_dataset_entry("orders_related_to_customers", df_ord)

    assert len(window.current_datasets) == 2

    cfg = build_analysis_config_from_v2(V2_CONFIG)
    result = AnalysisService().run(window.current_datasets, cfg)
    window._on_analysis_finished(result)

    # Relationship present and automatically validated
    assert len(result.relationship_results) == 1

    # Relationships section is visible
    assert not window.relationships_section.isHidden()

    rel = result.relationship_results[0]
    assert rel.parent_dataset == "customers_clean_100pct"
    assert rel.orphan_count == 20
    assert rel.origin == "configured"
    assert rel.origin_display == "Configured Rule"
    assert rel.status == "FAILED"

    # Dataset info: 2 datasets
    assert len(window.dataset_info._dataset_rows) == 2


# ---------------------------------------------------------------------------
# Clear results
# ---------------------------------------------------------------------------

def test_gui_clear_results(qtbot, monkeypatch):
    """Clearing results hides result sections and resets state."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)

    window = MainWindow()
    qtbot.addWidget(window)

    df = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    window.upload_section._add_dataset_entry("customers_clean_100pct", df)

    cfg = build_analysis_config_from_v2(V2_CONFIG)
    result = AnalysisService().run(window.current_datasets, cfg)
    window._on_analysis_finished(result)

    # Confirm visible
    assert not window.score_section.isHidden()

    # Clear
    window._clear_results()

    assert window.current_result is None
    for attr in ("score_section", "dimensions_section", "issues_section",
                 "relationships_section", "recommendations_section", "export_section"):
        assert getattr(window, attr).isHidden(), f"{attr} should be hidden after clear"


# ---------------------------------------------------------------------------
# Export reports
# ---------------------------------------------------------------------------

def test_gui_export_reports(qtbot, monkeypatch):
    """Export section generates HTML, Excel, and JSON reports."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical",    lambda *a, **k: QMessageBox.Ok)

    window = MainWindow()
    qtbot.addWidget(window)

    df = load_csv(SAMPLES_DIR / "customers_faulty.csv")
    window.upload_section._add_dataset_entry("customers_faulty", df)

    cfg = build_analysis_config_from_v2(V2_CONFIG)
    result = AnalysisService().run(window.current_datasets, cfg)
    window._on_analysis_finished(result)

    with tempfile.TemporaryDirectory() as tmp:
        window.export_section._output_dir = tmp
        window.export_section._generate_reports()
        assert window.export_section._file_list.count() == 3
        assert (Path(tmp) / "customers_faulty_data_quality_report.html").exists()
        assert (Path(tmp) / "customers_faulty_data_quality_report.xlsx").exists()
        assert (Path(tmp) / "customers_faulty_data_quality_report.json").exists()


# ---------------------------------------------------------------------------
# History and config info sections always visible
# ---------------------------------------------------------------------------

def test_gui_history_and_config_info_visible(qtbot):
    """Scan history placeholder and config info section are always shown."""
    window = MainWindow()
    qtbot.addWidget(window)

    # These are always visible (not hidden by default)
    assert not window.history_section.isHidden()
    assert not window.config_info.isHidden()


def test_gui_ui_text_cleanup(qtbot, monkeypatch):
    """Verify UI text cleanup: subtitle & category badge removed, dimension descriptions visible, no weight text."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical",    lambda *a, **k: QMessageBox.Ok)

    window = MainWindow()
    qtbot.addWidget(window)

    df = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    window.upload_section._add_dataset_entry("customers_clean_100pct", df)

    cfg = build_analysis_config_from_v2(V2_CONFIG)
    result = AnalysisService().run(window.current_datasets, cfg)
    window._on_analysis_finished(result)

    # 1. Overall score section checks
    score_sec = window.score_section
    # No category badge attribute exists
    assert not hasattr(score_sec, "_category_badge")
    assert not hasattr(score_sec, "_readiness_subtitle")

    # Score and KPI items exist and are populated
    assert score_sec._stat_cards["score"]._val_label.text() == "100.0"
    assert score_sec._stat_cards["critical"]._val_label.text() == "0"
    assert score_sec._stat_cards["high"]._val_label.text() == "0"
    assert score_sec._stat_cards["total"]._val_label.text() == "0"
    assert score_sec._stat_cards["datasets"]._val_label.text() == "1"

    # 2. Quality Dimension Cards checks
    dim_sec = window.dimensions_section
    assert dim_sec._grid.count() == 6

    # Verify all 6 cards contain descriptions and no weight text
    for i in range(dim_sec._grid.count()):
        item_w = dim_sec._grid.itemAt(i).widget()
        assert item_w is not None
        # Find all QLabels in the card
        labels = item_w.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        full_text = " ".join(texts)

        # Weight text must not be present
        assert "Weight" not in full_text
        assert "%" not in full_text or " / 100" in full_text  # only score / 100

        # Meaningful description must be present
        desc_lbl = labels[-1]  # Bottom row description
        assert desc_lbl.text() != ""
        assert "Measures" in desc_lbl.text()


def test_gui_issues_section_includes_patterns(qtbot):
    """Verify Pattern inconsistencies appear in the GUI Issues section with Low severity."""
    from core.models import AnalysisResult, PatternResult, DatasetProfile, Severity
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="test_ds", row_count=100, column_count=1, columns=[], is_primary=True)
    pat_res = PatternResult(
        dataset_name="test_ds",
        per_column=[{
            "column": "Product_Code",
            "dominant_pattern": "AAA-999",
            "has_case_inconsistency": True,
            "has_structural_inconsistency": False,
            "sample_inconsistencies": [{"row_number": 2, "value": "abc-002", "pattern": "aaa-999", "dominant_pattern": "AAA-999"}],
            "severity": "Low",
        }],
        severity=Severity.LOW,
    )
    res = AnalysisResult(
        run_id="test",
        timestamp="2026-08-26T10:00:00",
        enabled_checks=["patterns"],
        datasets=[ds],
        pattern_results=[pat_res],
    )

    window.issues_section.set_result(res)
    assert len(window.issues_section._all_issues) == 1
    iss = window.issues_section._all_issues[0]
    assert iss["category"] == "Patterns"
    assert iss["dimension"] == "Consistency"
    assert iss["severity"] == "Low"
    assert iss["dataset"] == "test_ds"
    assert iss["column"] == "Product_Code"
    assert "1 pattern inconsistencies" in iss["details"]
    assert window.issues_section._table.rowCount() == 1
    # Verify table column 4 is Quality Dimension
    assert window.issues_section._table.item(0, 4).text() == "Consistency"


# ---------------------------------------------------------------------------
# Quality Dimension Column & Filter Tests
# ---------------------------------------------------------------------------

def test_issues_section_has_quality_dimension_column(qtbot):
    """Verify Quality Dimension column is present in the table headers at column index 4."""
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="ds1", row_count=50, column_count=1, columns=[], is_primary=True)
    res = AnalysisResult(
        run_id="r1",
        timestamp="2026-09-01T12:00:00",
        enabled_checks=["whitespace"],
        datasets=[ds],
        whitespace_results=[WhitespaceResult(
            dataset_name="ds1",
            per_column=[{"column": "Name", "leading_count": 2, "trailing_count": 0, "multi_internal_count": 0, "severity": "Low"}],
            severity=Severity.LOW,
        )],
    )
    window.issues_section.set_result(res)

    headers = [
        window.issues_section._table.horizontalHeaderItem(i).text()
        for i in range(window.issues_section._table.columnCount())
    ]
    expected_headers = ["Severity", "Category", "Dataset", "Affected Field(s)", "Quality Dimension", "Issue Description"]
    assert headers == expected_headers
    assert headers[4] == "Quality Dimension"


def test_issues_section_dimension_values_correct(qtbot):
    """
    Dual-verification test:
    Verify for all issue types that BOTH:
      A. Internal issue data (iss['dimension'])
      B. Rendered GUI table cell (item at col 4)
    display the expected Quality Dimension.
    """
    from core.models import (
        DuplicateResult, MandatoryFieldResult, NullBlankResult,
        WhitespaceResult, SpecialCharResult, PatternResult, DateResult,
        RelationshipResult,
    )
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="ds1", row_count=100, column_count=8, columns=[], is_primary=True)
    res = AnalysisResult(
        run_id="r_all",
        timestamp="2026-09-01T12:00:00",
        enabled_checks=["all"],
        datasets=[ds],
        duplicate_results=[
            DuplicateResult(dataset_name="ds1", full_row_duplicate_count=5, full_row_duplicate_pct=5.0, severity=Severity.MEDIUM)
        ],
        mandatory_field_results=[
            MandatoryFieldResult(dataset_name="ds1", mandatory_fields=["ReqField"], failing_record_count=3, total_records=100, failing_pct=3.0, per_field=[{"field": "ReqField", "missing_count": 3}], severity=Severity.HIGH)
        ],
        null_blank_results=[
            NullBlankResult(dataset_name="ds1", per_column=[{"column": "OptField", "null_count": 4, "null_pct": 4.0, "blank_count": 0, "whitespace_only_count": 0, "severity": "Low"}])
        ],
        whitespace_results=[
            WhitespaceResult(dataset_name="ds1", per_column=[{"column": "TextField", "leading_count": 2, "trailing_count": 1, "multi_internal_count": 0, "severity": "Low"}], severity=Severity.LOW)
        ],
        special_char_results=[
            SpecialCharResult(dataset_name="ds1", per_column=[{"column": "CodeField", "rule_name": "alphanumeric", "violation_count": 1, "violation_pct": 1.0, "severity": "Medium"}])
        ],
        date_results=[
            DateResult(dataset_name="ds1", per_column=[{"column": "DateField", "invalid_count": 2, "invalid_pct": 2.0, "severity": "High"}])
        ],
        pattern_results=[
            PatternResult(dataset_name="ds1", per_column=[{"column": "PatField", "dominant_pattern": "AA-99", "has_case_inconsistency": True, "has_structural_inconsistency": False, "sample_inconsistencies": [{"row_number": 1, "value": "aa-01"}], "severity": "Low"}], severity=Severity.LOW)
        ],
        relationship_results=[
            RelationshipResult(parent_dataset="parent", child_dataset="ds1", parent_key="id", child_key="p_id", total_child_records=100, orphan_count=2, orphan_pct=2.0, severity=Severity.HIGH)
        ],
    )

    window.issues_section.set_result(res)

    expected_category_dimension = {
        "Duplicates": "Uniqueness",
        "Mandatory Fields": "Completeness",
        "Nulls/Blanks": "Completeness",
        "Whitespace": "Cleanliness",
        "Special Characters": "Validity",
        "Dates": "Validity",
        "Patterns": "Consistency",
        "Relationships": "Integrity",
    }

    # A. Check internal issue list
    for iss in window.issues_section._all_issues:
        cat = iss["category"]
        expected_dim = expected_category_dimension[cat]
        assert iss["dimension"] == expected_dim, f"Internal dimension mismatch for category '{cat}': expected '{expected_dim}', got '{iss['dimension']}'"

    # B. Check rendered table cells
    assert window.issues_section._table.rowCount() == len(window.issues_section._all_issues)
    for r in range(window.issues_section._table.rowCount()):
        cat_item = window.issues_section._table.item(r, 1).text()
        dim_item = window.issues_section._table.item(r, 4).text()
        expected_dim = expected_category_dimension[cat_item]
        assert dim_item == expected_dim, f"Rendered table cell mismatch at row {r} for category '{cat_item}': expected '{expected_dim}', got '{dim_item}'"


def test_issues_section_unknown_category_not_defaulted_to_validity(qtbot):
    """
    Verify an unmapped/unknown category is explicitly handled as 'Unclassified'
    and is NEVER silently assigned the 'Validity' dimension.
    """
    from core.models import get_dimension_for_category
    assert get_dimension_for_category("CompletelyUnknownCategory123") == "Unclassified"
    assert get_dimension_for_category("CompletelyUnknownCategory123") != "Validity"

    window = MainWindow()
    qtbot.addWidget(window)

    # Inject an unmapped category into _all_issues to test table rendering and filtering
    unmapped_dim = get_dimension_for_category("CompletelyUnknownCategory123")
    window.issues_section._all_issues = [{
        "category": "CompletelyUnknownCategory123",
        "dimension": unmapped_dim,
        "severity": "Low",
        "dataset": "ds1",
        "column": "colX",
        "details": "some unclassified issue",
    }]
    window.issues_section._apply_filters()

    assert window.issues_section._table.rowCount() == 1
    dim_rendered = window.issues_section._table.item(0, 4).text()
    assert dim_rendered == "Unclassified"
    assert dim_rendered != "Validity"


def test_issues_section_dimension_dropdown_options(qtbot):
    """Verify Quality Dimension dropdown contains All Dimensions and the 6 standard dimensions."""
    window = MainWindow()
    qtbot.addWidget(window)

    items = [
        window.issues_section._dim_filter.itemText(i)
        for i in range(window.issues_section._dim_filter.count())
    ]
    expected = [
        "All Dimensions", "Completeness", "Uniqueness",
        "Validity", "Consistency", "Integrity", "Cleanliness",
    ]
    assert items == expected


def test_issues_section_dimension_filter_uniqueness(qtbot):
    """Verify selecting Dimension = 'Uniqueness' displays only duplicate issues."""
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="ds1", row_count=100, column_count=2, columns=[], is_primary=True)
    res = AnalysisResult(
        run_id="r_filt",
        timestamp="2026-09-01T12:00:00",
        enabled_checks=["duplicates", "whitespace"],
        datasets=[ds],
        duplicate_results=[
            DuplicateResult(dataset_name="ds1", full_row_duplicate_count=3, full_row_duplicate_pct=3.0, severity=Severity.MEDIUM)
        ],
        whitespace_results=[
            WhitespaceResult(dataset_name="ds1", per_column=[{"column": "Name", "leading_count": 2, "trailing_count": 0, "multi_internal_count": 0, "severity": "Low"}], severity=Severity.LOW)
        ],
    )
    window.issues_section.set_result(res)
    assert window.issues_section._table.rowCount() == 2

    # Filter to Uniqueness
    window.issues_section._dim_filter.setCurrentText("Uniqueness")
    assert window.issues_section._table.rowCount() == 1
    assert window.issues_section._table.item(0, 1).text() == "Duplicates"
    assert window.issues_section._table.item(0, 4).text() == "Uniqueness"
    assert "1 issue(s) found" in window.issues_section._count_lbl.text()


def test_issues_section_dimension_filter_completeness(qtbot):
    """Verify selecting Dimension = 'Completeness' displays only Nulls and Mandatory issues."""
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="ds1", row_count=100, column_count=2, columns=[], is_primary=True)
    res = AnalysisResult(
        run_id="r_comp",
        timestamp="2026-09-01T12:00:00",
        enabled_checks=["nulls", "mandatory_fields", "dates"],
        datasets=[ds],
        mandatory_field_results=[
            MandatoryFieldResult(dataset_name="ds1", mandatory_fields=["ColA"], failing_record_count=2, total_records=100, failing_pct=2.0, per_field=[{"field": "ColA", "missing_count": 2}], severity=Severity.HIGH)
        ],
        null_blank_results=[
            NullBlankResult(dataset_name="ds1", per_column=[{"column": "ColB", "null_count": 5, "null_pct": 5.0, "blank_count": 0, "whitespace_only_count": 0, "severity": "Low"}])
        ],
        date_results=[
            DateResult(dataset_name="ds1", per_column=[{"column": "ColDate", "invalid_count": 1, "invalid_pct": 1.0, "severity": "High"}])
        ],
    )
    window.issues_section.set_result(res)
    assert window.issues_section._table.rowCount() == 3

    window.issues_section._dim_filter.setCurrentText("Completeness")
    assert window.issues_section._table.rowCount() == 2
    for r in range(2):
        assert window.issues_section._table.item(r, 4).text() == "Completeness"
    assert "2 issue(s) found" in window.issues_section._count_lbl.text()


def test_issues_section_dimension_filter_empty_result(qtbot):
    """Verify filtering to a dimension with 0 matching issues shows 0 found without error."""
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="ds1", row_count=100, column_count=1, columns=[], is_primary=True)
    res = AnalysisResult(
        run_id="r_empty",
        timestamp="2026-09-01T12:00:00",
        enabled_checks=["whitespace"],
        datasets=[ds],
        whitespace_results=[
            WhitespaceResult(dataset_name="ds1", per_column=[{"column": "Name", "leading_count": 2, "trailing_count": 0, "multi_internal_count": 0, "severity": "Low"}], severity=Severity.LOW)
        ],
    )
    window.issues_section.set_result(res)

    window.issues_section._dim_filter.setCurrentText("Integrity")
    assert window.issues_section._table.rowCount() == 0
    assert window.issues_section._count_lbl.text() == "0 issue(s) found"


def test_issues_section_combined_filtering(qtbot):
    """Verify simultaneous Severity + Category + Dimension + Search filtering."""
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="ds1", row_count=100, column_count=4, columns=[], is_primary=True)
    res = AnalysisResult(
        run_id="r_comb",
        timestamp="2026-09-01T12:00:00",
        enabled_checks=["nulls", "mandatory", "dates", "duplicates"],
        datasets=[ds],
        mandatory_field_results=[
            MandatoryFieldResult(dataset_name="ds1", mandatory_fields=["TargetCol"], failing_record_count=2, total_records=100, failing_pct=2.0, per_field=[{"field": "TargetCol", "missing_count": 2}], severity=Severity.HIGH)
        ],
        null_blank_results=[
            NullBlankResult(dataset_name="ds1", per_column=[{"column": "OtherCol", "null_count": 5, "null_pct": 5.0, "blank_count": 0, "whitespace_only_count": 0, "severity": "Low"}])
        ],
        date_results=[
            DateResult(dataset_name="ds1", per_column=[{"column": "DateCol", "invalid_count": 1, "invalid_pct": 1.0, "severity": "High"}])
        ],
    )
    window.issues_section.set_result(res)
    assert window.issues_section._table.rowCount() == 3

    # Apply combined filters: Severity=High, Category=Mandatory Fields, Dimension=Completeness, Search=TargetCol
    window.issues_section._sev_filter.setCurrentText("High")
    window.issues_section._cat_filter.setCurrentText("Mandatory Fields")
    window.issues_section._dim_filter.setCurrentText("Completeness")
    window.issues_section._search.setText("TargetCol")

    assert window.issues_section._table.rowCount() == 1
    assert window.issues_section._table.item(0, 0).text() == "High"
    assert window.issues_section._table.item(0, 1).text() == "Mandatory Fields"
    assert window.issues_section._table.item(0, 3).text() == "TargetCol"
    assert window.issues_section._table.item(0, 4).text() == "Completeness"


def test_issues_section_search_matches_dimension(qtbot):
    """Verify search input matches Quality Dimension name (case-insensitive)."""
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="ds1", row_count=100, column_count=3, columns=[], is_primary=True)
    res = AnalysisResult(
        run_id="r_search",
        timestamp="2026-09-01T12:00:00",
        enabled_checks=["whitespace", "dates"],
        datasets=[ds],
        whitespace_results=[
            WhitespaceResult(dataset_name="ds1", per_column=[{"column": "Name", "leading_count": 2, "trailing_count": 0, "multi_internal_count": 0, "severity": "Low"}], severity=Severity.LOW)
        ],
        date_results=[
            DateResult(dataset_name="ds1", per_column=[{"column": "DueDate", "invalid_count": 1, "invalid_pct": 1.0, "severity": "High"}])
        ],
    )
    window.issues_section.set_result(res)
    assert window.issues_section._table.rowCount() == 2

    # Search for "cleanliness"
    window.issues_section._search.setText("cleanliness")
    assert window.issues_section._table.rowCount() == 1
    assert window.issues_section._table.item(0, 4).text() == "Cleanliness"

    # Search for "validity"
    window.issues_section._search.setText("validity")
    assert window.issues_section._table.rowCount() == 1
    assert window.issues_section._table.item(0, 4).text() == "Validity"


def test_issues_section_all_dimensions_resets_view(qtbot):
    """Verify selecting 'All Dimensions' restores all issues in the view."""
    window = MainWindow()
    qtbot.addWidget(window)

    ds = DatasetProfile(name="ds1", row_count=100, column_count=2, columns=[], is_primary=True)
    res = AnalysisResult(
        run_id="r_reset",
        timestamp="2026-09-01T12:00:00",
        enabled_checks=["whitespace", "duplicates"],
        datasets=[ds],
        whitespace_results=[
            WhitespaceResult(dataset_name="ds1", per_column=[{"column": "Name", "leading_count": 2, "trailing_count": 0, "multi_internal_count": 0, "severity": "Low"}], severity=Severity.LOW)
        ],
        duplicate_results=[
            DuplicateResult(dataset_name="ds1", full_row_duplicate_count=1, full_row_duplicate_pct=1.0, severity=Severity.LOW)
        ],
    )
    window.issues_section.set_result(res)
    assert window.issues_section._table.rowCount() == 2

    window.issues_section._dim_filter.setCurrentText("Cleanliness")
    assert window.issues_section._table.rowCount() == 1

    window.issues_section._dim_filter.setCurrentText("All Dimensions")
    assert window.issues_section._table.rowCount() == 2



