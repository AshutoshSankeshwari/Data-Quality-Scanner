"""
tests/test_reports.py
Unit and integration tests for actionable Data Quality Assessment reports (HTML, Excel, JSON).
Verifies:
  1. Dataset Details, Performance & Readiness score, Issue summary counts.
  2. Detailed issue information with row references and problematic values.
  3. 7-sheet Excel workbook generation with top issues visibly listed in Summary worksheet and Auto-Discovered Relationships in Relationships sheet.
  4. Machine-readable JSON output with summary_counts, detailed_issues, and discovered_relationships.
  5. Historical report generation from SQLite-restored scans without raw files.
"""
import pytest
import tempfile
from pathlib import Path
import json
import openpyxl

from core.service import AnalysisService
from core.ingestion.loader import load_csv
from rules.config_loader import build_analysis_config_from_v2
from db.repository import ScanRepository
from reports.html_reporter import generate_html
from reports.excel_reporter import generate_excel
from reports.json_reporter import generate_json
from reports.summary_builder import build_issue_summary_counts, extract_detailed_issues
from reports import get_report_filename

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


@pytest.fixture
def live_faulty_analysis_result():
    """Live analysis result with faulty dataset having multiple quality issues."""
    df_faulty = load_csv(SAMPLES_DIR / "customers_faulty.csv")
    service = AnalysisService()
    cfg = build_analysis_config_from_v2(CONFIG_PATH)
    return service.run([("customers_faulty", df_faulty)], cfg)


@pytest.fixture
def live_dual_analysis_result():
    """Live analysis result with two datasets, relationship check, and discovery."""
    df_clean = load_csv(SAMPLES_DIR / "customers_clean_100pct.csv")
    df_orders = load_csv(SAMPLES_DIR / "orders_related_to_customers.csv")
    service = AnalysisService()
    cfg = build_analysis_config_from_v2(CONFIG_PATH)
    return service.run([("customers_clean_100pct", df_clean), ("orders_related_to_customers", df_orders)], cfg)


@pytest.fixture
def restored_analysis_result(live_dual_analysis_result):
    """AnalysisResult saved to SQLite and reconstructed without original data files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_reports.db"
        repo = ScanRepository(db_path)
        scan_id = repo.save_scan(live_dual_analysis_result, config_hash="test_v2_hash")
        assert scan_id is not None
        restored = repo.get_scan_result(scan_id)
        assert restored is not None
        return restored


# ---------------------------------------------------------------------------
# 1. Summary Builder Tests
# ---------------------------------------------------------------------------

def test_summary_builder_counts(live_faulty_analysis_result, live_dual_analysis_result):
    faulty_counts = build_issue_summary_counts(live_faulty_analysis_result)
    assert faulty_counts["total_problems"] > 0
    assert faulty_counts["duplicates"] > 0
    assert faulty_counts["nulls_and_blanks"] > 0
    assert faulty_counts["special_chars"] > 0

    dual_counts = build_issue_summary_counts(live_dual_analysis_result)
    assert dual_counts["relationships"] == 20  # 20 orphan records in orders


def test_detailed_issue_extractor(live_faulty_analysis_result, live_dual_analysis_result):
    faulty_issues = extract_detailed_issues(live_faulty_analysis_result)
    assert len(faulty_issues) > 0
    
    # Check that row numbers are preserved
    has_row_numbers = any(len(iss.get("sample_rows", [])) > 0 for iss in faulty_issues)
    assert has_row_numbers is True

    dual_issues = extract_detailed_issues(live_dual_analysis_result)
    rel_issues = [i for i in dual_issues if i["category"] == "Relationship Integrity"]
    assert len(rel_issues) == 1
    assert rel_issues[0]["affected_count"] == 20
    assert len(rel_issues[0]["sample_rows"]) > 0


# ---------------------------------------------------------------------------
# 2. Live AnalysisResult Reports (HTML, Excel, JSON)
# ---------------------------------------------------------------------------

def test_generate_html_report_live(live_dual_analysis_result):
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = generate_html(live_dual_analysis_result, Path(tmp_dir) / "report.html")
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        
        # 1. Dataset Details
        assert "1. Dataset Details" in content
        assert "customers_clean_100pct" in content
        assert "orders_related_to_customers" in content
        assert live_dual_analysis_result.run_id in content
        
        # 2. Dataset Performance / Readiness
        assert "2. Dataset Performance & Readiness" in content
        for dim in live_dual_analysis_result.score.dimensions:
            assert dim.name in content
            
        # 3. Quality Issue Summary
        assert "3. Quality Issue Summary" in content
        assert "Total Problems Detected" in content
        
        # 4. Detailed Issue Information
        assert "4. Detailed Issue Information" in content
        
        # 5. Relationship Integrity & Detection
        assert "5. Relationship Integrity & Detection" in content
        assert "orders_related_to_customers" in content and "customers_clean_100pct" in content


def test_generate_excel_report_live(live_dual_analysis_result):
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = generate_excel(live_dual_analysis_result, Path(tmp_dir) / "report.xlsx")
        assert out_path.exists()
        wb = openpyxl.load_workbook(out_path)
        
        # Check all 7 sheets
        assert "Summary" in wb.sheetnames
        assert "Dataset Details" in wb.sheetnames
        assert "Quality Issue Summary" in wb.sheetnames
        assert "Issue Details" in wb.sheetnames
        assert "Quality Dimensions" in wb.sheetnames
        assert "Relationships" in wb.sheetnames
        assert "Recommendations" in wb.sheetnames

        # Summary sheet checks
        summary_ws = wb["Summary"]
        assert summary_ws["B3"].value == live_dual_analysis_result.run_id

        # Verify "Issues Identified" section exists in Summary sheet
        summary_text_vals = [str(cell.value) for row in summary_ws.iter_rows() for cell in row if cell.value is not None]
        assert any("Issues Identified" in t for t in summary_text_vals)
        assert any("Severity" in t for t in summary_text_vals)
        assert any("Issue Category" in t for t in summary_text_vals)
        assert any("Relationship Integrity" in t for t in summary_text_vals)
        assert any("orders_related_to_customers" in t for t in summary_text_vals)

        # Relationships sheet checks
        rel_ws = wb["Relationships"]
        rel_text_vals = [str(cell.value) for row in rel_ws.iter_rows() for cell in row if cell.value is not None]
        assert any("Relationship Detected" in t for t in rel_text_vals)
        assert any("Integrity Status" in t for t in rel_text_vals)
        assert any("orders_related_to_customers" in t for t in rel_text_vals)
        assert any("customers_clean_100pct" in t for t in rel_text_vals)

        # Dataset Details sheet checks
        ds_ws = wb["Dataset Details"]
        assert ds_ws.cell(row=2, column=1).value == "customers_clean_100pct"
        assert ds_ws.cell(row=3, column=1).value == "orders_related_to_customers"

        # Quality Issue Summary checks
        qis_ws = wb["Quality Issue Summary"]
        assert qis_ws.cell(row=1, column=1).value == "Issue / Check Category"


def test_generate_excel_report_faulty_dataset(live_faulty_analysis_result):
    """Verify single faulty dataset populates Summary sheet with specific issue findings."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = generate_excel(live_faulty_analysis_result, Path(tmp_dir) / "faulty_report.xlsx")
        assert out_path.exists()
        wb = openpyxl.load_workbook(out_path)
        summary_ws = wb["Summary"]

        summary_text_vals = [str(cell.value) for row in summary_ws.iter_rows() for cell in row if cell.value is not None]
        assert any("Issues Identified" in t for t in summary_text_vals)
        assert any("customers_faulty" in t for t in summary_text_vals)
        assert any("Duplicates" in t or "Special Character" in t or "Null" in t for t in summary_text_vals)


def test_generate_json_report_live(live_dual_analysis_result):
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = generate_json(live_dual_analysis_result, Path(tmp_dir) / "report.json")
        assert out_path.exists()
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["scan_id"] == live_dual_analysis_result.run_id
        assert "summary_counts" in data
        assert data["summary_counts"]["relationships"] == 20
        assert "detailed_issues" in data
        assert len(data["detailed_issues"]) > 0
        assert "relationship_results" in data
        assert len(data["relationship_results"]) >= 1
        assert len(data["score"]["dimensions"]) == 6


# ---------------------------------------------------------------------------
# 3. Restored Historical AnalysisResult Reports
# ---------------------------------------------------------------------------

def test_generate_html_report_restored(restored_analysis_result):
    """Verify HTML report generates with full details from a restored SQLite scan."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = generate_html(restored_analysis_result, Path(tmp_dir) / "hist_report.html")
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert restored_analysis_result.run_id in content
        assert "customers_clean_100pct" in content
        assert "orders_related_to_customers" in content
        assert "Total Problems Detected" in content
        for dim in restored_analysis_result.score.dimensions:
            assert dim.name in content


def test_generate_excel_report_restored(restored_analysis_result):
    """Verify Excel workbook generates 7 sheets from a restored SQLite scan with issues in Summary."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = generate_excel(restored_analysis_result, Path(tmp_dir) / "hist_report.xlsx")
        assert out_path.exists()
        wb = openpyxl.load_workbook(out_path)
        assert "Summary" in wb.sheetnames
        assert "Dataset Details" in wb.sheetnames
        assert "Quality Issue Summary" in wb.sheetnames
        assert "Issue Details" in wb.sheetnames
        assert "Quality Dimensions" in wb.sheetnames
        assert "Relationships" in wb.sheetnames
        assert "Recommendations" in wb.sheetnames

        summary_ws = wb["Summary"]
        summary_text_vals = [str(cell.value) for row in summary_ws.iter_rows() for cell in row if cell.value is not None]
        assert any("Issues Identified" in t for t in summary_text_vals)
        assert any("orders_related_to_customers" in t for t in summary_text_vals)
        assert any("Relationship Integrity" in t for t in summary_text_vals)


def test_generate_json_report_restored(restored_analysis_result):
    """Verify JSON export generates with summary counts and details from restored scan."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = generate_json(restored_analysis_result, Path(tmp_dir) / "hist_report.json")
        assert out_path.exists()
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "relationship_results" in data
        assert len(data["relationship_results"]) >= 1


def test_dimensions_and_scan_id_retention(live_dual_analysis_result, restored_analysis_result):
    """Verify dimension scores and scan ID are identical between live and restored scans."""
    assert live_dual_analysis_result.run_id == restored_analysis_result.run_id
    assert len(live_dual_analysis_result.score.dimensions) == len(restored_analysis_result.score.dimensions)

    for live_dim, rest_dim in zip(live_dual_analysis_result.score.dimensions, restored_analysis_result.score.dimensions):
        assert live_dim.name == rest_dim.name
        assert live_dim.score == rest_dim.score


# ---------------------------------------------------------------------------
# 4. Standard Report Filename Convention Tests
# ---------------------------------------------------------------------------

def test_get_report_filename_convention(live_faulty_analysis_result, live_dual_analysis_result):
    """Verify generated report filenames follow <dataset_name>_data_quality_report.<ext>."""
    # 1. Single dataset AnalysisResult
    assert get_report_filename(live_faulty_analysis_result, "html") == "customers_faulty_data_quality_report.html"
    assert get_report_filename(live_faulty_analysis_result, "xlsx") == "customers_faulty_data_quality_report.xlsx"
    assert get_report_filename(live_faulty_analysis_result, ".json") == "customers_faulty_data_quality_report.json"

    # 2. Dual dataset AnalysisResult (uses primary dataset name)
    assert get_report_filename(live_dual_analysis_result, "html") == "customers_clean_100pct_data_quality_report.html"
    assert get_report_filename(live_dual_analysis_result, "xlsx") == "customers_clean_100pct_data_quality_report.xlsx"
    assert get_report_filename(live_dual_analysis_result, "json") == "customers_clean_100pct_data_quality_report.json"

    # 3. String dataset names
    assert get_report_filename("orders", "html") == "orders_data_quality_report.html"
    assert get_report_filename("orders.csv", "xlsx") == "orders_data_quality_report.xlsx"
    assert get_report_filename("orders.xlsx", "json") == "orders_data_quality_report.json"

    # 4. Sanitization of invalid filesystem characters and spaces
    assert get_report_filename("faulty/customers:2026", "html") == "faultycustomers2026_data_quality_report.html"
    assert get_report_filename("my raw dataset", "xlsx") == "my_raw_dataset_data_quality_report.xlsx"
    assert get_report_filename("", "json") == "dataset_data_quality_report.json"
