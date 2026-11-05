"""
gui/sections/dataset_info_section.py
Section C — Compact Dataset Information rows.

Displays essential dataset metadata (name, record count, column count,
file type, and analysis status) as clean horizontal rows without
heavy nested cards or column profiling tables.
"""
from __future__ import annotations
import pandas as pd

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)

from gui.sections.section_helpers import make_section_card, make_section_header


class DatasetInfoSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dataset_rows: list[_DatasetRow] = []
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card, self._card_layout = make_section_card()
        self._card_layout.addWidget(
            make_section_header(
                "Dataset Information",
                subtitle="Loaded dataset metadata and analysis status",
                accent_color="#334155",
            )
        )

        self._rows_widget = QWidget()
        self._rows_widget.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(20, 10, 20, 12)
        self._rows_layout.setSpacing(6)

        self._card_layout.addWidget(self._rows_widget)
        outer.addWidget(self._card)

    def update_datasets(self, datasets: list[tuple[str, pd.DataFrame]]):
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._dataset_rows.clear()

        for idx, (name, df) in enumerate(datasets):
            row = _DatasetRow(
                name=name,
                rows=len(df),
                cols=len(df.columns),
                is_primary=(idx == 0),
                status="Pending",
            )
            self._dataset_rows.append(row)
            self._rows_layout.addWidget(row)

    def set_status_all(self, status: str):
        for row in self._dataset_rows:
            row.set_status(status)


class _DatasetRow(QFrame):
    _STATUS_STYLES = {
        "Pending":    ("background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0;"),
        "Analysing…": ("background: #fef9c3; color: #854d0e; border: 1px solid #fde047;"),
        "Analysed ✓": ("background: #dcfce7; color: #166534; border: 1px solid #bbf7d0;"),
        "Error":      ("background: #fee2e2; color: #991b1b; border: 1px solid #fecaca;"),
    }

    def __init__(self, name: str, rows: int, cols: int,
                 is_primary: bool, status: str, parent=None):
        super().__init__(parent)

        self.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #edf2f7;
                border-radius: 6px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(16)

        # Primary / Secondary Badge
        tag = "★ Primary" if is_primary else "🔗 Secondary"
        tag_bg = "#eff6ff" if is_primary else "#f5f3ff"
        tag_fg = "#1d4ed8" if is_primary else "#6d28d9"
        tag_border = "#bfdbfe" if is_primary else "#ddd6fe"

        tag_lbl = QLabel(tag)
        tag_lbl.setStyleSheet(f"""
            background: {tag_bg};
            color: {tag_fg};
            border: 1px solid {tag_border};
            font-size: 11px;
            font-weight: 600;
            border-radius: 4px;
            padding: 2px 8px;
        """)

        # Dataset Name
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #0f172a; background: transparent; border: none;"
        )

        # Separator dot
        dot = QLabel("·")
        dot.setStyleSheet("color: #cbd5e1; font-weight: bold; background: transparent; border: none;")

        # Records & Columns metadata
        stats_lbl = QLabel(f"<b>{rows:,}</b> records  ·  <b>{cols}</b> columns")
        stats_lbl.setStyleSheet(
            "color: #475569; font-size: 12px; background: transparent; border: none;"
        )

        # Status badge
        self._status_lbl = QLabel(status)
        style_css = self._STATUS_STYLES.get(status, self._STATUS_STYLES["Pending"])
        self._status_lbl.setStyleSheet(f"""
            {style_css}
            font-size: 11px;
            font-weight: 600;
            border-radius: 4px;
            padding: 2px 8px;
        """)

        layout.addWidget(tag_lbl)
        layout.addWidget(name_lbl)
        layout.addWidget(dot)
        layout.addWidget(stats_lbl)
        layout.addStretch()
        layout.addWidget(self._status_lbl)

    def set_status(self, status: str):
        style_css = self._STATUS_STYLES.get(status, self._STATUS_STYLES["Pending"])
        self._status_lbl.setText(status)
        self._status_lbl.setStyleSheet(f"""
            {style_css}
            font-size: 11px;
            font-weight: 600;
            border-radius: 4px;
            padding: 2px 8px;
        """)
