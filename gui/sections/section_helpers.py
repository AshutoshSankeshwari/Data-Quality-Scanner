"""
gui/sections/section_helpers.py
Shared styling and helper functions for section cards and headers.
Refined for a clean, modern enterprise dashboard layout without
nested borders or heavy full-width saturated gradients.
"""
from __future__ import annotations
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


SECTION_CARD_STYLE = """
    QFrame#sectionCard {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }
"""


def make_section_card() -> tuple[QFrame, QVBoxLayout]:
    """Return (card QFrame, inner QVBoxLayout)."""
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setStyleSheet(SECTION_CARD_STYLE)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return card, layout


def make_section_header(
    title: str,
    subtitle: str = "",
    accent_color: str = "#2563eb",
    color0: str | None = None,  # Backwards compatibility
    color1: str | None = None,  # Backwards compatibility
) -> QFrame:
    """
    Return a refined section header:
    Clean dark typography with a subtle vertical accent pill,
    optional subtitle, and a subtle bottom separator.
    """
    if color0 is not None:
        accent = color0
    else:
        accent = accent_color

    header = QFrame()
    header.setStyleSheet("""
        QFrame {
            background: #ffffff;
            border-bottom: 1px solid #f1f5f9;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
    """)
    h_layout = QHBoxLayout(header)
    h_layout.setContentsMargins(20, 14, 20, 14)
    h_layout.setSpacing(10)

    # Accent color pill
    accent_pill = QFrame()
    accent_pill.setFixedSize(4, 18)
    accent_pill.setStyleSheet(f"""
        QFrame {{
            background-color: {accent};
            border-radius: 2px;
            border: none;
        }}
    """)
    h_layout.addWidget(accent_pill)

    # Title
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        "color: #0f172a; font-size: 15px; font-weight: 700; background: transparent; border: none;"
    )
    h_layout.addWidget(title_lbl)

    if subtitle:
        h_layout.addSpacing(6)
        sub_lbl = QLabel(f"·  {subtitle}")
        sub_lbl.setStyleSheet(
            "color: #64748b; font-size: 12px; font-weight: 400; background: transparent; border: none;"
        )
        h_layout.addWidget(sub_lbl)

    h_layout.addStretch()
    return header
