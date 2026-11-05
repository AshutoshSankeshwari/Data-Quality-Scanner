"""
gui/sections/dimensions_section.py
Section F — Quality Dimension Scores.

Presents the 6 quality dimensions as clean dashboard metric items
with horizontal progress indicators, scores, weights, and explanations,
avoiding heavy nested box-in-box cards.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QProgressBar,
)
from PySide6.QtCore import Qt

from core.models import AnalysisResult, DimensionScore
from gui.sections.section_helpers import make_section_card, make_section_header


DIMENSION_DESCRIPTIONS = {
    "Completeness": "Measures how many required values are populated.",
    "Uniqueness": "Measures how free the data is from duplicate records.",
    "Validity": "Measures how many values conform to expected formats.",
    "Consistency": "Measures how uniform naming/patterns are within a column.",
    "Integrity": "Measures whether related records reference valid parents.",
    "Cleanliness": "Measures freedom from whitespace and formatting noise.",
}


class DimensionsSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card, self._card_layout = make_section_card()
        self._card_layout.addWidget(
            make_section_header(
                "Quality Dimension Scores",
                subtitle="Independent diagnostic scores across 6 quality dimensions",
                accent_color="#4338ca",
            )
        )

        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._body)
        self._grid.setContentsMargins(20, 16, 20, 20)
        self._grid.setHorizontalSpacing(24)
        self._grid.setVerticalSpacing(16)

        self._card_layout.addWidget(self._body)
        outer.addWidget(self._card)

    def set_result(self, result: AnalysisResult):
        # Clear existing items
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not result.score:
            return

        for idx, dim in enumerate(result.score.dimensions):
            item_widget = self._make_dim_item(dim)
            self._grid.addWidget(item_widget, idx // 2, idx % 2)

    def _make_dim_item(self, dim: DimensionScore) -> QWidget:
        """Create a clean dashboard metric row for a dimension."""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #edf2f7;
                border-radius: 6px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        # Semantic color based on score
        if dim.score >= 80:
            score_color = "#10b981"  # green
        elif dim.score >= 50:
            score_color = "#f59e0b"  # amber
        else:
            score_color = "#ef4444"  # red

        # ── Top row: Name + Score ──────────────────────────────────────
        top_row = QHBoxLayout()
        name_lbl = QLabel(dim.name)
        name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #0f172a; background: transparent; border: none;"
        )

        score_lbl = QLabel(
            f"<span style='font-size: 14px; font-weight: 800; color: {score_color};'>{dim.score:.1f}</span>"
            f"<span style='font-size: 11px; font-weight: 500; color: #94a3b8;'> / 100</span>"
        )
        score_lbl.setTextFormat(Qt.RichText)
        score_lbl.setStyleSheet("background: transparent; border: none;")

        top_row.addWidget(name_lbl)
        top_row.addStretch()
        top_row.addWidget(score_lbl)
        layout.addLayout(top_row)

        # ── Middle row: Clean Progress Bar ────────────────────────────
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(dim.score))
        pbar.setFixedHeight(6)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background: #e2e8f0;
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {score_color};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(pbar)

        # ── Bottom row: Meaningful Description ─────────────────────────
        desc_text = dim.explanation or DIMENSION_DESCRIPTIONS.get(dim.name, "Dimension quality measurement.")
        desc_lbl = QLabel(desc_text)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "font-size: 11px; color: #64748b; background: transparent; border: none; line-height: 1.3;"
        )
        layout.addWidget(desc_lbl)

        return widget
