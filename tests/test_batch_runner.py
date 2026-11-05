"""
tests/test_batch_runner.py
Comprehensive automated test suite for headless Batch Mode (batch_runner.py).
Verifies non-UI execution, CLI arguments, exit codes, report generation,
SQLite persistence, relationship origin labeling, and error resilience.
"""
import pytest
import tempfile
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication

from batch_runner import run_batch
from db.repository import ScanRepository

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


def test_batch_mode_no_qapplication_initialized():
    """Verify batch runner can execute without initializing a QApplication."""
    # Before running, check that no QApplication is required
    app_before = QApplication.instance()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "reports"
        db_path = Path(tmp_dir) / "test.db"
        
        exit_code = run_batch([
            str(SAMPLES_DIR / "customers_clean_100pct.csv"),
            "--output", str(out_dir),
            "--db", str(db_path),
            "--quiet",
        ])
        
        assert exit_code == 0
        # Check that running batch mode did not create a QApplication instance if none existed
        if app_before is None:
            assert QApplication.instance() is None


def test_batch_single_clean_dataset():
    """1. Single clean dataset execution returns exit code 0 and generates clean reports with option 4."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "reports"
        db_path = Path(tmp_dir) / "test.db"

        exit_code = run_batch([
            str(SAMPLES_DIR / "customers_clean_100pct.csv"),
            "--config", str(CONFIG_PATH),
            "--output", str(out_dir),
            "--db", str(db_path),
        ], input_func=lambda _: "4")

        assert exit_code == 0
        assert (out_dir / "customers_clean_100pct_data_quality_report.html").exists()
        assert (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
        
        json_path = out_dir / "customers_clean_100pct_data_quality_report.json"
        assert json_path.exists()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["score"]["overall"] == 100.0
        assert data["summary_counts"]["total_problems"] == 0


def test_batch_single_faulty_dataset():
    """2. Single faulty dataset runs successfully (exit code 0) despite quality findings."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "reports"
        db_path = Path(tmp_dir) / "test.db"

        exit_code = run_batch([
            str(SAMPLES_DIR / "customers_faulty.csv"),
            "--config", str(CONFIG_PATH),
            "--output", str(out_dir),
            "--db", str(db_path),
        ], input_func=lambda _: "2")

        # IMPORTANT: Data quality findings MUST return exit code 0
        assert exit_code == 0
        json_path = out_dir / "customers_faulty_data_quality_report.json"
        assert json_path.exists()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["summary_counts"]["total_problems"] > 0
        assert len(data["detailed_issues"]) > 0


def test_batch_multiple_datasets_configured_relationship():
    """3 & 5 & 6 & 7: Multiple datasets with configured relationship."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "reports"
        db_path = Path(tmp_dir) / "test.db"

        exit_code = run_batch([
            str(SAMPLES_DIR / "customers_clean_100pct.csv"),
            str(SAMPLES_DIR / "orders_related_to_customers.csv"),
            "--config", str(CONFIG_PATH),
            "--output", str(out_dir),
            "--db", str(db_path),
        ], input_func=lambda _: "2")

        assert exit_code == 0
        json_path = out_dir / "customers_clean_100pct_data_quality_report.json"
        assert json_path.exists()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["relationship_results"]) == 1
        rel = data["relationship_results"][0]
        assert rel["origin"] == "configured"
        assert rel["parent_dataset"] == "customers_clean_100pct"
        assert rel["child_dataset"] == "orders_related_to_customers"
        assert rel["orphan_count"] == 20
        assert len(rel["sample_orphan_records"]) == 20
        assert rel["sample_orphan_records"][0]["key_value"] == "CUST9001"
        assert rel["sample_orphan_records"][0]["row_number"] == 131


def test_batch_multiple_datasets_automatic_relationship_without_config():
    """4. Multiple datasets without configured relationship automatically detects relationship."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "reports"
        db_path = Path(tmp_dir) / "test.db"
        empty_cfg_path = Path(tmp_dir) / "empty_cfg.yaml"
        empty_cfg_path.write_text("relationships: []\n", encoding="utf-8")

        exit_code = run_batch([
            str(SAMPLES_DIR / "customers_clean_100pct.csv"),
            str(SAMPLES_DIR / "orders_related_to_customers.csv"),
            "--config", str(empty_cfg_path),
            "--output", str(out_dir),
            "--db", str(db_path),
        ], input_func=lambda _: "2")

        assert exit_code == 0
        json_path = out_dir / "customers_clean_100pct_data_quality_report.json"
        assert json_path.exists()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["relationship_results"]) == 1
        rel = data["relationship_results"][0]
        assert rel["origin"] == "automatic"
        assert rel["orphan_count"] == 20


def test_batch_report_format_toggles():
    """8, 9, 10: Verify selective report generation flags (--html, --excel, --json)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "reports"
        
        # Only JSON requested via CLI flag (no prompt needed)
        exit_code = run_batch([
            str(SAMPLES_DIR / "customers_clean_100pct.csv"),
            "--json",
            "--output", str(out_dir),
            "--no-db",
        ])
        assert exit_code == 0
        assert (out_dir / "customers_clean_100pct_data_quality_report.json").exists()
        assert not (out_dir / "customers_clean_100pct_data_quality_report.html").exists()
        assert not (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()


def test_batch_sqlite_persistence():
    """11. Verify scan persistence to SQLite database and queryability."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "persisted_scans.db"

        exit_code = run_batch([
            str(SAMPLES_DIR / "customers_faulty.csv"),
            "--config", str(CONFIG_PATH),
            "--db", str(db_path),
            "--no-reports",
        ])

        assert exit_code == 0
        assert db_path.exists()
        repo = ScanRepository(db_path)
        assert repo.count_scans() == 1
        scans = repo.list_scans()
        assert scans[0]["primary_dataset"] == "customers_faulty"


def test_batch_invalid_arguments_exit_code_1():
    """12. Invalid command-line arguments return exit code 1."""
    # Unknown flag
    exit_code = run_batch(["--unrecognized-argument-xyz"])
    assert exit_code == 1

    # No input files
    exit_code_no_files = run_batch([])
    assert exit_code_no_files == 1


def test_batch_missing_file_exit_code_2():
    """13. Missing / non-existent dataset file returns exit code 2."""
    exit_code = run_batch(["non_existent_file_12345.csv"])
    assert exit_code == 2


def test_batch_unsupported_file_type_exit_code_2(tmp_path):
    """14. Unsupported file extension (e.g. .txt, .pdf) returns exit code 2."""
    bad_file = tmp_path / "data.txt"
    bad_file.write_text("col1,col2\n1,2\n", encoding="utf-8")

    exit_code = run_batch([str(bad_file)])
    assert exit_code == 2


def test_batch_invalid_config_yaml_exit_code_2(tmp_path):
    """Configuration YAML syntax error returns exit code 2."""
    bad_cfg = tmp_path / "bad_syntax.yaml"
    bad_cfg.write_text("checks: [unclosed list", encoding="utf-8")

    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--config", str(bad_cfg),
    ])
    assert exit_code == 2


def test_batch_runner_subprocess_cli_invocation(tmp_path):
    """Verify batch_runner.py executes as an external Python subprocess with piped input."""
    import sys
    import subprocess

    out_dir = tmp_path / "reports"
    script_path = Path(__file__).parent.parent / "batch_runner.py"

    cmd = [
        sys.executable,
        str(script_path),
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ]

    proc = subprocess.run(cmd, input="2\n", capture_output=True, text=True)
    assert proc.returncode == 0
    assert "Data Quality Scanner V2 -- Batch Mode" in proc.stdout
    assert "Scan completed successfully." in proc.stdout
    assert (out_dir / "customers_clean_100pct_data_quality_report.json").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.html").exists()


def test_batch_default_db_matches_central_default():
    """Verify batch_runner parser defaults to DEFAULT_DB_PATH (data/scanner.db)."""
    from batch_runner import create_parser
    from db.connection import DEFAULT_DB_PATH

    parser = create_parser()
    args = parser.parse_args([str(SAMPLES_DIR / "customers_clean_100pct.csv")])
    assert args.db == str(DEFAULT_DB_PATH)
    assert "scanner.db" in args.db


# ---------------------------------------------------------------------------
# Interactive Export Selection Flow Tests
# ---------------------------------------------------------------------------

def test_parse_export_selection():
    """Unit tests for parse_export_selection parsing logic."""
    from batch_runner import parse_export_selection

    # Single options
    assert parse_export_selection("1") == {"excel": True, "json": False, "html": False}
    assert parse_export_selection("2") == {"excel": False, "json": True, "html": False}
    assert parse_export_selection("3") == {"excel": False, "json": False, "html": True}
    assert parse_export_selection("4") == {"excel": True, "json": True, "html": True}

    # Multiple combinations
    assert parse_export_selection("1,3") == {"excel": True, "json": False, "html": True}
    assert parse_export_selection("1, 3") == {"excel": True, "json": False, "html": True}
    assert parse_export_selection("1,2,3") == {"excel": True, "json": True, "html": True}
    assert parse_export_selection("1, 2, 3") == {"excel": True, "json": True, "html": True}

    # Option 4 combined with others -> All formats
    assert parse_export_selection("1,4") == {"excel": True, "json": True, "html": True}
    assert parse_export_selection("4, 2") == {"excel": True, "json": True, "html": True}
    assert parse_export_selection("1, 2, 4") == {"excel": True, "json": True, "html": True}

    # Duplicate selections
    assert parse_export_selection("1, 1, 3") == {"excel": True, "json": False, "html": True}
    assert parse_export_selection("2,2") == {"excel": False, "json": True, "html": False}

    # Invalid inputs
    assert parse_export_selection("") is None
    assert parse_export_selection("   ") is None
    assert parse_export_selection("0") is None
    assert parse_export_selection("5") is None
    assert parse_export_selection("abc") is None
    assert parse_export_selection("1, 5") is None
    assert parse_export_selection("1, abc") is None
    assert parse_export_selection("1,,3") is None
    assert parse_export_selection(",1") is None
    assert parse_export_selection("1,") is None


def test_batch_interactive_selection_option_1_excel_only(tmp_path):
    """Option 1 generates Excel only."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: "1")

    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.json").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.html").exists()


def test_batch_interactive_selection_option_2_json_only(tmp_path):
    """Option 2 generates JSON only."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: "2")

    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.json").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.html").exists()


def test_batch_interactive_selection_option_3_html_only(tmp_path):
    """Option 3 generates HTML only."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: "3")

    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.html").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.json").exists()


def test_batch_interactive_selection_option_1_3_excel_and_html(tmp_path):
    """Option 1,3 generates Excel + HTML only."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: "1,3")

    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.html").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.json").exists()


def test_batch_interactive_selection_option_1_2_3_all(tmp_path):
    """Option 1,2,3 generates Excel + JSON + HTML."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: "1, 2, 3")

    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.json").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.html").exists()


def test_batch_interactive_selection_option_4_all(tmp_path):
    """Option 4 generates All formats (Excel + JSON + HTML)."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: "4")

    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.json").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.html").exists()


def test_batch_interactive_selection_invalid_then_valid(tmp_path, capsys):
    """Invalid inputs re-prompt with clear message until valid option is entered."""
    out_dir = tmp_path / "reports"
    
    # Inputs: "invalid", "5", then "1,3"
    inputs = iter(["invalid", "5", "1,3"])
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: next(inputs))

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Invalid selection. Please choose 1, 2, 3, or 4." in captured.out
    assert (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.html").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.json").exists()


def test_batch_interactive_selection_option_4_combined_with_others(tmp_path):
    """Option 4 combined with others (e.g. 1,4) treats as All formats without duplicate errors."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: "1, 4")

    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.json").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.html").exists()


def test_batch_interactive_selection_spaces_and_duplicates(tmp_path):
    """Spaces around commas and duplicate valid choices (e.g. ' 1 , 1 ,  3 ') are accepted cleanly."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--no-db",
    ], input_func=lambda _: " 1 , 1 ,  3 ")

    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.xlsx").exists()
    assert (out_dir / "customers_clean_100pct_data_quality_report.html").exists()
    assert not (out_dir / "customers_clean_100pct_data_quality_report.json").exists()


