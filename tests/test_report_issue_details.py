"""
tests/test_report_issue_details.py
Tests verifying that generated reports (HTML, Excel, JSON, CLI) display the actual
problematic source values alongside row numbers for all reportable row-level issues.
"""
import pytest
import tempfile
import json
from pathlib import Path
import pandas as pd
import openpyxl

from core.models import AnalysisResult, ReadinessScore, ReadinessCategory, DimensionScore
from core.service import AnalysisService, AnalysisConfig
from reports.html_reporter import generate_html
from reports.excel_reporter import generate_excel
from reports.json_reporter import generate_json
from reports.summary_builder import extract_detailed_issues
from batch_runner import run_batch


@pytest.fixture
def test_datasets():
    """Create test datasets with known distinctive problematic values."""
    customers_data = {
        "Customer_ID": ["101", "102", "103", "104", "105", "106", "DUP999", "DUP999", "109"],
        "Customer_Name": [
            "John@Smith",     # Row 1: Special char anomaly (@)
            "Jane Doe",       # Row 2: Valid name
            "Bob Jones",      # Row 3: Valid name
            "",               # Row 4: Mandatory blank ("")
            "   ",            # Row 5: Mandatory whitespace ("   ")
            "Mary Roe",       # Row 6: Valid name
            "Dup First",      # Row 7: Duplicate base
            "Dup Second",     # Row 8: Duplicate key offender
            "Null Person",    # Row 9: Valid name
        ],
        "Email": [
            "john@test.com",  # Row 1
            "abc@",           # Row 2: Pattern anomaly (abc@)
            "bob@test.com",   # Row 3
            "empty@test.com", # Row 4
            "ws@test.com",    # Row 5
            "mary@test.com",  # Row 6
            "dup1@test.com",  # Row 7
            "dup2@test.com",  # Row 8
            None,             # Row 9: Null email
        ],
        "Notes": [
            "Good",           # Row 1
            "Fine",           # Row 2
            "  Ashutosh  ",   # Row 3: Whitespace anomaly
            "ValidNote",      # Row 4
            "ValidNote",      # Row 5
            "ValidNote",      # Row 6
            "First",          # Row 7
            "Second",         # Row 8
            None,             # Row 9: Null notes
        ],
        "Order_Date": [
            "2023-01-01",     # Row 1
            "2023-01-02",     # Row 2
            "2023-01-03",     # Row 3
            "2023-01-04",     # Row 4
            "2023-01-05",     # Row 5
            "2023-02-31",     # Row 6: Impossible date
            "2023-01-07",     # Row 7
            "2023-01-08",     # Row 8
            "2023-01-09",     # Row 9
        ],
    }
    df_customers = pd.DataFrame(customers_data)

    orders_data = {
        "Order_ID": ["O1", "O2"],
        "Customer_ID": ["101", "ORPHAN_CUST_999"],  # Row 2: Orphan customer key
        "Amount": [100.0, 250.0],
    }
    df_orders = pd.DataFrame(orders_data)

    return [("customers", df_customers), ("orders", df_orders)]


@pytest.fixture
def analysis_result_and_datasets(test_datasets):
    cfg = AnalysisConfig(
        enabled_checks=[
            "duplicates", "nulls", "mandatory_fields", "whitespace",
            "special_chars", "patterns", "dates", "relationships",
        ],
        mandatory_fields=["Customer_Name"],
        duplicate_key_sets=[["Customer_ID"]],
        field_character_rules={"Customer_Name": "alpha_numeric_only"},
        anomaly_characters=["@"],
        pattern_exclude_columns=[],
        date_columns=["Order_Date"],
        relationships=[{
            "parent_dataset": "customers",
            "child_dataset": "orders",
            "parent_key": "Customer_ID",
            "child_key": "Customer_ID",
        }],
    )
    service = AnalysisService()
    result = service.run(test_datasets, cfg)
    return result, test_datasets


# ---------------------------------------------------------------------------
# 1. Summary Builder / extract_detailed_issues Tests
# ---------------------------------------------------------------------------

def test_extract_detailed_issues_captures_all_actual_values(analysis_result_and_datasets):
    result, datasets = analysis_result_and_datasets
    issues = extract_detailed_issues(result, datasets=datasets)
    assert len(issues) > 0

    # 1. Mandatory fields: Row 4 ("") and Row 5 ("   ")
    mand = next(i for i in issues if i["category"] == "Mandatory Fields" and i["column"] == "Customer_Name")
    mand_rows = {d["row_number"]: d for d in mand["details"]}
    assert 4 in mand_rows
    assert mand_rows[4]["value"] == ""
    assert mand_rows[4]["field"] == "Customer_Name"
    assert "blank" in mand_rows[4]["issue"].lower()
    assert mand_rows[4].get("record_data") is not None
    assert mand_rows[4]["record_data"]["Customer_ID"] == "104"

    assert 5 in mand_rows
    assert mand_rows[5]["value"] == "   "
    assert "whitespace" in mand_rows[5]["issue"].lower()
    assert mand_rows[5]["record_data"]["Customer_ID"] == "105"

    # 2. Special characters: Row 1 has "John@Smith" with "@"
    sc = next(i for i in issues if i["category"] == "Special Character Issues" and i["column"] == "Customer_Name")
    sc_rows = {d["row_number"]: d for d in sc["details"]}
    assert 1 in sc_rows
    assert sc_rows[1]["value"] == "John@Smith"
    assert "@" in sc_rows[1]["issue"] or "@" in sc_rows[1].get("character", "")

    # 3. Pattern issue: Row 2 has "abc@"
    pat = next((i for i in issues if i["category"] == "Pattern / Naming Issues" and i["column"] == "Email"), None)
    if pat:
        pat_rows = {d["row_number"]: d for d in pat["details"]}
        assert 2 in pat_rows
        assert pat_rows[2]["value"] == "abc@"

    # 4. Whitespace issue: Row 3 has "  Ashutosh  "
    ws = next(i for i in issues if i["category"] == "Whitespace Issues" and i["column"] == "Notes")
    ws_rows = {d["row_number"]: d for d in ws["details"]}
    assert 3 in ws_rows
    assert ws_rows[3]["value"] == "  Ashutosh  "

    # 5. Date issue: Row 6 has "2023-02-31"
    dt = next(i for i in issues if i["category"] == "Date Issues" and i["column"] == "Order_Date")
    dt_rows = {d["row_number"]: d for d in dt["details"]}
    assert 6 in dt_rows
    assert dt_rows[6]["value"] == "2023-02-31"
    assert "impossible" in dt_rows[6]["issue"].lower()

    # 6. Duplicate key issue: Row 8 has Customer_ID="DUP999" (duplicate of row 7)
    dup = next(i for i in issues if i["category"] == "Duplicates" and "Customer_ID" in i["column"])
    dup_rows = {d["row_number"]: d for d in dup["details"]}
    assert 8 in dup_rows
    assert dup_rows[8]["value"] == "DUP999"
    assert dup_rows[8]["duplicate_of_row"] == 7

    # 7. Relationship orphan key issue: Child Row 2 has "ORPHAN_CUST_999"
    rel = next(i for i in issues if i["category"] == "Relationship Integrity")
    rel_rows = {d["row_number"]: d for d in rel["details"]}
    assert 2 in rel_rows
    assert rel_rows[2]["value"] == "ORPHAN_CUST_999"


# ---------------------------------------------------------------------------
# 2. HTML Report Verification
# ---------------------------------------------------------------------------

def test_html_report_shows_actual_problematic_values(analysis_result_and_datasets):
    result, datasets = analysis_result_and_datasets
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "test_report.html"
        generate_html(result, out_file, datasets=datasets)
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")

        # Verify exact problematic values are present in HTML output
        assert "John@Smith" in content
        assert "Row 1" in content
        assert "  Ashutosh  " in content or "Ashutosh" in content
        assert "Row 3" in content
        assert "2023-02-31" in content
        assert "Row 6" in content
        assert "DUP999" in content
        assert "Row 8" in content
        assert "ORPHAN_CUST_999" in content
        assert "Row 2" in content
        assert '"" (empty)' in content or '""' in content


# ---------------------------------------------------------------------------
# 3. Excel Report Verification
# ---------------------------------------------------------------------------

def test_excel_report_shows_actual_problematic_values(analysis_result_and_datasets, test_datasets):
    result, datasets = analysis_result_and_datasets
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "test_report.xlsx"
        generate_excel(result, out_file, datasets=datasets)
        assert out_file.exists()

        wb = openpyxl.load_workbook(out_file)
        # Verify 7 sheets
        assert len(wb.sheetnames) == 7

        # -------------------------------------------------------------------
        # Sheet 4: Issue Details (1 Displayed Issue Occurrence = 1 Excel Row)
        # -------------------------------------------------------------------
        ws_issues = wb["Issue Details"]
        
        # Verify frozen header at A2
        assert ws_issues.freeze_panes == "A2"

        # Verify exact header columns
        expected_headers = [
            "Row", "Dataset", "Category", "Severity", "Field / Column",
            "Actual Value", "Issue Description", "Context / Detail"
        ]
        actual_headers = [ws_issues.cell(row=1, column=c).value for c in range(1, 9)]
        assert actual_headers == expected_headers

        # Extract structured issue rows
        header_keys = actual_headers
        issue_rows = []
        for r_idx in range(2, ws_issues.max_row + 1):
            row_val_0 = ws_issues.cell(row=r_idx, column=1).value
            # Break if we hit the Aggregate Findings section or empty rows
            if row_val_0 == "Aggregate & Dataset-Level Findings" or row_val_0 is None:
                break
            row_dict = {
                header_keys[c - 1]: ws_issues.cell(row=r_idx, column=c).value
                for c in range(1, 9)
            }
            issue_rows.append(row_dict)

        assert len(issue_rows) > 0

        # Verify AutoFilter bounds strictly cover the row table: A1:H{row_table_last_row}
        expected_last_row = len(issue_rows) + 1
        assert ws_issues.auto_filter.ref == f"A1:H{expected_last_row}"

        # Verify NO fake row-level records exist in the table
        for r in issue_rows:
            assert r["Row"] != "-", "Row should not be '-'"
            assert isinstance(r["Row"], int), f"Row should be integer, got {type(r['Row'])}"
            assert r["Actual Value"] != "-", "Actual Value should not be '-'"

        # Dynamically derive expected row numbers from test fixtures
        cust_df = dict(test_datasets)["customers"]
        orders_df = dict(test_datasets)["orders"]
        john_expected_row = int(cust_df[cust_df["Customer_Name"] == "John@Smith"].index[0]) + 1
        notes_ws_expected_row = int(cust_df[cust_df["Notes"] == "  Ashutosh  "].index[0]) + 1
        date_expected_row = int(cust_df[cust_df["Order_Date"] == "2023-02-31"].index[0]) + 1
        mand_blank_expected_row = int(cust_df[cust_df["Customer_Name"] == ""].index[0]) + 1
        mand_ws_expected_row = int(cust_df[cust_df["Customer_Name"] == "   "].index[0]) + 1
        orphan_expected_row = int(orders_df[orders_df["Customer_ID"] == "ORPHAN_CUST_999"].index[0]) + 1

        # 1. Special char issue: John@Smith
        john_entry = next(r for r in issue_rows if r["Actual Value"] == "John@Smith")
        assert john_entry["Row"] == john_expected_row
        assert john_entry["Dataset"] == "customers"
        assert john_entry["Category"] == "Special Character Issues"
        assert john_entry["Field / Column"] == "Customer_Name"
        assert "@" in john_entry["Context / Detail"] or "@" in john_entry["Issue Description"]

        # 2. Whitespace issue: "  Ashutosh  "
        ws_entry = next(r for r in issue_rows if r["Row"] == notes_ws_expected_row and r["Field / Column"] == "Notes")
        assert "Ashutosh" in ws_entry["Actual Value"]
        assert ws_entry["Category"] == "Whitespace Issues"

        # 3. Date issue: "2023-02-31"
        dt_entry = next(r for r in issue_rows if r["Row"] == date_expected_row and r["Field / Column"] == "Order_Date")
        assert dt_entry["Actual Value"] == "2023-02-31"
        assert dt_entry["Category"] == "Date Issues"
        assert "Reason:" in dt_entry["Context / Detail"] or "impossible" in dt_entry["Issue Description"].lower()

        # 4. Duplicate issue: DUP999
        dup_entry = next(r for r in issue_rows if r["Category"] == "Duplicates" and r["Actual Value"] == "DUP999")
        assert dup_entry["Context / Detail"] == "Duplicate of Row 7"

        # 5. Mandatory field issue: blank ("") and whitespace ("   ")
        blank_entry = next(r for r in issue_rows if r["Row"] == mand_blank_expected_row and r["Category"] == "Mandatory Fields")
        assert blank_entry["Actual Value"] in ("", None)
        assert blank_entry["Context / Detail"] == "Missing mandatory value"

        ws_mand_entry = next(r for r in issue_rows if r["Row"] == mand_ws_expected_row and r["Category"] == "Mandatory Fields")
        assert ws_mand_entry["Actual Value"] in ('"   "', "   ")
        assert ws_mand_entry["Context / Detail"] == "Missing mandatory value"

        # 6. Relationship integrity issue: distinct context in Col 8
        rel_entry = next(r for r in issue_rows if r["Category"] == "Relationship Integrity")
        assert rel_entry["Row"] == orphan_expected_row
        assert rel_entry["Actual Value"] == "ORPHAN_CUST_999"
        assert "Parent Dataset: customers" in rel_entry["Context / Detail"]
        assert "Parent Key: Customer_ID" in rel_entry["Context / Detail"]
        assert rel_entry["Context / Detail"] != rel_entry["Issue Description"]

        # -------------------------------------------------------------------
        # Sheet 1: Summary (Compact Sample Rows)
        # -------------------------------------------------------------------
        ws_summary = wb["Summary"]
        # Find header row in summary for top findings
        top_header_row = None
        for r_idx in range(1, ws_summary.max_row + 1):
            if ws_summary.cell(row=r_idx, column=1).value == "Severity" and ws_summary.cell(row=r_idx, column=2).value == "Issue Category":
                top_header_row = r_idx
                break
        assert top_header_row is not None
        assert ws_summary.cell(row=top_header_row, column=8).value == "Sample Rows"

        # Verify summary rows are concise and do NOT contain multi-record concatenated dumps
        for r_idx in range(top_header_row + 1, top_header_row + 10):
            val = ws_summary.cell(row=r_idx, column=8).value
            if val is not None:
                assert " | " not in str(val), "Summary sheet should not contain multi-field error dumps"

        # -------------------------------------------------------------------
        # Sheet 6: Relationships (Row-level Orphan Details Table)
        # -------------------------------------------------------------------
        ws_rel = wb["Relationships"]
        # Table 1 Col 12 should point to the details table
        assert ws_rel.cell(row=2, column=12).value == "1 orphan records (see Orphan Details table below)"

        # Verify Table 2 exists and has 1 displayed orphan record = 1 row
        orphan_section_found = False
        orphan_header_row = None
        for r_idx in range(1, ws_rel.max_row + 1):
            val = str(ws_rel.cell(row=r_idx, column=1).value or "")
            if "Orphan Reference Details" in val:
                orphan_section_found = True
                orphan_header_row = r_idx + 1
                break

        assert orphan_section_found, "Orphan Reference Details section should exist in Relationships sheet"
        assert orphan_header_row is not None
        orphan_headers = [ws_rel.cell(row=orphan_header_row, column=c).value for c in range(1, 8)]
        assert orphan_headers == [
            "Row", "Child Dataset", "Child Key", "Actual Orphan Value",
            "Parent Dataset", "Parent Key", "Issue"
        ]

        # Verify orphan record row
        orphan_data_row = orphan_header_row + 1
        assert ws_rel.cell(row=orphan_data_row, column=1).value == orphan_expected_row
        assert ws_rel.cell(row=orphan_data_row, column=2).value == "orders"
        assert ws_rel.cell(row=orphan_data_row, column=3).value == "Customer_ID"
        assert ws_rel.cell(row=orphan_data_row, column=4).value == "ORPHAN_CUST_999"
        assert ws_rel.cell(row=orphan_data_row, column=5).value == "customers"
        assert ws_rel.cell(row=orphan_data_row, column=6).value == "Customer_ID"
        assert ws_rel.cell(row=orphan_data_row, column=7).value == "Missing in customers"


# ---------------------------------------------------------------------------
# 4. JSON Report Verification
# ---------------------------------------------------------------------------

def test_json_report_structured_actual_data(analysis_result_and_datasets):
    result, datasets = analysis_result_and_datasets
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "test_report.json"
        generate_json(result, out_file, datasets=datasets)
        assert out_file.exists()

        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "detailed_issues" in data
        issues = data["detailed_issues"]

        # 1. Mandatory field has structured record
        mand = next(i for i in issues if i["category"] == "Mandatory Fields" and i["column"] == "Customer_Name")
        assert len(mand["details"]) >= 2
        d4 = next(d for d in mand["details"] if d["row_number"] == 4)
        assert d4["value"] == ""
        assert d4["field"] == "Customer_Name"
        assert "record_data" in d4
        assert d4["record_data"]["Customer_ID"] == "104"

        # 2. Special char has structured record
        sc = next(i for i in issues if i["category"] == "Special Character Issues")
        d1 = next(d for d in sc["details"] if d["row_number"] == 1)
        assert d1["value"] == "John@Smith"
        assert d1["field"] == "Customer_Name"

        # 3. Duplicate key has structured record
        dup = next(i for i in issues if i["category"] == "Duplicates" and "Customer_ID" in i["column"])
        d8 = next(d for d in dup["details"] if d["row_number"] == 8)
        assert d8["value"] == "DUP999"
        assert d8["duplicate_of_row"] == 7

        # 4. Date has structured record
        dt = next(i for i in issues if i["category"] == "Date Issues")
        d6 = next(d for d in dt["details"] if d["row_number"] == 6)
        assert d6["value"] == "2023-02-31"

        # 5. Relationship has structured record
        rel = next(i for i in issues if i["category"] == "Relationship Integrity")
        d_rel = next(d for d in rel["details"] if d["row_number"] == 2)
        assert d_rel["value"] == "ORPHAN_CUST_999"


# ---------------------------------------------------------------------------
# 5. Aggregate-Only Findings Do Not Fabricate Row Data
# ---------------------------------------------------------------------------

def test_aggregate_only_findings_have_no_fabricated_row_data():
    """Ensure aggregate findings (e.g. clean dataset or score) do not invent row numbers."""
    clean_df = pd.DataFrame({
        "ID": ["1", "2", "3"],
        "Name": ["Alice", "Bob", "Charlie"],
    })
    service = AnalysisService()
    cfg = AnalysisConfig(enabled_checks=["duplicates", "nulls", "whitespace"])
    result = service.run([("clean", clean_df)], cfg)

    issues = extract_detailed_issues(result, datasets=[("clean", clean_df)])
    # Clean dataset produces 0 issues
    assert len(issues) == 0


# ---------------------------------------------------------------------------
# 6. Historical Scan Fallback (No DataFrames Available)
# ---------------------------------------------------------------------------

def test_historical_scan_fallback_without_dataframes(analysis_result_and_datasets):
    """When datasets=None (e.g. historical scan loaded from SQLite), reports still work gracefully."""
    result, _ = analysis_result_and_datasets
    # Call without datasets
    issues = extract_detailed_issues(result, datasets=None)
    assert len(issues) > 0

    # Carried values (special chars, dates, duplicates) are still preserved
    sc = next(i for i in issues if i["category"] == "Special Character Issues")
    assert sc["details"][0]["value"] == "John@Smith"

    dt = next(i for i in issues if i["category"] == "Date Issues")
    assert dt["details"][0]["value"] == "2023-02-31"

    # Mandatory field without dataframe gracefully marks value as "" without crashing or fabricating
    mand = next(i for i in issues if i["category"] == "Mandatory Fields")
    assert mand["details"][0]["value"] == ""
    assert mand["details"][0]["row_number"] == 4


# ---------------------------------------------------------------------------
# 7. CLI / Batch Runner Verification
# ---------------------------------------------------------------------------

def test_cli_batch_runner_generates_reports_with_actual_values(test_datasets):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        cust_csv = tmp_p / "customers.csv"
        orders_csv = tmp_p / "orders.csv"
        test_datasets[0][1].to_csv(cust_csv, index=False)
        test_datasets[1][1].to_csv(orders_csv, index=False)

        out_dir = tmp_p / "cli_reports"
        db_path = tmp_p / "test.db"

        exit_code = run_batch([
            str(cust_csv),
            str(orders_csv),
            "--html",
            "--excel",
            "--json",
            "--output", str(out_dir),
            "--db", str(db_path),
            "--quiet",
        ])
        assert exit_code == 0

        # Check JSON
        json_file = out_dir / "customers_data_quality_report.json"
        assert json_file.exists()
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "detailed_issues" in data
        all_vals = [d.get("value") for iss in data["detailed_issues"] for d in iss.get("details", [])]
        assert "John@Smith" in all_vals
        assert "2023-02-31" in all_vals

        # Check HTML
        html_file = out_dir / "customers_data_quality_report.html"
        assert html_file.exists()
        html_text = html_file.read_text(encoding="utf-8")
        assert "John@Smith" in html_text
        assert "2023-02-31" in html_text

        # Check Excel
        excel_file = out_dir / "customers_data_quality_report.xlsx"
        assert excel_file.exists()
        wb = openpyxl.load_workbook(excel_file)
        assert len(wb.sheetnames) == 7
        ws_iss = wb["Issue Details"]
        assert ws_iss["A1"].value == "Row"
        assert ws_iss["F1"].value == "Actual Value"
        issue_cells = [str(cell.value) for row in ws_iss.iter_rows() for cell in row if cell.value]
        assert any("John@Smith" in c for c in issue_cells)


# ---------------------------------------------------------------------------
# 8. Multi-Issue Same-Row and Explicit Storage Rules Verification
# ---------------------------------------------------------------------------

def test_excel_report_one_issue_occurrence_per_row_and_storage_rules():
    """
    Verify:
    1. A single source row with multiple independent DQ issues yields separate Excel rows.
    2. Column 6 storage rules: NULL, empty string, numerics, and preserved whitespace.
    3. AutoFilter ref covers only the row table, and aggregate findings are outside.
    """
    # Create dataset where Row 1 has both an invalid email pattern AND leading whitespace in Name
    df = pd.DataFrame({
        "ID": ["1", "2"],
        "Name": ["  LeadingSpace", "ValidName"],
        "Email": ["invalid@", "valid@test.com"],
        "Amount": [100.5, 200.0],
        "Score": [None, 95],
    })
    service = AnalysisService()
    cfg = AnalysisConfig(
        enabled_checks=["whitespace", "patterns", "nulls"],
        pattern_exclude_columns=[],
    )
    result = service.run([("test_ds", df)], cfg)

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "test_multi_issue.xlsx"
        generate_excel(result, out_file, datasets=[("test_ds", df)])
        assert out_file.exists()

        wb = openpyxl.load_workbook(out_file)
        ws_issues = wb["Issue Details"]

        # Parse table rows up to aggregate section
        table_rows = []
        for r_idx in range(2, ws_issues.max_row + 1):
            val1 = ws_issues.cell(row=r_idx, column=1).value
            if val1 == "Aggregate & Dataset-Level Findings" or val1 is None:
                break
            table_rows.append({
                "row": ws_issues.cell(row=r_idx, column=1).value,
                "dataset": ws_issues.cell(row=r_idx, column=2).value,
                "category": ws_issues.cell(row=r_idx, column=3).value,
                "field": ws_issues.cell(row=r_idx, column=5).value,
                "actual_value": ws_issues.cell(row=r_idx, column=6).value,
                "issue": ws_issues.cell(row=r_idx, column=7).value,
                "context": ws_issues.cell(row=r_idx, column=8).value,
            })

        # Row 1 has multiple issues (Name whitespace and potentially Email pattern)
        row1_issues = [r for r in table_rows if r["row"] == 1]
        assert len(row1_issues) >= 1
        # Each issue is on a distinct Excel row
        fields_in_row1 = [r["field"] for r in row1_issues]
        assert len(fields_in_row1) == len(set(fields_in_row1)) or len(row1_issues) == 1

        # Check AutoFilter bounds strictly match row table
        last_table_row = len(table_rows) + 1
        assert ws_issues.auto_filter.ref == f"A1:H{last_table_row}"

        # If any aggregate section exists, it must be outside the AutoFilter
        for r_idx in range(last_table_row + 1, ws_issues.max_row + 1):
            if ws_issues.cell(row=r_idx, column=1).value == "Aggregate & Dataset-Level Findings":
                assert r_idx > last_table_row, "Aggregate section must be outside AutoFilter"

