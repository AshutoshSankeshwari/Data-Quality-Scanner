"""
reports/excel_reporter.py
Generates an actionable, multi-sheet formatted Excel assessment report using openpyxl.
Features an executive Summary worksheet with immediate top findings, dataset details,
readiness scoring, quality dimensions, detailed issue breakdowns, relationships, and recommendations.
Supports both live AnalysisResult objects and historical scans restored from SQLite.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from core.models import AnalysisResult, format_display_timestamp
from reports.summary_builder import build_issue_summary_counts, extract_detailed_issues, _format_row_range, count_affected_rows

MAX_SUMMARY_ISSUES = 20

THIN_BORDER = Border(
    left=Side(style="thin", color="D1D5DB"),
    right=Side(style="thin", color="D1D5DB"),
    top=Side(style="thin", color="D1D5DB"),
    bottom=Side(style="thin", color="D1D5DB"),
)


def _apply_header_style(ws, row: int, num_cols: int, bg_color: str = "1E3A8A"):
    header_fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)
        cell.border = THIN_BORDER


def _auto_fit_columns(ws, min_width: int = 12, max_width: int = 65):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            lines = val_str.split("\n")
            line_max = max(len(l) for l in lines) if lines else len(val_str)
            max_len = max(max_len, line_max)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, min_width), max_width)


def generate_excel(
    result: AnalysisResult,
    output_path: str | Path,
    datasets: list[tuple[str, Any]] | dict[str, Any] | None = None,
) -> Path:
    """
    Generate a comprehensive 7-sheet Excel (.xlsx) report from an AnalysisResult.
    The Summary sheet immediately surfaces executive scores, dimensions, and top identified issues.
    """
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()

    title_font = Font(name="Segoe UI", size=15, bold=True, color="1E3A8A")
    section_font = Font(name="Segoe UI", size=11, bold=True, color="1E293B")
    bold_font = Font(name="Segoe UI", size=9, bold=True)
    normal_font = Font(name="Segoe UI", size=9)
    note_font = Font(name="Segoe UI", size=8, italic=True, color="64748B")

    summary_counts = build_issue_summary_counts(result)
    detailed_issues = extract_detailed_issues(result, datasets=datasets)
    primary = result.primary_dataset()

    # =======================================================================
    # Sheet 1: Executive Summary
    # =======================================================================
    ws_summary = wb.active
    ws_summary.title = "Summary"

    ws_summary["A1"] = "Data Quality Assessment — Executive Summary"
    ws_summary["A1"].font = title_font

    ws_summary["A3"] = "Scan ID:"
    ws_summary["B3"] = result.run_id
    ws_summary["A4"] = "Analysis Timestamp:"
    ws_summary["B4"] = format_display_timestamp(result.timestamp)
    ws_summary["A5"] = "Datasets Scanned:"
    ws_summary["B5"] = len(result.datasets)
    ws_summary["A6"] = "Primary Dataset:"
    ws_summary["B6"] = primary.name if primary else "N/A"
    ws_summary["A7"] = "Total Issue Findings:"
    ws_summary["B7"] = len(detailed_issues)
    ws_summary["A8"] = "Total Problem Instances / Affected Records:"
    ws_summary["B8"] = summary_counts["total_problems"]
    aff = count_affected_rows(result)
    ws_summary["A9"] = "Affected Rows (Unique):"
    ws_summary["B9"] = aff if aff is not None else "—"

    for r in range(3, 10):
        ws_summary[f"A{r}"].font = bold_font
        ws_summary[f"B{r}"].font = normal_font

    curr_row = 11
    if result.score:
        ws_summary.cell(row=curr_row, column=1, value="Data Quality Performance & Readiness Score").font = section_font
        curr_row += 1

        score_rows = [
            ("Overall Score:", round(result.score.overall, 2)),
            ("Readiness Category:", result.score.category.value if hasattr(result.score.category, "value") else str(result.score.category)),
            ("Critical Issues:", result.score.blocker_count),
            ("High Severity Issues:", result.score.high_count),
            ("Medium Severity Issues:", result.score.medium_count),
            ("Low Severity Issues:", result.score.low_count),
        ]
        for label, val in score_rows:
            ws_summary.cell(row=curr_row, column=1, value=label).font = bold_font
            ws_summary.cell(row=curr_row, column=2, value=val).font = normal_font
            curr_row += 1

        curr_row += 1
        ws_summary.cell(row=curr_row, column=1, value="Quality Dimensions Summary").font = section_font
        curr_row += 1

        dim_headers = ["Dimension", "Diagnostic Score (/100)", "Status"]
        for c_idx, h in enumerate(dim_headers, 1):
            ws_summary.cell(row=curr_row, column=c_idx, value=h)
        _apply_header_style(ws_summary, curr_row, len(dim_headers))
        curr_row += 1

        for dim in result.score.dimensions:
            status = "Healthy" if dim.score >= 90 else ("Acceptable" if dim.score >= 75 else "Needs Attention")
            ws_summary.cell(row=curr_row, column=1, value=dim.name).font = normal_font
            ws_summary.cell(row=curr_row, column=2, value=round(dim.score, 1)).font = normal_font
            ws_summary.cell(row=curr_row, column=3, value=status).font = normal_font
            for c in range(1, len(dim_headers) + 1):
                ws_summary.cell(row=curr_row, column=c).border = THIN_BORDER
            curr_row += 1

    # Add "Issues Identified" section to Summary worksheet
    curr_row += 1
    ws_summary.cell(row=curr_row, column=1, value="Issues Identified (Top Findings)").font = section_font
    curr_row += 1

    note_text = (
        f"Total Findings: {len(detailed_issues)} | Showing top {min(len(detailed_issues), MAX_SUMMARY_ISSUES)} findings. "
        f"See 'Issue Details' sheet for the complete breakdown."
    )
    ws_summary.cell(row=curr_row, column=1, value=note_text).font = note_font
    curr_row += 1

    iss_headers = [
        "Severity", "Issue Category", "Dataset", "Affected Field(s)",
        "Affected Records", "% of Total", "Problem Description", "Sample Rows"
    ]
    for c_idx, h in enumerate(iss_headers, 1):
        ws_summary.cell(row=curr_row, column=c_idx, value=h)
    _apply_header_style(ws_summary, curr_row, len(iss_headers), bg_color="1E3A8A")
    curr_row += 1

    if detailed_issues:
        for iss in detailed_issues[:MAX_SUMMARY_ISSUES]:
            sev_str = (iss.get("severity") or "Info").upper()
            
            # Plain text severity without colored background
            cell_sev = ws_summary.cell(row=curr_row, column=1, value=sev_str)
            cell_sev.font = bold_font
            cell_sev.alignment = Alignment(horizontal="center", vertical="center")

            ws_summary.cell(row=curr_row, column=2, value=iss.get("category", "")).font = normal_font
            ws_summary.cell(row=curr_row, column=3, value=iss.get("dataset", "")).font = normal_font
            ws_summary.cell(row=curr_row, column=4, value=iss.get("column", "")).font = normal_font
            
            cell_aff = ws_summary.cell(row=curr_row, column=5, value=iss.get("affected_count", 0))
            cell_aff.font = bold_font
            cell_aff.alignment = Alignment(horizontal="right", vertical="center")
            
            pct_val = iss.get("affected_pct", 0.0)
            cell_pct = ws_summary.cell(row=curr_row, column=6, value=f"{pct_val:.1f}%" if pct_val > 0 else "-")
            cell_pct.font = normal_font
            cell_pct.alignment = Alignment(horizontal="right", vertical="center")

            cell_desc = ws_summary.cell(row=curr_row, column=7, value=iss.get("issue_type", ""))
            cell_desc.font = normal_font
            cell_desc.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

            # Use concise sample rows only (no raw Python dicts, no long concatenated error values)
            s_rows = iss.get("sample_rows", [])
            row_str = _format_row_range(s_rows, max_items=5) if s_rows else (
                f"{iss.get('affected_count', 0)} affected rows" if iss.get("affected_count", 0) > 0 else "-"
            )
            cell_ex = ws_summary.cell(row=curr_row, column=8, value=row_str)
            cell_ex.font = normal_font
            cell_ex.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

            for c in range(1, 9):
                ws_summary.cell(row=curr_row, column=c).border = THIN_BORDER

            curr_row += 1
    else:
        ws_summary.cell(row=curr_row, column=1, value="No quality issues detected — dataset is clean.").font = normal_font
        for c in range(1, 9):
            ws_summary.cell(row=curr_row, column=c).border = THIN_BORDER
        curr_row += 1

    _auto_fit_columns(ws_summary, max_width=65)

    # =======================================================================
    # Sheet 2: Dataset Details
    # =======================================================================
    ws_ds = wb.create_sheet(title="Dataset Details")
    ds_headers = [
        "Dataset Name", "Role", "File Type", "Record Count", "Column Count",
        "Null Cells %", "Duplicate Rows", "Duplicate Row %", "Scan ID", "Timestamp"
    ]
    for c_idx, h in enumerate(ds_headers, 1):
        ws_ds.cell(row=1, column=c_idx, value=h)
    _apply_header_style(ws_ds, 1, len(ds_headers), bg_color="1E3A8A")

    for r_idx, ds in enumerate(result.datasets, 2):
        role_str = "Primary" if ds.is_primary or r_idx == 2 else "Secondary"
        ws_ds.cell(row=r_idx, column=1, value=ds.name).font = normal_font
        ws_ds.cell(row=r_idx, column=2, value=role_str).font = bold_font
        ws_ds.cell(row=r_idx, column=3, value=ds.file_type or "CSV").font = normal_font
        ws_ds.cell(row=r_idx, column=4, value=ds.row_count).font = normal_font
        ws_ds.cell(row=r_idx, column=5, value=ds.column_count).font = normal_font
        ws_ds.cell(row=r_idx, column=6, value=f"{ds.overall_null_pct:.1f}%").font = normal_font
        ws_ds.cell(row=r_idx, column=7, value=ds.duplicate_row_count).font = normal_font
        ws_ds.cell(row=r_idx, column=8, value=f"{ds.duplicate_row_pct:.1f}%").font = normal_font
        ws_ds.cell(row=r_idx, column=9, value=result.run_id).font = normal_font
        ws_ds.cell(row=r_idx, column=10, value=format_display_timestamp(result.timestamp)).font = normal_font
        for c in range(1, 11):
            ws_ds.cell(row=r_idx, column=c).border = THIN_BORDER

    _auto_fit_columns(ws_ds)

    # =======================================================================
    # Sheet 3: Quality Issue Summary
    # =======================================================================
    ws_qis = wb.create_sheet(title="Quality Issue Summary")
    qis_headers = ["Issue / Check Category", "Problems Detected", "Status"]
    for c_idx, h in enumerate(qis_headers, 1):
        ws_qis.cell(row=1, column=c_idx, value=h)
    _apply_header_style(ws_qis, 1, len(qis_headers), bg_color="1E3A8A")

    cat_rows = [
        ("Duplicates (Full-Row & Key-Based)", summary_counts["duplicates"]),
        ("Null / Blank / Empty-String Values", summary_counts["nulls_and_blanks"]),
        ("Mandatory Field Failures", summary_counts["mandatory_fields"]),
        ("Whitespace Anomalies (Leading/Trailing/Internal)", summary_counts["whitespace"]),
        ("Special Character Violations", summary_counts["special_chars"]),
        ("Date & Format Inconsistencies", summary_counts["dates"]),
        ("Pattern & Naming Inconsistencies", summary_counts["patterns"]),
        ("Relationship Referential Integrity Orphans", summary_counts["relationships"]),
    ]

    for r_idx, (cat_name, count) in enumerate(cat_rows, 2):
        status = "PASSED (Clean)" if count == 0 else "ISSUES DETECTED"
        ws_qis.cell(row=r_idx, column=1, value=cat_name).font = normal_font
        ws_qis.cell(row=r_idx, column=2, value=count).font = bold_font
        ws_qis.cell(row=r_idx, column=3, value=status).font = bold_font
        for c in range(1, 4):
            ws_qis.cell(row=r_idx, column=c).border = THIN_BORDER

    total_r = len(cat_rows) + 2
    ws_qis.cell(row=total_r, column=1, value="Total Problems Detected").font = bold_font
    ws_qis.cell(row=total_r, column=2, value=summary_counts["total_problems"]).font = bold_font
    ws_qis.cell(row=total_r, column=3, value="ATTENTION REQUIRED" if summary_counts["total_problems"] > 0 else "ALL CHECKS CLEAN").font = bold_font
    for c in range(1, 4):
        ws_qis.cell(row=total_r, column=c).border = THIN_BORDER

    _auto_fit_columns(ws_qis)

    # =======================================================================
    # Sheet 4: Issue Details (Complete Detailed View)
    # =======================================================================
    ws_issues = wb.create_sheet(title="Issue Details")
    issue_headers = [
        "Row", "Dataset", "Category", "Severity", "Field / Column",
        "Actual Value", "Issue Description", "Context / Detail"
    ]
    for c_idx, h in enumerate(issue_headers, 1):
        ws_issues.cell(row=1, column=c_idx, value=h)
    _apply_header_style(ws_issues, 1, len(issue_headers), bg_color="1E3A8A")
    ws_issues.freeze_panes = "A2"

    curr_row = 2
    row_count_in_table = 0
    aggregate_findings = []

    if detailed_issues:
        for iss in detailed_issues:
            details = iss.get("details", [])
            # Aggregate-only finding without row-level details
            if not details and iss.get("affected_count", 0) > 0:
                aggregate_findings.append(iss)
                continue

            for rec in details:
                r_num = rec.get("row_number")
                if r_num is None:
                    continue

                ds_name = rec.get("dataset") or iss.get("dataset", "")
                cat_name = iss.get("category", "")
                sev_str = (iss.get("severity") or "Info").upper()
                field_name = rec.get("field", "")
                raw_val = rec.get("value")

                # Column 6: Actual Value storage rules
                # - Python None / missing source value -> "NULL"
                # - Empty string -> ""
                # - Whitespace-only string -> preserve whitespace content, e.g. f'"{raw_val}"'
                # - Numeric values -> numeric Excel values (int, float)
                # - Other native values -> convert safely preserving content
                if raw_val is None:
                    stored_val = "NULL"
                elif isinstance(raw_val, bool):
                    stored_val = raw_val
                elif isinstance(raw_val, (int, float)):
                    stored_val = "NULL" if pd.isna(raw_val) else raw_val
                elif isinstance(raw_val, str):
                    if raw_val == "":
                        stored_val = ""
                    elif raw_val.strip() == "":
                        stored_val = f'"{raw_val}"'
                    else:
                        stored_val = raw_val
                else:
                    stored_val = str(raw_val)

                issue_desc = rec.get("issue") or iss.get("issue_type", "")

                # Column 8: Context / Detail mapping
                if cat_name == "Relationship Integrity":
                    p_ds = rec.get("parent_dataset") or ""
                    p_key = rec.get("parent_key") or ""
                    if p_ds or p_key:
                        ctx = f"Parent Dataset: {p_ds}; Parent Key: {p_key}"
                    else:
                        ctx = issue_desc
                elif cat_name == "Pattern / Naming Issues":
                    dom = rec.get("dominant_pattern")
                    pat = rec.get("pattern")
                    if dom:
                        ctx = f"Expected Pattern: {dom}"
                    elif pat:
                        ctx = f"Pattern: {pat}"
                    else:
                        ctx = "-"
                elif cat_name == "Special Character Issues":
                    ch = rec.get("character")
                    ru = rec.get("rule")
                    if ch:
                        ctx = f"Invalid Character: {ch}"
                    elif ru:
                        ctx = f"Rule: {ru}"
                    else:
                        ctx = "-"
                elif cat_name == "Date Issues":
                    reason = rec.get("reason")
                    ctx = f"Reason: {reason}" if reason else "-"
                elif cat_name == "Duplicates":
                    dup_of = rec.get("duplicate_of_row")
                    ctx = f"Duplicate of Row {dup_of}" if dup_of is not None else "-"
                elif cat_name == "Mandatory Fields":
                    ctx = "Missing mandatory value"
                else:
                    ctx = rec.get("issue") or "-"

                c_row = ws_issues.cell(row=curr_row, column=1, value=int(r_num))
                c_row.font = normal_font
                c_row.alignment = Alignment(horizontal="center", vertical="center")

                c_ds = ws_issues.cell(row=curr_row, column=2, value=ds_name)
                c_ds.font = normal_font
                c_ds.alignment = Alignment(horizontal="left", vertical="center")

                c_cat = ws_issues.cell(row=curr_row, column=3, value=cat_name)
                c_cat.font = normal_font
                c_cat.alignment = Alignment(horizontal="left", vertical="center")

                c_sev = ws_issues.cell(row=curr_row, column=4, value=sev_str)
                c_sev.font = bold_font
                c_sev.alignment = Alignment(horizontal="center", vertical="center")

                c_fld = ws_issues.cell(row=curr_row, column=5, value=field_name)
                c_fld.font = normal_font
                c_fld.alignment = Alignment(horizontal="left", vertical="center")

                c_val = ws_issues.cell(row=curr_row, column=6, value=stored_val)
                c_val.font = normal_font
                is_num = isinstance(stored_val, (int, float)) and not isinstance(stored_val, bool)
                c_val.alignment = Alignment(horizontal="right" if is_num else "left", vertical="center")

                c_iss = ws_issues.cell(row=curr_row, column=7, value=issue_desc)
                c_iss.font = normal_font
                c_iss.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

                c_ctx = ws_issues.cell(row=curr_row, column=8, value=ctx)
                c_ctx.font = normal_font
                c_ctx.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

                for c in range(1, 9):
                    ws_issues.cell(row=curr_row, column=c).border = THIN_BORDER

                curr_row += 1
                row_count_in_table += 1

    if row_count_in_table > 0:
        row_table_last_row = curr_row - 1
        ws_issues.auto_filter.ref = f"A1:H{row_table_last_row}"
    else:
        ws_issues.cell(row=2, column=1, value="No row-level issues detected.").font = normal_font
        for c in range(1, 9):
            ws_issues.cell(row=2, column=c).border = THIN_BORDER
        row_table_last_row = 2

    # Column widths for Sheet 4 table
    issue_col_widths = {
        "A": 10,
        "B": 18,
        "C": 26,
        "D": 14,
        "E": 24,
        "F": 30,
        "G": 38,
        "H": 36,
    }
    for col_let, wid in issue_col_widths.items():
        ws_issues.column_dimensions[col_let].width = wid

    # Aggregate & Dataset-Level Findings (separated below and STRICTLY outside AutoFilter)
    if aggregate_findings:
        agg_start_row = row_table_last_row + 3
        ws_issues.cell(row=agg_start_row, column=1, value="Aggregate & Dataset-Level Findings").font = section_font
        agg_header_row = agg_start_row + 1
        agg_headers = ["Dataset", "Category", "Severity", "Scope", "Findings Description", "Affected Count", "Affected %"]
        for c_idx, h in enumerate(agg_headers, 1):
            ws_issues.cell(row=agg_header_row, column=c_idx, value=h)
        _apply_header_style(ws_issues, agg_header_row, len(agg_headers), bg_color="334155")

        r_agg = agg_header_row + 1
        for agg_iss in aggregate_findings:
            ws_issues.cell(row=r_agg, column=1, value=agg_iss.get("dataset", "")).font = normal_font
            ws_issues.cell(row=r_agg, column=2, value=agg_iss.get("category", "")).font = normal_font
            cell_sev = ws_issues.cell(row=r_agg, column=3, value=(agg_iss.get("severity") or "Info").upper())
            cell_sev.font = bold_font
            cell_sev.alignment = Alignment(horizontal="center", vertical="center")
            ws_issues.cell(row=r_agg, column=4, value=agg_iss.get("column", "")).font = normal_font
            ws_issues.cell(row=r_agg, column=5, value=agg_iss.get("issue_type", "")).font = normal_font
            
            c_cnt = ws_issues.cell(row=r_agg, column=6, value=agg_iss.get("affected_count", 0))
            c_cnt.font = bold_font
            c_cnt.alignment = Alignment(horizontal="right", vertical="center")
            
            pct = agg_iss.get("affected_pct", 0.0)
            c_pct = ws_issues.cell(row=r_agg, column=7, value=f"{pct:.1f}%" if pct > 0 else "-")
            c_pct.font = normal_font
            c_pct.alignment = Alignment(horizontal="right", vertical="center")
            
            for c in range(1, len(agg_headers) + 1):
                ws_issues.cell(row=r_agg, column=c).border = THIN_BORDER
            r_agg += 1

    # =======================================================================
    # Sheet 5: Quality Dimensions
    # =======================================================================
    if result.score and result.score.dimensions:
        ws_dims = wb.create_sheet(title="Quality Dimensions")
        dim_headers = ["Dimension", "Score (/100)", "Weight (%)", "Weighted Score", "Factor Explanation"]
        for c_idx, h in enumerate(dim_headers, 1):
            ws_dims.cell(row=1, column=c_idx, value=h)
        _apply_header_style(ws_dims, 1, len(dim_headers), bg_color="1E3A8A")

        for r_idx, dim in enumerate(result.score.dimensions, 2):
            ws_dims.cell(row=r_idx, column=1, value=dim.name).font = normal_font
            ws_dims.cell(row=r_idx, column=2, value=round(dim.score, 1)).font = normal_font
            ws_dims.cell(row=r_idx, column=3, value=f"{round(dim.weight * 100, 1)}%").font = normal_font
            ws_dims.cell(row=r_idx, column=4, value=round(dim.weighted, 2)).font = normal_font
            ws_dims.cell(row=r_idx, column=5, value=dim.explanation or "").font = normal_font
            for c in range(1, 6):
                ws_dims.cell(row=r_idx, column=c).border = THIN_BORDER

        _auto_fit_columns(ws_dims, max_width=80)

    # =======================================================================
    # Sheet 6: Relationships
    # =======================================================================
    if result.relationship_results:
        ws_rel = wb.create_sheet(title="Relationships")
        rel_headers = [
            "Relationship Detected", "Origin", "Child Dataset", "Child Key", "Parent Dataset", "Parent Key",
            "Integrity Status", "Child Records", "Invalid References", "Invalid Reference Rate", "Severity", "Invalid Reference Details"
        ]
        for c_idx, h in enumerate(rel_headers, 1):
            ws_rel.cell(row=1, column=c_idx, value=h)
        _apply_header_style(ws_rel, 1, len(rel_headers), bg_color="7C3AED")

        for r_idx, rel in enumerate(result.relationship_results, 2):
            origin_str = rel.origin_display
            status_str = "PASSED" if rel.orphan_count == 0 else "FAILED"
            sev_str = (rel.severity.value if hasattr(rel.severity, "value") else str(rel.severity)).upper()
            
            p_key = ", ".join(rel.parent_key) if isinstance(rel.parent_key, list) else str(rel.parent_key)
            c_key = ", ".join(rel.child_key) if isinstance(rel.child_key, list) else str(rel.child_key)
            
            if rel.orphan_count > 0:
                orphan_summary_text = f"{rel.orphan_count} orphan records (see Orphan Details table below)"
            else:
                orphan_summary_text = "All references valid"

            ws_rel.cell(row=r_idx, column=1, value="YES").font = bold_font
            ws_rel.cell(row=r_idx, column=2, value=origin_str).font = normal_font
            ws_rel.cell(row=r_idx, column=3, value=rel.child_dataset).font = normal_font
            ws_rel.cell(row=r_idx, column=4, value=c_key).font = normal_font
            ws_rel.cell(row=r_idx, column=5, value=rel.parent_dataset).font = normal_font
            ws_rel.cell(row=r_idx, column=6, value=p_key).font = normal_font
            
            cell_stat = ws_rel.cell(row=r_idx, column=7, value=status_str)
            cell_stat.font = bold_font
            cell_stat.alignment = Alignment(horizontal="center", vertical="center")

            cell_tot = ws_rel.cell(row=r_idx, column=8, value=rel.total_child_records)
            cell_tot.font = normal_font
            cell_tot.alignment = Alignment(horizontal="right", vertical="center")

            cell_orph = ws_rel.cell(row=r_idx, column=9, value=rel.orphan_count)
            cell_orph.font = bold_font
            cell_orph.alignment = Alignment(horizontal="right", vertical="center")

            cell_rate = ws_rel.cell(row=r_idx, column=10, value=f"{rel.orphan_pct:.1f}%")
            cell_rate.font = normal_font
            cell_rate.alignment = Alignment(horizontal="right", vertical="center")

            cell_sev = ws_rel.cell(row=r_idx, column=11, value=sev_str)
            cell_sev.font = bold_font
            cell_sev.alignment = Alignment(horizontal="center", vertical="center")

            cell_ex = ws_rel.cell(row=r_idx, column=12, value=orphan_summary_text)
            cell_ex.font = normal_font
            cell_ex.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

            for c in range(1, 13):
                ws_rel.cell(row=r_idx, column=c).border = THIN_BORDER

        # Table 2: Orphan Record Details (1 Displayed Orphan Record = 1 Row)
        total_orphans = sum(r.orphan_count for r in result.relationship_results)
        total_samples = sum(len(r.sample_orphan_records) for r in result.relationship_results)
        if total_orphans > 0:
            last_rel_row = len(result.relationship_results) + 1
            curr_r = last_rel_row + 3
            ws_rel.cell(
                row=curr_r,
                column=1,
                value=f"Orphan Reference Details (Showing {total_samples} of {total_orphans} orphan records)"
            ).font = section_font
            curr_r += 1

            orphan_headers = [
                "Row", "Child Dataset", "Child Key", "Actual Orphan Value",
                "Parent Dataset", "Parent Key", "Issue"
            ]
            for c_idx, h in enumerate(orphan_headers, 1):
                ws_rel.cell(row=curr_r, column=c_idx, value=h)
            _apply_header_style(ws_rel, curr_r, len(orphan_headers), bg_color="7C3AED")
            curr_r += 1

            for rel in result.relationship_results:
                if not rel.sample_orphan_records:
                    continue
                p_key = ", ".join(rel.parent_key) if isinstance(rel.parent_key, list) else str(rel.parent_key)
                c_key = ", ".join(rel.child_key) if isinstance(rel.child_key, list) else str(rel.child_key)
                for s in rel.sample_orphan_records:
                    r_num = s.get("row_number")
                    val = s.get("key_value")

                    c_r = ws_rel.cell(row=curr_r, column=1, value=r_num)
                    c_r.font = normal_font
                    c_r.alignment = Alignment(horizontal="center", vertical="center")

                    ws_rel.cell(row=curr_r, column=2, value=rel.child_dataset).font = normal_font
                    ws_rel.cell(row=curr_r, column=3, value=c_key).font = normal_font
                    
                    val_str = "NULL" if val is None else str(val)
                    ws_rel.cell(row=curr_r, column=4, value=val_str).font = normal_font
                    
                    ws_rel.cell(row=curr_r, column=5, value=rel.parent_dataset).font = normal_font
                    ws_rel.cell(row=curr_r, column=6, value=p_key).font = normal_font
                    ws_rel.cell(row=curr_r, column=7, value=f"Missing in {rel.parent_dataset}").font = normal_font

                    for c in range(1, len(orphan_headers) + 1):
                        ws_rel.cell(row=curr_r, column=c).border = THIN_BORDER
                    curr_r += 1

        _auto_fit_columns(ws_rel, max_width=80)

    # =======================================================================
    # Sheet 7: Recommendations
    # =======================================================================
    ws_recs = wb.create_sheet(title="Recommendations")
    rec_headers = ["Priority / Severity", "Title", "Description", "Dataset", "Affected Columns"]
    for c_idx, h in enumerate(rec_headers, 1):
        ws_recs.cell(row=1, column=c_idx, value=h)
    _apply_header_style(ws_recs, 1, len(rec_headers), bg_color="059669")

    if result.recommendations:
        for r_idx, rec in enumerate(result.recommendations, 2):
            sev_str = (rec.severity.value if hasattr(rec.severity, "value") else str(rec.severity)).upper()
            cell_sev = ws_recs.cell(row=r_idx, column=1, value=sev_str)
            cell_sev.font = bold_font
            cell_sev.alignment = Alignment(horizontal="center", vertical="center")

            ws_recs.cell(row=r_idx, column=2, value=rec.title).font = bold_font
            
            cell_desc = ws_recs.cell(row=r_idx, column=3, value=rec.description)
            cell_desc.font = normal_font
            cell_desc.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

            ws_recs.cell(row=r_idx, column=4, value=rec.dataset_name).font = normal_font
            ws_recs.cell(row=r_idx, column=5, value=", ".join(rec.affected_columns)).font = normal_font
            for c in range(1, 6):
                ws_recs.cell(row=r_idx, column=c).border = THIN_BORDER
    else:
        ws_recs.cell(row=2, column=1, value="No recommendations required — dataset is clean.").font = normal_font

    _auto_fit_columns(ws_recs, max_width=80)

    wb.save(out_p)
    return out_p
