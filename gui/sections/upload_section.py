"""
gui/sections/upload_section.py
Section B — Dataset Upload widget for the V2 single-page layout.

Handles CSV and multi-sheet Excel loading. Emits `datasets_changed`
to the MainWindow. No navigation signals.
"""
from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QListWidgetItem, QInputDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Signal, Qt
import pandas as pd

from core.ingestion.loader import load_file, get_excel_sheets
from gui.sections.section_helpers import make_section_card, make_section_header


class UploadSection(QWidget):
    """Dataset upload and quick-preview section."""

    datasets_changed = Signal(list)  # list[tuple[str, DataFrame]]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loaded_datasets: list[tuple[str, pd.DataFrame]] = []
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card, layout = make_section_card()
        layout.addWidget(
            make_section_header(
                "Dataset Upload",
                subtitle="Import CSV or multi-sheet Excel workbooks",
                accent_color="#2563eb",
            )
        )

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(20, 16, 20, 20)
        b_layout.setSpacing(14)

        # Action Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_csv = QPushButton("➕  Add CSV File")
        self._btn_csv.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: #ffffff;
                padding: 7px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        self._btn_csv.clicked.connect(self._add_csv)

        self._btn_excel = QPushButton("➕  Add Excel Workbook")
        self._btn_excel.setStyleSheet("""
            QPushButton {
                background: #059669;
                color: #ffffff;
                padding: 7px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover { background: #047857; }
        """)
        self._btn_excel.clicked.connect(self._add_excel)

        self._btn_remove = QPushButton("🗑️  Remove Selected")
        self._btn_remove.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                color: #dc2626;
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #fecaca;
            }
            QPushButton:hover { background: #fee2e2; border-color: #fca5a5; }
        """)
        self._btn_remove.clicked.connect(self._remove_selected)

        btn_row.addWidget(self._btn_csv)
        btn_row.addWidget(self._btn_excel)
        btn_row.addWidget(self._btn_remove)
        btn_row.addStretch()
        b_layout.addLayout(btn_row)

        # Content split: Dataset list on left, Preview on right
        split = QHBoxLayout()
        split.setSpacing(18)

        # Left: dataset list
        left = QVBoxLayout()
        left.setSpacing(6)
        list_lbl = QLabel("Loaded Datasets")
        list_lbl.setStyleSheet(
            "font-weight: 600; color: #334155; font-size: 12px; background: transparent;"
        )
        self._list = QListWidget()
        self._list.setMinimumHeight(130)
        self._list.setMaximumHeight(160)
        self._list.setStyleSheet("""
            QListWidget {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px;
                color: #1e293b;
            }
            QListWidget::item {
                padding: 7px 10px;
                border-radius: 4px;
                color: #1e293b;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:selected {
                background: #e0f2fe;
                color: #0369a1;
                font-weight: 600;
            }
        """)
        self._list.currentRowChanged.connect(self._on_selected)
        left.addWidget(list_lbl)
        left.addWidget(self._list)
        split.addLayout(left, 1)

        # Right: preview table
        right = QVBoxLayout()
        right.setSpacing(6)
        prev_lbl = QLabel("Dataset Preview  (First 10 Rows)")
        prev_lbl.setStyleSheet(
            "font-weight: 600; color: #334155; font-size: 12px; background: transparent;"
        )
        self._preview = QTableWidget()
        self._preview.setMinimumHeight(130)
        self._preview.setMaximumHeight(160)
        self._preview.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                gridline-color: #f1f5f9;
            }
            QTableWidget::item {
                padding: 4px 8px;
                color: #334155;
            }
        """)
        right.addWidget(prev_lbl)
        right.addWidget(self._preview)
        split.addLayout(right, 2)

        b_layout.addLayout(split)
        layout.addWidget(body)
        outer.addWidget(card)

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    def _add_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV Dataset", "", "CSV Files (*.csv)"
        )
        if path:
            try:
                df = load_file(path)
                self._add_entry(Path(path).stem, df)
            except Exception as exc:
                QMessageBox.critical(self, "Load Error", f"Failed to load CSV:\n{exc}")

    def _add_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Excel Dataset", "", "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            sheets = get_excel_sheets(path)
            sel = sheets[0]
            if len(sheets) > 1:
                s, ok = QInputDialog.getItem(
                    self, "Select Sheet",
                    "Workbook has multiple sheets — choose one:",
                    sheets, 0, False,
                )
                if ok and s:
                    sel = s
                else:
                    return
            df = load_file(path, sheet_name=sel)
            self._add_entry(f"{Path(path).stem}_{sel}", df)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to load Excel:\n{exc}")

    def _add_entry(self, name: str, df: pd.DataFrame):
        self.loaded_datasets.append((name, df))
        self._refresh()
        self.datasets_changed.emit(self.loaded_datasets)

    def _remove_selected(self):
        row = self._list.currentRow()
        if 0 <= row < len(self.loaded_datasets):
            self.loaded_datasets.pop(row)
            self._refresh()
            self.datasets_changed.emit(self.loaded_datasets)

    def _refresh(self):
        self._list.clear()
        for idx, (name, df) in enumerate(self.loaded_datasets):
            prefix = "★ [PRIMARY] " if idx == 0 else f"🔗 [DATASET #{idx + 1}] "
            self._list.addItem(
                QListWidgetItem(f"{prefix}{name}  ({len(df):,} rows, {len(df.columns)} cols)")
            )
        if self.loaded_datasets:
            self._list.setCurrentRow(len(self.loaded_datasets) - 1)
        else:
            self._preview.clear()
            self._preview.setRowCount(0)
            self._preview.setColumnCount(0)

    def _on_selected(self, row: int):
        if 0 <= row < len(self.loaded_datasets):
            _, df = self.loaded_datasets[row]
            self._populate_preview(df)

    def _populate_preview(self, df: pd.DataFrame):
        preview = df.head(10)
        self._preview.clear()
        self._preview.setRowCount(len(preview))
        self._preview.setColumnCount(len(df.columns))
        self._preview.setHorizontalHeaderLabels(list(df.columns))
        for r in range(len(preview)):
            for c in range(len(df.columns)):
                self._preview.setItem(r, c, QTableWidgetItem(str(preview.iloc[r, c])))
        self._preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    # ------------------------------------------------------------------
    # Public API for testing
    # ------------------------------------------------------------------

    def _add_dataset_entry(self, name: str, df: pd.DataFrame):
        """Public test API: directly add a dataset."""
        self._add_entry(name, df)

    @property
    def dataset_list(self):
        return self._list

    @property
    def preview_table(self):
        return self._preview
