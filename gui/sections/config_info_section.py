"""
gui/sections/config_info_section.py
Section L — Read-only active configuration indicator.
No editor. No check selection. No rule customization.
"""
from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QPushButton
from PySide6.QtCore import Qt, Signal
from rules.config_loader import get_config_hash


class ConfigInfoSection(QWidget):
    import_logo_clicked = Signal()

    def __init__(self, config_path: Path, parent=None):
        super().__init__(parent)
        self._path = config_path
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(14)

        icon = QLabel("⚙️")
        icon.setStyleSheet("font-size: 18px; background: transparent;")

        cfg_hash = get_config_hash(self._path)
        if self._path.exists():
            cfg_path_str = str(self._path.resolve())
            detail_str = f"<code>{cfg_path_str}</code>  ·  hash: <code>{cfg_hash}</code>"
        else:
            detail_str = "<code>config/config.yaml</code> not found · Running in Default Inference Mode"

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)

        title = QLabel("<b>Active Configuration</b>  <span style='color: #64748b; font-weight: normal;'>(read-only)</span>")
        title.setStyleSheet("color: #0f172a; font-size: 13px; background: transparent;")

        detail = QLabel(detail_str)
        detail.setStyleSheet("color: #475569; font-size: 11px; background: transparent;")
        detail.setWordWrap(True)

        note = QLabel(
            "All quality checks, rules, thresholds, and scoring weights are managed "
            "exclusively through <code>config/config.yaml</code>. "
            "In-app configuration editing, rule selection, and check customization are disabled by design."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent;")

        text_layout.addWidget(title)
        text_layout.addWidget(detail)
        text_layout.addWidget(note)

        layout.addWidget(icon, alignment=Qt.AlignTop)
        layout.addLayout(text_layout, 1)

        # ── Branding Logo Import Control ──────────────────────────────
        self.btn_import_logo = QPushButton("🎨  Import Company Logo…")
        self.btn_import_logo.setToolTip("Upload a PNG, JPG, JPEG, or SVG company logo for dashboard header branding")
        self.btn_import_logo.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #e2e8f0;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background: #cbd5e1;
            }
        """)
        self.btn_import_logo.clicked.connect(self.import_logo_clicked.emit)
        layout.addWidget(self.btn_import_logo, alignment=Qt.AlignVCenter)

        outer.addWidget(card)

