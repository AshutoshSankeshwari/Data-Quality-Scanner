"""core/ingestion/__init__.py"""
from .loader import load_file, load_csv, load_excel, get_excel_sheets, DataLoadError

__all__ = ["load_file", "load_csv", "load_excel", "get_excel_sheets", "DataLoadError"]
