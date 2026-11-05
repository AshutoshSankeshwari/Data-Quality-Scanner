"""
gui/sections/export_section.py
Section J — Export Reports (HTML, Excel, JSON).

Provides clean report generation options and a list of generated files
in a simplified, un-boxed layout.
"""
from __future__ import annotations
from pathlib import Path
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt

from core.models import AnalysisResult
from reports import generate_html, generate_excel, generate_json, get_report_filename
from gui.sections.section_helpers import make_section_card, make_section_header


class ExportSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: AnalysisResult | None = None
        self._datasets: list[tuple[str, Any]] | dict[str, Any] | None = None
        self._output_dir = str(Path("./reports").resolve())
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card, card_layout = make_section_card()
        card_layout.addWidget(
            make_section_header(
                "Export Reports",
                subtitle="Generate stakeholder deliverables and audit artifacts",
                accent_color="#0284c7",
            )
        )

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(20, 16, 20, 20)
        b_layout.setSpacing(14)

        # ── Formats Selection ─────────────────────────────────────────
        fmt_box = QVBoxLayout()
        fmt_box.setSpacing(6)
        fmt_lbl = QLabel("Report Formats")
        fmt_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #334155; background: transparent;"
        )
        fmt_box.addWidget(fmt_lbl)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(20)
        self._cb_html  = QCheckBox("HTML Report")
        self._cb_excel = QCheckBox("Excel Workbook (.xlsx)")
        self._cb_json  = QCheckBox("JSON (machine-readable)")
        for cb in (self._cb_html, self._cb_excel, self._cb_json):
            cb.setChecked(True)
            cb.setStyleSheet("color: #1e293b; font-size: 12px; font-weight: 500;")
            fmt_row.addWidget(cb)
        fmt_row.addStretch()
        fmt_box.addLayout(fmt_row)
        b_layout.addLayout(fmt_box)

        # ── Output Directory ──────────────────────────────────────────
        dir_box = QVBoxLayout()
        dir_box.setSpacing(6)
        dir_lbl = QLabel("Output Directory")
        dir_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #334155; background: transparent;"
        )
        dir_box.addWidget(dir_lbl)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(10)
        self._dir_display = QLabel(self._output_dir)
        self._dir_display.setStyleSheet("""
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            padding: 7px 12px;
            border-radius: 6px;
            color: #334155;
            font-size: 12px;
        """)
        btn_browse = QPushButton("Browse…")
        btn_browse.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                padding: 7px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        btn_browse.clicked.connect(self._choose_dir)
        dir_row.addWidget(self._dir_display, 1)
        dir_row.addWidget(btn_browse)
        dir_box.addLayout(dir_row)
        b_layout.addLayout(dir_box)

        # ── Generate Button ───────────────────────────────────────────
        self._btn_export = QPushButton("📥  Generate & Save Reports")
        self._btn_export.setMinimumHeight(40)
        self._btn_export.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                padding: 8px 22px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        self._btn_export.clicked.connect(self._generate_reports)
        b_layout.addWidget(self._btn_export, alignment=Qt.AlignLeft)

        # ── Generated Files List ──────────────────────────────────────
        files_box = QVBoxLayout()
        files_box.setSpacing(6)
        files_lbl = QLabel("Generated Reports")
        files_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #334155; background: transparent;"
        )
        files_box.addWidget(files_lbl)

        self._file_list = QListWidget()
        self._file_list.setMinimumHeight(80)
        self._file_list.setMaximumHeight(130)
        self._file_list.setStyleSheet("""
            QListWidget {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px;
                color: #1e293b;
            }
            QListWidget::item {
                padding: 6px 10px;
                color: #1e293b;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:hover {
                background: #e0f2fe;
            }
        """)
        self._file_list.itemDoubleClicked.connect(self._open_file)
        files_box.addWidget(self._file_list)
        b_layout.addLayout(files_box)

        card_layout.addWidget(body)
        outer.addWidget(self._card)

    def set_result(
        self,
        result: AnalysisResult,
        datasets: list[tuple[str, Any]] | dict[str, Any] | None = None,
    ):
        self._result = result
        self._datasets = datasets
        self._file_list.clear()

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory", self._output_dir)
        if d:
            self._output_dir = str(Path(d).resolve())
            self._dir_display.setText(self._output_dir)

    def _generate_reports(self):
        if not self._result:
            QMessageBox.warning(self, "No Results", "Please run analysis before generating reports.")
            return

        out = Path(self._output_dir)
        out.mkdir(parents=True, exist_ok=True)

        self._file_list.clear()
        created = []

        try:
            if self._cb_html.isChecked():
                filename = get_report_filename(self._result, "html")
                p = out / filename
                generate_html(self._result, p, datasets=self._datasets)
                created.append(p)
            if self._cb_excel.isChecked():
                filename = get_report_filename(self._result, "xlsx")
                p = out / filename
                generate_excel(self._result, p, datasets=self._datasets)
                created.append(p)
            if self._cb_json.isChecked():
                filename = get_report_filename(self._result, "json")
                p = out / filename
                generate_json(self._result, p, datasets=self._datasets)
                created.append(p)

            for f in created:
                self._file_list.addItem(
                    QListWidgetItem(f"📄 {f.name}  —  {f}  (Double-click to open)")
                )
            QMessageBox.information(
                self, "Export Complete",
                f"Successfully generated {len(created)} report(s) in:\n{self._output_dir}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to generate reports:\n{exc}")

    def _open_file(self, item: QListWidgetItem):
        txt = item.text()
        if "—" in txt:
            parts = txt.split("—")
            if len(parts) >= 2:
                path_str = parts[1].strip().split("(")[0].strip()
                if os.path.exists(path_str):
                    os.startfile(path_str)
