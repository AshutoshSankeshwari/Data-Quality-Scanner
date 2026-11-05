"""
gui/workers.py
Background worker thread for running AnalysisService asynchronously
so the PySide6 UI remains completely responsive during heavy analysis.
"""
from __future__ import annotations

import threading
from PySide6.QtCore import QThread, Signal
import pandas as pd

from core.service import AnalysisService, AnalysisConfig, AnalysisCancelledError


class AnalysisWorker(QThread):
    """Worker thread that executes AnalysisService.run()."""
    progress = Signal(str, int)                      # (status_message, percentage 0-100)
    finished = Signal(object)                       # emits AnalysisResult
    error = Signal(str)                             # emits error message string
    cancelled = Signal()                            # emits when analysis is cancelled by user
    request_mandatory_confirmation = Signal(list)   # emits list[str] of newly inferred mandatory fields

    def __init__(
        self,
        datasets: list[tuple[str, pd.DataFrame]],
        config: AnalysisConfig,
        parent=None,
    ):
        super().__init__(parent)
        self.datasets = datasets
        self.config = config
        self.service = AnalysisService()
        self._confirm_event = threading.Event()
        self._confirm_result = False

    def confirm_mandatory_callback(self, fields: list[str]) -> bool:
        """Called by AnalysisService on the background thread to ask user approval."""
        self._confirm_result = False
        self._confirm_event.clear()
        self.request_mandatory_confirmation.emit(fields)
        self._confirm_event.wait()
        return self._confirm_result

    def set_confirmation_result(self, approved: bool):
        """Called from the GUI main thread to unblock the worker with user's decision."""
        self._confirm_result = approved
        self._confirm_event.set()

    def run(self):
        try:
            def _on_progress(step_msg: str, pct: float):
                self.progress.emit(step_msg, int(pct))

            result = self.service.run(
                datasets=self.datasets,
                config=self.config,
                progress_callback=_on_progress,
                mandatory_confirmation_callback=self.confirm_mandatory_callback,
            )
            self.finished.emit(result)
        except AnalysisCancelledError:
            self.cancelled.emit()
        except Exception as e:
            self.error.emit(str(e))
