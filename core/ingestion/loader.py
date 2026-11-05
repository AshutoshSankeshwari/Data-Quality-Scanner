"""
core/ingestion/loader.py
File loading layer: CSV and Excel ingestion with robust error handling,
encoding detection, and file validation.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------

class DataLoadError(Exception):
    """Raised when a file cannot be loaded. Message is user-friendly."""
    pass


# ---------------------------------------------------------------------------
# Supported extensions
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# Common delimiters to auto-detect
_DELIMITERS = [",", ";", "\t", "|"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_file(path: str | Path) -> Path:
    """
    Check file exists, is readable, and has a supported extension.
    Returns the resolved Path. Raises DataLoadError otherwise.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise DataLoadError(f"File not found: {p}")
    if not p.is_file():
        raise DataLoadError(f"Path is not a file: {p}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise DataLoadError(
            f"Unsupported file type '{p.suffix}'. Supported types: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS))
        )
    if os.access(p, os.R_OK) is False:
        raise DataLoadError(f"Permission denied: cannot read file {p}")
    return p


def detect_encoding(path: Path) -> str:
    """
    Detect file encoding using charset-normalizer (with chardet fallback).
    Returns a best-guess encoding string (e.g. 'utf-8', 'latin-1').
    """
    try:
        from charset_normalizer import from_path
        result = from_path(path).best()
        if result is not None:
            return result.encoding or "utf-8"
    except ImportError:
        pass
    # Fallback: try chardet
    try:
        import chardet
        with open(path, "rb") as f:
            raw = f.read(65536)
        detected = chardet.detect(raw)
        return detected.get("encoding") or "utf-8"
    except ImportError:
        pass
    return "utf-8"


def detect_delimiter(path: Path, encoding: str) -> str:
    """
    Sniff the CSV delimiter from the first few lines.
    Falls back to comma if detection is ambiguous.
    """
    import csv
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(4096)
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(_DELIMITERS))
        return dialect.delimiter
    except csv.Error:
        return ","


def load_csv(
    path: str | Path,
    delimiter: Optional[str] = None,
    encoding: Optional[str] = None,
    header_row: int = 0,
) -> pd.DataFrame:
    """
    Load a CSV file into a DataFrame.

    Args:
        path: Path to the CSV file.
        delimiter: Column delimiter. If None, auto-detected.
        encoding: File encoding. If None, auto-detected.
        header_row: Row index to use as header (0-based). Default 0.

    Returns:
        pd.DataFrame (may be empty if file has no data rows).

    Raises:
        DataLoadError: on any loading failure.
    """
    p = validate_file(path)

    if encoding is None:
        encoding = detect_encoding(p)

    if delimiter is None:
        delimiter = detect_delimiter(p, encoding)

    try:
        df = pd.read_csv(
            p,
            sep=delimiter,
            encoding=encoding,
            header=header_row,
            on_bad_lines="warn",
            low_memory=False,
        )
        # Strip whitespace from column names
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except pd.errors.EmptyDataError:
        # Return empty DataFrame — not a fatal error
        return pd.DataFrame()
    except UnicodeDecodeError as e:
        raise DataLoadError(
            f"Encoding error reading '{p.name}'. "
            f"Detected encoding was '{encoding}'. "
            f"Try specifying the encoding explicitly. Detail: {e}"
        )
    except Exception as e:
        raise DataLoadError(f"Could not read CSV file '{p.name}': {e}")


def get_excel_sheets(path: str | Path) -> list[str]:
    """
    Return the list of sheet names in an Excel workbook.

    Raises:
        DataLoadError: if the file cannot be opened.
    """
    p = validate_file(path)
    try:
        with pd.ExcelFile(p, engine="openpyxl") as xl:
            return list(xl.sheet_names)
    except Exception as e:
        raise DataLoadError(
            f"Could not open Excel file '{p.name}' — it may be corrupted or password-protected. "
            f"Detail: {e}"
        )


def load_excel(
    path: str | Path,
    sheet_name: str | int = 0,
    header_row: int = 0,
) -> pd.DataFrame:
    """
    Load a single sheet from an Excel file into a DataFrame.

    Args:
        path: Path to the .xlsx/.xls file.
        sheet_name: Sheet name or 0-based index. Default first sheet.
        header_row: Row index to use as header. Default 0.

    Returns:
        pd.DataFrame (may be empty).

    Raises:
        DataLoadError: on any loading failure.
    """
    p = validate_file(path)
    try:
        df = pd.read_excel(
            p,
            sheet_name=sheet_name,
            header=header_row,
            engine="openpyxl",
        )
        # Strip whitespace from column names
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        raise DataLoadError(
            f"Could not read Excel file '{p.name}' "
            f"(sheet='{sheet_name}'). "
            f"It may be corrupted or password-protected. Detail: {e}"
        )


def load_file(
    path: str | Path,
    sheet_name: str | int = 0,
    delimiter: Optional[str] = None,
    encoding: Optional[str] = None,
    header_row: int = 0,
) -> pd.DataFrame:
    """
    Unified loader — dispatches to load_csv or load_excel based on extension.
    """
    p = validate_file(path)
    if p.suffix.lower() == ".csv":
        return load_csv(p, delimiter=delimiter, encoding=encoding, header_row=header_row)
    else:
        return load_excel(p, sheet_name=sheet_name, header_row=header_row)
