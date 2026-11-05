"""
Tests for core/ingestion/loader.py
"""
import pytest
from pathlib import Path
import pandas as pd
import tempfile

from core.ingestion.loader import (
    load_file, load_csv, load_excel, get_excel_sheets,
    validate_file, DataLoadError,
)

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def test_validate_file_valid():
    csv_path = SAMPLES_DIR / "customers_clean_100pct.csv"
    resolved = validate_file(csv_path)
    assert resolved.exists()
    assert resolved.suffix == ".csv"


def test_validate_file_not_found():
    with pytest.raises(DataLoadError, match="File not found"):
        validate_file("non_existent_file_xyz.csv")


def test_validate_file_unsupported_extension():
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
        with pytest.raises(DataLoadError, match="Unsupported file type"):
            validate_file(tmp.name)


def test_load_csv_clean():
    csv_path = SAMPLES_DIR / "customers_clean_100pct.csv"
    df = load_csv(csv_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 200
    assert "Customer_ID" in df.columns
    assert "Customer_Name" in df.columns


def test_load_csv_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as tmp:
        tmp.write("")
        tmp_path = tmp.name

    try:
        df = load_csv(tmp_path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
    finally:
        Path(tmp_path).unlink()


def test_load_excel_sheets():
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
            pd.DataFrame({"A": [1, 2]}).to_excel(writer, sheet_name="Customers", index=False)
            pd.DataFrame({"B": [3, 4]}).to_excel(writer, sheet_name="Metadata", index=False)

        sheets = get_excel_sheets(tmp_path)
        assert "Customers" in sheets
        assert "Metadata" in sheets
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_load_excel_sheet_selection():
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
            pd.DataFrame({"Customer_ID": ["CUST0001", "CUST0002"]}).to_excel(writer, sheet_name="Customers", index=False)
            pd.DataFrame({"Property": ["Name", "Date"]}).to_excel(writer, sheet_name="Metadata", index=False)

        df_customers = load_excel(tmp_path, sheet_name="Customers")
        assert len(df_customers) == 2
        assert "Customer_ID" in df_customers.columns

        df_meta = load_excel(tmp_path, sheet_name="Metadata")
        assert len(df_meta) == 2
        assert "Property" in df_meta.columns
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_unified_load_file_csv():
    df = load_file(SAMPLES_DIR / "customers_clean_100pct.csv")
    assert len(df) == 200


def test_unified_load_file_excel():
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
            pd.DataFrame({"Customer_ID": ["CUST0001", "CUST0002"]}).to_excel(writer, sheet_name="Customers", index=False)

        df = load_file(tmp_path, sheet_name="Customers")
        assert len(df) == 2
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
