"""
gui/sections/issues_section.py
Section G — Quality Issues (searchable & filterable table).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt

from core.models import AnalysisResult, get_dimension_for_category
from gui.sections.section_helpers import make_section_card, make_section_header

_SEVERITY_COLORS = {
    "Critical": "#dc2626",
    "High":     "#ea580c",
    "Medium":   "#d97706",
    "Low":      "#0284c7",
    "Info":     "#64748b",
}
 

class IssuesSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_issues: list[dict] = []
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card, card_layout = make_section_card()
        card_layout.addWidget(
            make_section_header(
                "Quality Issues",
                subtitle="Filterable log of all detected rule violations",
                accent_color="#d97706",
            )
        )

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(20, 14, 20, 20)
        b_layout.setSpacing(12)

        # Filters Row
        f_row = QHBoxLayout()
        f_row.setSpacing(12)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search issues by keyword, column, dataset, or quality dimension…")
        self._search.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                color: #1e293b;
            }
            QLineEdit:focus { border-color: #2563eb; }
        """)
        self._search.textChanged.connect(self._apply_filters)
        f_row.addWidget(self._search, 3)

        self._sev_filter = QComboBox()
        self._sev_filter.addItems(["All Severities", "Critical", "High", "Medium", "Low", "Info"])
        self._sev_filter.currentIndexChanged.connect(self._apply_filters)
        f_row.addWidget(self._sev_filter, 1)

        self._cat_filter = QComboBox()
        self._cat_filter.addItems([
            "All Categories", "Duplicates", "Nulls/Blanks",
            "Mandatory Fields", "Dates", "Special Characters",
            "Patterns", "Relationships", "Whitespace",
        ])
        self._cat_filter.currentIndexChanged.connect(self._apply_filters)
        f_row.addWidget(self._cat_filter, 1)

        self._dim_filter = QComboBox()
        self._dim_filter.addItems([
            "All Dimensions", "Completeness", "Uniqueness",
            "Validity", "Consistency", "Integrity", "Cleanliness",
        ])
        self._dim_filter.currentIndexChanged.connect(self._apply_filters)
        f_row.addWidget(self._dim_filter, 1)

        b_layout.addLayout(f_row)

        # Count label
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500;")
        b_layout.addWidget(self._count_lbl)

        # Issues Table
        self._table = QTableWidget()
        self._table.setMinimumHeight(240)
        self._table.setMaximumHeight(340)
        self._table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                gridline-color: #f1f5f9;
            }
            QTableWidget::item {
                padding: 5px 8px;
                color: #334155;
            }
        """)
        b_layout.addWidget(self._table)

        card_layout.addWidget(body)
        outer.addWidget(self._card)

    def set_result(self, result: AnalysisResult):
        self._extract_issues(result)
        self._apply_filters()

    def _extract_issues(self, result: AnalysisResult):
        self._all_issues = []

        # Duplicates -> Uniqueness
        for dr in result.duplicate_results:
            if dr.full_row_duplicate_count > 0:
                self._all_issues.append({
                    "category": "Duplicates",
                    "dimension": get_dimension_for_category("Duplicates"),
                    "severity": dr.severity.value,
                    "dataset": dr.dataset_name,
                    "column": "ALL",
                    "details": f"{dr.full_row_duplicate_count} full-row duplicates ({dr.full_row_duplicate_pct:.1f}%)",
                })
            for kb in dr.key_based_results:
                if kb["duplicate_count"] > 0:
                    self._all_issues.append({
                        "category": "Duplicates",
                        "dimension": get_dimension_for_category("Duplicates"),
                        "severity": kb["severity"],
                        "dataset": dr.dataset_name,
                        "column": ", ".join(kb["key_columns"]),
                        "details": f"{kb['duplicate_count']} key-based duplicates ({kb['duplicate_pct']:.1f}%)",
                    })

        # Mandatory fields -> Completeness
        for mf in result.mandatory_field_results:
            if mf.failing_record_count > 0:
                missing_cols = [f["field"] for f in mf.per_field if f.get("missing_count", 0) > 0]
                self._all_issues.append({
                    "category": "Mandatory Fields",
                    "dimension": get_dimension_for_category("Mandatory Fields"),
                    "severity": mf.severity.value,
                    "dataset": mf.dataset_name,
                    "column": ", ".join(missing_cols),
                    "details": f"{mf.failing_record_count} records missing mandatory fields ({mf.failing_pct:.1f}%)",
                })

        # Dates -> Validity
        for dr in result.date_results:
            for c in dr.per_column:
                if c["invalid_count"] > 0 or c.get("has_inconsistency"):
                    parts = []
                    if c["invalid_count"] > 0:
                        parts.append(f"{c['invalid_count']} invalid dates")
                    if c.get("impossible_date_count", 0) > 0:
                        parts.append(f"{c['impossible_date_count']} impossible dates")
                    if c.get("has_inconsistency"):
                        parts.append(f"Multiple formats (dominant: {c.get('dominant_format')})")
                    self._all_issues.append({
                        "category": "Dates",
                        "dimension": get_dimension_for_category("Dates"),
                        "severity": c["severity"],
                        "dataset": dr.dataset_name,
                        "column": c["column"],
                        "details": " | ".join(parts),
                    })

        # Special chars -> Validity
        for sc in result.special_char_results:
            for c in sc.per_column:
                self._all_issues.append({
                    "category": "Special Characters",
                    "dimension": get_dimension_for_category("Special Characters"),
                    "severity": c["severity"],
                    "dataset": sc.dataset_name,
                    "column": c["column"],
                    "details": f"{c['violation_count']} violations for rule '{c['rule_name']}'",
                })

        # Relationships -> Integrity
        for rr in result.relationship_results:
            if rr.orphan_count > 0:
                self._all_issues.append({
                    "category": "Relationships",
                    "dimension": get_dimension_for_category("Relationships"),
                    "severity": rr.severity.value,
                    "dataset": rr.child_dataset,
                    "column": rr.child_key,
                    "details": f"{rr.orphan_count} orphan records ({rr.orphan_pct:.1f}%) → {rr.parent_dataset}",
                })

        # Whitespace -> Cleanliness
        for wr in result.whitespace_results:
            for c in wr.per_column:
                total_ws = c["leading_count"] + c["trailing_count"] + c["multi_internal_count"]
                if total_ws > 0:
                    sev = c.get("severity", wr.severity.value if hasattr(wr, "severity") and hasattr(wr.severity, "value") else "Low")
                    if hasattr(sev, "value"):
                        sev = sev.value
                    self._all_issues.append({
                        "category": "Whitespace",
                        "dimension": get_dimension_for_category("Whitespace"),
                        "severity": str(sev),
                        "dataset": wr.dataset_name,
                        "column": c["column"],
                        "details": f"Leading: {c['leading_count']}, Trailing: {c['trailing_count']}, Multi-internal: {c['multi_internal_count']}",
                    })

        # Patterns -> Consistency
        for pr in result.pattern_results:
            for c in pr.per_column:
                samples = c.get("sample_inconsistencies", [])
                if samples or c.get("has_case_inconsistency") or c.get("has_structural_inconsistency"):
                    dominant = c.get("dominant_pattern", "N/A")
                    sev = c.get("severity", pr.severity.value if hasattr(pr, "severity") and hasattr(pr.severity, "value") else "Low")
                    if hasattr(sev, "value"):
                        sev = sev.value
                    self._all_issues.append({
                        "category": "Patterns",
                        "dimension": get_dimension_for_category("Patterns"),
                        "severity": str(sev),
                        "dataset": pr.dataset_name,
                        "column": c["column"],
                        "details": f"{len(samples)} pattern inconsistencies (expected {dominant})",
                    })

        # Nulls -> Completeness
        for nr in result.null_blank_results:
            for c in nr.per_column:
                if c["null_count"] > 0 or c["blank_count"] > 0:
                    self._all_issues.append({
                        "category": "Nulls/Blanks",
                        "dimension": get_dimension_for_category("Nulls/Blanks"),
                        "severity": c.get("severity", "Low") if isinstance(c.get("severity"), str) else "Low",
                        "dataset": nr.dataset_name,
                        "column": c["column"],
                        "details": f"Nulls: {c['null_count']} ({c['null_pct']:.1f}%), Blanks: {c['blank_count']}",
                    })

    def _apply_filters(self):
        query = self._search.text().lower().strip()
        sev = self._sev_filter.currentText()
        cat = self._cat_filter.currentText()
        dim = self._dim_filter.currentText()

        filtered = []
        for iss in self._all_issues:
            if sev != "All Severities" and iss["severity"] != sev:
                continue
            if cat != "All Categories" and iss["category"] != cat:
                continue
            if dim != "All Dimensions" and iss.get("dimension") != dim:
                continue
            if query:
                combined = f"{iss['category']} {iss.get('dimension', '')} {iss['severity']} {iss['dataset']} {iss['column']} {iss['details']}".lower()
                if query not in combined:
                    continue
            filtered.append(iss)

        self._count_lbl.setText(f"{len(filtered)} issue(s) found")

        headers = ["Severity", "Category", "Dataset", "Affected Field(s)", "Quality Dimension", "Issue Description"]
        self._table.clear()
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(filtered))

        for r, iss in enumerate(filtered):
            sev_val = iss["severity"]
            sev_item = QTableWidgetItem(sev_val)
            color_hex = _SEVERITY_COLORS.get(sev_val, "#475569")
            sev_item.setForeground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(color_hex))

            self._table.setItem(r, 0, sev_item)
            self._table.setItem(r, 1, QTableWidgetItem(iss["category"]))
            self._table.setItem(r, 2, QTableWidgetItem(iss["dataset"]))
            self._table.setItem(r, 3, QTableWidgetItem(iss["column"]))
            self._table.setItem(r, 4, QTableWidgetItem(iss.get("dimension", "")))
            self._table.setItem(r, 5, QTableWidgetItem(iss["details"]))

        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
