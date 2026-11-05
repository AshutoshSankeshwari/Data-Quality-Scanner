"""
gui/sections/recommendations_section.py
Section I — Actionable, Prioritized Recommendations.

Renders prioritized data remediation actions as clean rows with
subtle left-side severity accents, without nested boxes.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PySide6.QtCore import Qt

from core.models import AnalysisResult, Recommendation, Severity
from gui.sections.section_helpers import make_section_card, make_section_header


_SEVERITY_META = {
    Severity.CRITICAL: ("#ef4444", "🔴", "CRITICAL", "#dc2626"),
    Severity.HIGH:     ("#f97316", "🟠", "HIGH",     "#ea580c"),
    Severity.MEDIUM:   ("#eab308", "🟡", "MEDIUM",   "#ca8a04"),
    Severity.LOW:      ("#0284c7", "🔵", "LOW",      "#0369a1"),
    Severity.INFO:     ("#64748b", "⚪", "INFO",     "#475569"),
}


class RecommendationsSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card, card_layout = make_section_card()
        card_layout.addWidget(
            make_section_header(
                "Recommendations",
                subtitle="Prioritized data cleansing and remediation actions",
                accent_color="#059669",
            )
        )

        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._b_layout = QVBoxLayout(self._body)
        self._b_layout.setContentsMargins(20, 14, 20, 20)
        self._b_layout.setSpacing(10)

        card_layout.addWidget(self._body)
        outer.addWidget(self._card)

    def set_result(self, result: AnalysisResult):
        # Clear existing
        while self._b_layout.count():
            item = self._b_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not result.recommendations:
            lbl = QLabel("🎉  No cleansing actions required — datasets satisfy all quality standards.")
            lbl.setStyleSheet("""
                color: #059669;
                font-size: 13px;
                font-weight: 600;
                background: #f0fdf4;
                border: 1px solid #bbf7d0;
                border-radius: 6px;
                padding: 14px 16px;
            """)
            lbl.setWordWrap(True)
            self._b_layout.addWidget(lbl)
            return

        for rec in result.recommendations:
            self._b_layout.addWidget(self._make_rec_row(rec))

    def _make_rec_row(self, rec: Recommendation) -> QFrame:
        accent_color, icon, tag_text, tag_fg = _SEVERITY_META.get(
            rec.severity, ("#64748b", "⚪", "INFO", "#475569")
        )

        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: #ffffff;
                border: 1px solid #edf2f7;
                border-left: 3px solid {accent_color};
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Header: Severity Tag + Title
        top = QHBoxLayout()
        top.setSpacing(8)

        tag = QLabel(f"{icon} <b>{tag_text}</b>")
        tag.setStyleSheet(
            f"color: {tag_fg}; font-size: 11px; font-weight: 700; background: transparent; border: none;"
        )
        top.addWidget(tag)

        title = QLabel(rec.title)
        title.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #0f172a; background: transparent; border: none;"
        )
        top.addWidget(title)
        top.addStretch()
        layout.addLayout(top)

        # Description
        desc = QLabel(rec.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            "font-size: 12px; color: #475569; background: transparent; border: none; line-height: 1.35;"
        )
        layout.addWidget(desc)

        # Metadata footer
        cols_str = ", ".join(rec.affected_columns) if rec.affected_columns else "—"
        meta = QLabel(
            f"Dataset: <b>{rec.dataset_name}</b>  ·  Field(s): <code>{cols_str}</code>"
        )
        meta.setStyleSheet(
            "font-size: 11px; color: #64748b; background: transparent; border: none; margin-top: 2px;"
        )
        layout.addWidget(meta)

        return row
