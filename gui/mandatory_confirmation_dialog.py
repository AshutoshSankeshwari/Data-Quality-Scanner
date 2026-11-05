"""
gui/mandatory_confirmation_dialog.py
Confirmation popup dialog for automatically inferred mandatory fields.
Allows the user to review and decide whether to apply newly detected
high-confidence mandatory fields before analysis execution completes.

Layout:
- Fixed Header (Title & prompt)
- Scrollable field list (QScrollArea, strictly bounded height)
- Fixed Footer (Explanation text & Cancel/Proceed buttons)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QWidget,
    QScrollArea,
    QSizePolicy,
)


class InferredMandatoryConfirmationDialog(QDialog):
    """
    Modal confirmation dialog presenting newly inferred mandatory fields to the user.
    Provides clear 'Proceed' and 'Cancel' choices with a scrollable field list
    and permanently visible fixed action buttons.
    """

    def __init__(self, new_fields: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Mandatory Fields Detected")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setMaximumWidth(560)
        self.setMaximumHeight(540)
        self.setStyleSheet("background-color: #ffffff;")

        # Main layout for fixed elements + scrollable list
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(14)

        # 1. Fixed Header area
        title_label = QLabel("Mandatory Fields Detected")
        title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #0f172a;")
        main_layout.addWidget(title_label)

        # 2. Fixed Prompt text
        prompt_label = QLabel(
            "The following fields were identified as likely mandatory based on the dataset:"
        )
        prompt_label.setWordWrap(True)
        prompt_label.setStyleSheet("font-size: 13px; color: #334155; line-height: 1.4;")
        main_layout.addWidget(prompt_label)

        # 3. Scrollable field list container
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #f1f5f9;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 24px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )

        # Fixed maximum height capped at 220px with scrolling for long lists
        self.scroll_area.setMaximumHeight(220)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        list_frame = QFrame()
        list_frame.setObjectName("listFrame")
        list_frame.setStyleSheet(
            """
            QFrame#listFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
            """
        )
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(14, 10, 14, 10)
        list_layout.setSpacing(6)

        for field in new_fields:
            item_label = QLabel(f"•  {field}")
            item_label.setStyleSheet(
                "font-size: 13px; font-weight: 600; color: #1e293b; background: transparent; border: none;"
            )
            list_layout.addWidget(item_label)

        list_layout.addStretch()
        self.scroll_area.setWidget(list_frame)
        main_layout.addWidget(self.scroll_area)

        # 4. Fixed Explanation text
        desc_label = QLabel(
            "These fields will be checked for missing values.\n\n"
            "Would you like to apply these fields for this analysis?"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 13px; color: #334155; line-height: 1.4;")
        main_layout.addWidget(desc_label)

        # 5. Fixed Action buttons (always visible at bottom)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(
            """
            QPushButton {
                background-color: #ffffff;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #1e293b;
                border-color: #94a3b8;
            }
            """
        )
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_proceed = QPushButton("Proceed")
        self.btn_proceed.setCursor(Qt.PointingHandCursor)
        self.btn_proceed.setDefault(True)
        self.btn_proceed.setStyleSheet(
            """
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #2563eb;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
                border-color: #1d4ed8;
            }
            """
        )
        self.btn_proceed.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_proceed)

        main_layout.addLayout(btn_layout)

    def closeEvent(self, event):
        """Ensure closing via window X button rejects the dialog cleanly."""
        self.reject()
        event.accept()

    def keyPressEvent(self, event):
        """Escape key rejects the dialog."""
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
