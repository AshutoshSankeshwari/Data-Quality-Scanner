"""
gui/main_window.py
Data Quality Scanner v2 — Single-page scrollable dashboard.

No sidebar. No QStackedWidget. No interactive configuration.
All sections are rendered sequentially in one QScrollArea.
Results appear in-place after analysis completes and are persisted to SQLite.
"""
from __future__ import annotations
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QScrollArea, QMessageBox, QDialog, QFileDialog,
)
from PySide6.QtCore import Qt
import pandas as pd

from core.models import AnalysisResult
from rules.config_loader import (
    build_analysis_config_from_v2,
    get_config_hash,
    load_branding_config,
    get_project_root,
)
from rules.admin_config_manager import import_branding_logo
from gui.workers import AnalysisWorker
from gui.mandatory_confirmation_dialog import InferredMandatoryConfirmationDialog
from db.repository import ScanRepository

from gui.sections.upload_section import UploadSection
from gui.sections.dataset_info_section import DatasetInfoSection
from gui.sections.run_section import RunSection
from gui.sections.score_section import ScoreSection
from gui.sections.dimensions_section import DimensionsSection
from gui.sections.issues_section import IssuesSection
from gui.sections.relationships_section import RelationshipsSection
from gui.sections.recommendations_section import RecommendationsSection
from gui.sections.export_section import ExportSection
from gui.sections.history_section import HistorySection
from gui.sections.config_info_section import ConfigInfoSection
from gui.sections.header_widget import HeaderWidget

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


class MainWindow(QMainWindow):
    """Single-page scrollable Data Quality Scanner (V2) with SQLite persistence."""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__()
        self.setWindowTitle("Data Quality Scanner v2.0")
        self.resize(1280, 900)
        self.setMinimumSize(1024, 700)

        self.db_path = db_path
        self.repo = ScanRepository(db_path)

        self.current_datasets: list[tuple[str, pd.DataFrame]] = []
        self.current_result: AnalysisResult | None = None
        self.worker: AnalysisWorker | None = None

        self._init_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Fixed header bar ─────────────────────────────────────────
        self.branding = load_branding_config()
        self.header = HeaderWidget(branding=self.branding)
        self.header.import_logo_requested.connect(self._on_import_logo)
        root_layout.addWidget(self.header)

        # ── Main scrollable body ──────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #f1f5f9; }")

        body = QWidget()
        body.setStyleSheet("background: #f1f5f9;")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(32, 24, 32, 32)
        self.body_layout.setSpacing(18)

        # B — Dataset Upload
        self.upload_section = UploadSection()
        self.upload_section.datasets_changed.connect(self._on_datasets_changed)
        self.body_layout.addWidget(self.upload_section)

        # C — Dataset Information (compact metadata rows, visible after upload)
        self.dataset_info = DatasetInfoSection()
        self.dataset_info.setVisible(False)
        self.body_layout.addWidget(self.dataset_info)

        # D — Run Analysis
        self.run_section = RunSection()
        self.run_section.run_clicked.connect(self._start_analysis)
        self.run_section.clear_clicked.connect(self._clear_results)
        self.body_layout.addWidget(self.run_section)

        # E — Overall Score
        self.score_section = ScoreSection()
        self.score_section.setVisible(False)
        self.body_layout.addWidget(self.score_section)

        # F — Quality Dimension Scores
        self.dimensions_section = DimensionsSection()
        self.dimensions_section.setVisible(False)
        self.body_layout.addWidget(self.dimensions_section)

        # G — Quality Issues
        self.issues_section = IssuesSection()
        self.issues_section.setVisible(False)
        self.body_layout.addWidget(self.issues_section)

        # H — Relationship Integrity (prominent)
        self.relationships_section = RelationshipsSection()
        self.relationships_section.setVisible(False)
        self.body_layout.addWidget(self.relationships_section)

        # I — Recommendations
        self.recommendations_section = RecommendationsSection()
        self.recommendations_section.setVisible(False)
        self.body_layout.addWidget(self.recommendations_section)

        # J — Export Reports
        self.export_section = ExportSection()
        self.export_section.setVisible(False)
        self.body_layout.addWidget(self.export_section)

        # K — Scan History (SQLite persistence)
        self.history_section = HistorySection(db_path=self.db_path)
        self.history_section.scan_loaded.connect(self._on_history_scan_loaded)
        self.body_layout.addWidget(self.history_section)

        # L — Active Configuration (read-only)
        self.config_info = ConfigInfoSection(_CONFIG_PATH)
        self.config_info.import_logo_clicked.connect(self._on_import_logo)
        self.body_layout.addWidget(self.config_info)

        self.body_layout.addStretch()

        scroll.setWidget(body)
        root_layout.addWidget(scroll, 1)

        # Keep a reference to the scroll area for auto-scroll after results
        self._scroll = scroll

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_datasets_changed(self, datasets: list[tuple[str, pd.DataFrame]]):
        self.current_datasets = datasets
        self.run_section.set_datasets_ready(len(datasets) > 0)
        if datasets:
            self.dataset_info.update_datasets(datasets)
            self.dataset_info.setVisible(True)
        else:
            self.dataset_info.setVisible(False)

    def _start_analysis(self):
        if not self.current_datasets:
            QMessageBox.warning(
                self, "No Datasets",
                "Please upload at least one dataset before running analysis.",
            )
            return

        try:
            config = build_analysis_config_from_v2(_CONFIG_PATH) if _CONFIG_PATH.exists() else AnalysisConfig()
        except Exception as exc:
            QMessageBox.critical(
                self, "Configuration Error",
                f"Failed to load config/config.yaml:\n{exc}",
            )
            return

        # Reset results visibility
        for section in (
            self.score_section, self.dimensions_section,
            self.issues_section, self.relationships_section,
            self.recommendations_section, self.export_section,
        ):
            section.setVisible(False)

        self.run_section.set_running(True)
        self.dataset_info.set_status_all("Analysing…")

        self.worker = AnalysisWorker(
            datasets=self.current_datasets,
            config=config,
            parent=self,
        )
        self.worker.progress.connect(self.run_section.update_progress)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.cancelled.connect(self._on_analysis_cancelled)
        self.worker.request_mandatory_confirmation.connect(self._on_request_mandatory_confirmation)
        self.worker.start()

    def _on_request_mandatory_confirmation(self, fields: list[str]):
        """Show the confirmation popup on the GUI/main thread and relay user choice."""
        dialog = InferredMandatoryConfirmationDialog(fields, parent=self)
        accepted = (dialog.exec() == QDialog.Accepted)
        if hasattr(self, "worker") and self.worker:
            self.worker.set_confirmation_result(accepted)

    def _on_analysis_cancelled(self):
        """Handle user cancellation of mandatory fields confirmation cleanly."""
        self.run_section.set_running(False)
        self.run_section.reset()

        if self.current_result is not None:
            self.dataset_info.set_status_all("Analysed ✓")
            # Restore visibility of previously completed scan results
            for section in (
                self.score_section, self.dimensions_section,
                self.issues_section, self.relationships_section,
                self.recommendations_section, self.export_section,
            ):
                section.setVisible(True)
        else:
            self.dataset_info.set_status_all("Pending")

    def _on_analysis_finished(self, result: AnalysisResult):
        self.current_result = result

        self.run_section.set_running(False, timestamp=result.timestamp)
        self.dataset_info.set_status_all("Analysed ✓")

        self._display_result(result, datasets=self.current_datasets)

        # Persist to SQLite (non-blocking, failures do not halt UI)
        try:
            cfg_hash = get_config_hash(_CONFIG_PATH)
            saved_id = self.repo.save_scan(result, app_version="2.0.0", config_hash=cfg_hash)
            if saved_id is not None:
                self.history_section.refresh_history()
        except Exception as exc:
            logger.warning("Non-blocking persistence notice: failed to save scan: %s", exc)

    def _on_history_scan_loaded(self, result: AnalysisResult):
        """Restore a historical scan result into the active dashboard view."""
        self.current_result = result
        self.run_section.set_completed(timestamp=result.timestamp)
        self._display_result(result, datasets=None)

    def _display_result(self, result: AnalysisResult, datasets: list[tuple[str, pd.DataFrame]] | None = None):
        """Render an AnalysisResult across all dashboard sections."""
        self.score_section.set_result(result)
        self.score_section.setVisible(True)

        self.dimensions_section.set_result(result)
        self.dimensions_section.setVisible(True)

        self.issues_section.set_result(result)
        self.issues_section.setVisible(True)

        self.relationships_section.set_result(result)
        self.relationships_section.setVisible(True)

        self.recommendations_section.set_result(result)
        self.recommendations_section.setVisible(True)

        self.export_section.set_result(result, datasets=datasets)
        self.export_section.setVisible(True)

    def _on_analysis_error(self, err_msg: str):
        self.run_section.set_running(False)
        self.dataset_info.set_status_all("Error")
        QMessageBox.critical(
            self, "Analysis Failed",
            f"An error occurred during analysis:\n{err_msg}",
        )

    def _clear_results(self):
        self.current_result = None
        for section in (
            self.score_section, self.dimensions_section,
            self.issues_section, self.relationships_section,
            self.recommendations_section, self.export_section,
        ):
            section.setVisible(False)
        self.dataset_info.set_status_all("Pending")
        self.run_section.reset()

    def _on_import_logo(self):
        """Handle logo import request from header context menu or Section L."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Company Logo",
            "",
            "Supported Images (*.png *.jpg *.jpeg *.svg);;PNG Images (*.png);;JPEG Images (*.jpg *.jpeg);;SVG Images (*.svg);;All Files (*.*)",
        )
        if not file_path:
            return

        src = Path(file_path)
        root = get_project_root()
        target_dir = root / "assets" / "branding"
        collision_exists = (target_dir / src.name).exists()

        overwrite = False
        replace_active = False
        if collision_exists:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Logo Filename Collision")
            msg_box.setText(f"An asset named '{src.name}' already exists in branding assets.")
            msg_box.setInformativeText("Would you like to Replace the existing file or Save it as a new version?")
            btn_replace = msg_box.addButton("Replace", QMessageBox.AcceptRole)
            btn_new_ver = msg_box.addButton("Save as New Version", QMessageBox.ActionRole)
            btn_cancel = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(btn_replace)
            msg_box.exec()

            clicked = msg_box.clickedButton()
            if clicked == btn_cancel:
                return
            elif clicked == btn_replace:
                overwrite = True
                replace_active = True
            else:
                overwrite = False
                replace_active = False

        try:
            new_branding = import_branding_logo(
                source_path=src,
                project_root=root,
                overwrite=overwrite,
                replace_active=replace_active,
            )
            self.branding = new_branding
            self.header.update_branding(new_branding)
            QMessageBox.information(
                self,
                "Branding Updated",
                f"Company logo successfully updated to:\n{new_branding.logo_file}",
            )
        except Exception as exc:
            logger.error("Failed to import branding logo: %s", exc)
            QMessageBox.critical(
                self,
                "Logo Import Error",
                f"Failed to import company logo:\n{exc}",
            )

    def closeEvent(self, event):
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self.worker.set_confirmation_result(False)
            self.worker.wait(1000)
        event.accept()

