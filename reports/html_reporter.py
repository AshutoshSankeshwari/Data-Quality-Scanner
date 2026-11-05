"""
reports/html_reporter.py
Generates an actionable, self-contained HTML assessment report using Jinja2 templates.
"""
from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from core.models import AnalysisResult, format_display_timestamp
from reports.summary_builder import build_issue_summary_counts, extract_detailed_issues, count_affected_rows


def generate_html(
    result: AnalysisResult,
    output_path: str | Path,
    datasets: list[tuple[str, Any]] | dict[str, Any] | None = None,
) -> Path:
    """
    Generate an actionable HTML report for an AnalysisResult.
    Works for both live scans and historical scans restored from SQLite.
    """
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    env.filters["display_timestamp"] = format_display_timestamp
    template = env.get_template("report.html.j2")

    primary = result.primary_dataset()
    summary_counts = build_issue_summary_counts(result)
    detailed_issues = extract_detailed_issues(result, datasets=datasets)

    aff = count_affected_rows(result)
    aff_str = f"{aff:,}" if aff is not None else "—"

    html_content = template.render(
        result=result,
        primary_dataset=primary,
        summary_counts=summary_counts,
        detailed_issues=detailed_issues,
        affected_rows=aff_str,
    )

    with open(out_p, "w", encoding="utf-8") as f:
        f.write(html_content)

    return out_p
