"""
reports/__init__.py
Report generation package for HTML, Excel, and JSON deliverables with standardized naming.
"""
import re
from pathlib import Path

from core.models import AnalysisResult
from .html_reporter import generate_html
from .excel_reporter import generate_excel
from .json_reporter import generate_json


def get_report_filename(result_or_name: AnalysisResult | str, extension: str) -> str:
    """
    Generate standard report filename following: <dataset_name>_data_quality_report.<extension>
    
    Args:
        result_or_name: AnalysisResult object or string dataset name.
        extension: File extension string, e.g. 'html', 'xlsx', 'json' (with or without dot).
        
    Returns:
        Safe OS-compatible filename, e.g. 'customers_dirty_data_quality_report.xlsx'
    """
    if isinstance(result_or_name, AnalysisResult):
        primary = result_or_name.primary_dataset()
        raw_name = primary.name if primary else "dataset"
    else:
        raw_name = str(result_or_name)
        
    # Remove file extension from dataset name if present (e.g., 'customers.csv' -> 'customers')
    stem_name = Path(raw_name).stem if "." in raw_name else raw_name
    
    # Sanitize OS-unsafe characters: / \ : * ? " < > |
    safe_name = re.sub(r'[\\/*?:"<>|]', "", stem_name)
    # Replace spaces or multiple underscores with single underscore
    safe_name = re.sub(r'\s+', '_', safe_name).strip("._ ")
    
    if not safe_name:
        safe_name = "dataset"
        
    ext = extension.lstrip(".")
    return f"{safe_name}_data_quality_report.{ext}"


__all__ = ["generate_html", "generate_excel", "generate_json", "get_report_filename"]
