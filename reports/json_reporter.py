"""
reports/json_reporter.py
Generates comprehensive machine-readable JSON structured output from an AnalysisResult,
including summary issue counts and detailed issue records with row numbers.
"""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import asdict
from core.models import AnalysisResult
from reports.summary_builder import build_issue_summary_counts, extract_detailed_issues


def _json_default(obj):
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "__dict__"):
        return asdict(obj)
    return str(obj)


def generate_json(
    result: AnalysisResult,
    output_path: str | Path,
    datasets: list[tuple[str, Any]] | dict[str, Any] | None = None,
) -> Path:
    """
    Export an AnalysisResult to a formatted JSON file with metadata, summary counts,
    and structured problem details.
    """
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    base_data = asdict(result)
    
    # Enrich with summary counts and flat detailed issues
    summary_counts = build_issue_summary_counts(result)
    detailed_issues = extract_detailed_issues(result, datasets=datasets)

    payload = {
        "report_type": "Data Quality Assessment Report",
        "app_version": "2.0",
        "scan_id": result.run_id,
        "timestamp": result.timestamp,
        "summary_counts": summary_counts,
        "detailed_issues": detailed_issues,
        **base_data,
    }

    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=_json_default, indent=2)

    return out_p
