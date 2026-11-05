"""
gui/sections/history_section.py
Section K — Scan History & SQLite Persistence.

Displays historical scan runs retrieved from SQLite.
Supports clicking/loading past scans to inspect findings and re-export reports.
"""
from __future__ import annotations
from typing import Optional, Any
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
)
from PySide6.QtCore import Qt, Signal

from db.repository import ScanRepository
from core.models import format_display_timestamp
from gui.sections.section_helpers import make_section_card, make_section_header


class HistorySection(QWidget):
    """Scan history section backed by SQLite persistence."""

    scan_loaded = Signal(object)  # Emits AnalysisResult

    def __init__(self, db_path: Optional[str | Path] = None, parent=None):
        super().__init__(parent)
        self.repo = ScanRepository(db_path)
        self._scans: list[dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card, card_layout = make_section_card()
        card_layout.addWidget(
            make_section_header(
                "Scan History",
                subtitle="Historical quality assessments stored in SQLite",
                accent_color="#475569",
            )
        )

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        self._b_layout = QVBoxLayout(body)
        self._b_layout.setContentsMargins(20, 14, 20, 20)
        self._b_layout.setSpacing(10)

        # ── Placeholder for empty history ─────────────────────────────
        self._placeholder = QLabel(
            "📂  <b>No scan history yet.</b><br>"
            "<span style='color: #64748b; font-size: 12px;'>"
            "Completed data quality scans are automatically persisted to SQLite and will appear here."
            "</span>"
        )
        self._placeholder.setStyleSheet("""
            color: #334155;
            font-size: 13px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 14px 18px;
        """)
        self._placeholder.setWordWrap(True)
        self._b_layout.addWidget(self._placeholder)

        # ── History Table (hidden when empty) ─────────────────────────
        self._table = QTableWidget()
        self._table.setMinimumHeight(140)
        self._table.setMaximumHeight(220)
        self._table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                gridline-color: #f1f5f9;
            }
            QTableWidget::item {
                padding: 6px 10px;
                color: #334155;
            }
        """)
        self._table.verticalHeader().setVisible(False)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self._table.setVisible(False)
        self._b_layout.addWidget(self._table)

        # Bottom row: Refresh button + double-click hint
        self._footer_row = QHBoxLayout()
        self._footer_hint = QLabel(
            "💡  Double-click a historical scan to load its findings into the dashboard."
        )
        self._footer_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        self._footer_hint.setVisible(False)

        self._btn_refresh = QPushButton("🔄 Refresh History")
        self._btn_refresh.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        self._btn_refresh.clicked.connect(self.refresh_history)

        self._footer_row.addWidget(self._footer_hint)
        self._footer_row.addStretch()
        self._footer_row.addWidget(self._btn_refresh)
        self._b_layout.addLayout(self._footer_row)

        card_layout.addWidget(body)
        outer.addWidget(self._card)

        # Load initial history from SQLite
        self.refresh_history()

    def refresh_history(self):
        """Query SQLite and populate history table."""
        self._scans = self.repo.list_scans(limit=30)

        if not self._scans:
            self._placeholder.setVisible(True)
            self._table.setVisible(False)
            self._footer_hint.setVisible(False)
            return

        self._placeholder.setVisible(False)
        self._table.setVisible(True)
        self._footer_hint.setVisible(True)

        headers = [
            "Scan Date & Time", "Primary Dataset", "Datasets",
            "Readiness Score", "Category", "Issues Found", "Action",
        ]
        self._table.clear()
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(self._scans))

        for r, scan in enumerate(self._scans):
            timestamp = scan.get("started_at", "—")
            display_ts = format_display_timestamp(timestamp)
            primary_ds = scan.get("primary_dataset") or scan.get("all_datasets") or "—"
            ds_count = str(scan.get("dataset_count", 1))
            score_val = scan.get("overall_score")
            score_str = f"{score_val:.1f}" if score_val is not None else "—"
            category_str = scan.get("readiness_category") or "—"
            issues_str = str(scan.get("total_issues", 0))

            self._table.setItem(r, 0, QTableWidgetItem(display_ts))
            self._table.setItem(r, 1, QTableWidgetItem(primary_ds))
            self._table.setItem(r, 2, QTableWidgetItem(ds_count))
            self._table.setItem(r, 3, QTableWidgetItem(score_str))
            self._table.setItem(r, 4, QTableWidgetItem(category_str))
            self._table.setItem(r, 5, QTableWidgetItem(issues_str))

            btn_load = QPushButton("🔍 View Findings")
            btn_load.setStyleSheet("""
                QPushButton {
                    background: #eff6ff;
                    color: #1d4ed8;
                    border: 1px solid #bfdbfe;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover { background: #dbeafe; }
            """)
            scan_id = scan["id"]
            btn_load.clicked.connect(lambda checked=False, sid=scan_id: self._load_scan_by_id(sid))
            self._table.setCellWidget(r, 6, btn_load)

        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)

    def _on_row_double_clicked(self, row: int, column: int):
        if 0 <= row < len(self._scans):
            scan_id = self._scans[row]["id"]
            self._load_scan_by_id(scan_id)

    def _load_scan_by_id(self, scan_id: int):
        result = self.repo.get_scan_result(scan_id)
        if result:
            self.scan_loaded.emit(result)
