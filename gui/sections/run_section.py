"""
gui/sections/run_section.py
Section D — Run Analysis button, progress bar, and status.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar,
    QLabel, QFrame, QSizePolicy,
)
from PySide6.QtCore import Signal

from core.models import format_display_timestamp


class RunSection(QWidget):
    run_clicked = Signal()
    clear_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        card = QFrame()
        card.setObjectName("runCard")
        card.setStyleSheet("""
            QFrame#runCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px 20px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_run = QPushButton("Run Data Quality Analysis")
        self.btn_run.setEnabled(False)
        self.btn_run.setMinimumHeight(44)
        self.btn_run.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background: #059669;
                color: #ffffff;
                font-weight: 700;
                font-size: 14px;
                padding: 10px 24px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover   { background: #047857; }
            QPushButton:pressed { background: #065f46; }
            QPushButton:disabled {
                background: #e2e8f0;
                color: #94a3b8;
            }
        """)
        self.btn_run.clicked.connect(self.run_clicked)

        self.btn_clear = QPushButton("✕  Clear Results")
        self.btn_clear.setVisible(False)
        self.btn_clear.setMinimumHeight(44)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                color: #dc2626;
                font-weight: 600;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                border: 1px solid #fecaca;
            }
            QPushButton:hover { background: #fee2e2; border-color: #fca5a5; }
        """)
        self.btn_clear.clicked.connect(self.clear_clicked)

        btn_row.addWidget(self.btn_run, 4)
        btn_row.addWidget(self.btn_clear, 1)
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #e2e8f0;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #059669
                );
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500;")
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

    def set_datasets_ready(self, ready: bool):
        self.btn_run.setEnabled(ready)

    def set_running(self, running: bool, timestamp: str | Any = None):
        if running:
            self.btn_run.setEnabled(False)
            self.btn_run.setText("⏳  Running Analysis…")
            self.btn_clear.setVisible(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.status_lbl.setText("Initialising analysis engine…")
            self.status_lbl.setVisible(True)
        else:
            self.btn_run.setEnabled(True)
            self.btn_run.setText("Run Data Quality Analysis")
            self.progress_bar.setValue(100)
            self.btn_clear.setVisible(True)
            if timestamp:
                self.status_lbl.setText(f"Analysis completed: {format_display_timestamp(timestamp)}")
                self.status_lbl.setVisible(True)

    def set_completed(self, timestamp: str | Any = None):
        """Display completed status and scan completion timestamp."""
        self.btn_run.setEnabled(True)
        self.btn_run.setText("Run Data Quality Analysis")
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(True)
        self.btn_clear.setVisible(True)
        if timestamp:
            self.status_lbl.setText(f"Analysis completed: {format_display_timestamp(timestamp)}")
            self.status_lbl.setVisible(True)

    def update_progress(self, message: str, pct: int):
        self.progress_bar.setValue(pct)
        self.status_lbl.setText(message)

    def reset(self):
        self.btn_clear.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.status_lbl.setVisible(False)
        self.btn_run.setText("Run Data Quality Analysis")
