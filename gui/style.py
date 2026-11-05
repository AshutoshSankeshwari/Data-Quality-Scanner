"""
gui/style.py
Global theme, QPalette, and stylesheet configuration for high contrast and modern UI.
Ensures dark, readable text on light backgrounds regardless of OS Dark Mode settings.
"""
from __future__ import annotations
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


GLOBAL_STYLESHEET = """
/* Base typography and widget defaults */
QWidget {
    color: #1e293b;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

/* Window and containers */
QMainWindow {
    background-color: #f8fafc;
}

QStackedWidget {
    background-color: #f8fafc;
}

/* Headings and labels */
QLabel {
    color: #1e293b;
    background: transparent;
    border: none;
}

/* Table styling */
QTableWidget, QTableView {
    background-color: #ffffff;
    color: #1e293b;
    gridline-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    selection-background-color: #e0f2fe;
    selection-color: #0369a1;
    outline: none;
}

QTableWidget::item, QTableView::item {
    color: #1e293b;
    padding: 5px 8px;
    border: none;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #e0f2fe;
    color: #0369a1;
    font-weight: 600;
}

QHeaderView {
    background-color: #f1f5f9;
    border: none;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #334155;
    font-weight: 700;
    font-size: 12px;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #cbd5e1;
}

QHeaderView::section:last {
    border-right: none;
}

/* List widget styling */
QListWidget, QListView {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    outline: none;
}

QListWidget::item, QListView::item {
    color: #1e293b;
    padding: 6px 10px;
    border-radius: 4px;
}

QListWidget::item:hover, QListView::item:hover {
    background-color: #f1f5f9;
}

QListWidget::item:selected, QListView::item:selected {
    background-color: #e0f2fe;
    color: #0369a1;
    font-weight: 600;
}

/* Text inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #bfdbfe;
    selection-color: #1e293b;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #2563eb;
}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* ComboBox */
QComboBox {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 20px;
    font-weight: 600;
}

QComboBox:hover {
    border-color: #94a3b8;
}

QComboBox:focus {
    border-color: #2563eb;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    selection-background-color: #e0f2fe;
    selection-color: #0369a1;
    padding: 4px;
    outline: none;
}

/* Checkboxes */
QCheckBox {
    color: #1e293b;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #94a3b8;
    border-radius: 4px;
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: #2563eb;
    background-color: #f0f7ff;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

QCheckBox::indicator:disabled {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
}

/* Standard buttons (if not specifically styled with custom background) */
QPushButton {
    background-color: #f1f5f9;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #e2e8f0;
    color: #0f172a;
    border-color: #94a3b8;
}

QPushButton:pressed {
    background-color: #cbd5e1;
}

QPushButton:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background: #ffffff;
    border-radius: 8px;
}

QTabBar::tab {
    background: #f1f5f9;
    color: #475569;
    padding: 8px 16px;
    font-weight: 600;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #1e3a8a;
    border-bottom: 2px solid #2563eb;
    font-weight: 700;
}

QTabBar::tab:hover:!selected {
    background: #e2e8f0;
    color: #1e293b;
}

/* ScrollBars */
QScrollBar:vertical {
    background: #f8fafc;
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

QScrollBar:horizontal {
    background: #f8fafc;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    min-width: 24px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* GroupBox */
QGroupBox {
    font-weight: bold;
    color: #1e3a8a;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    background: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #1e3a8a;
}
"""


def create_light_palette() -> QPalette:
    """Create an explicit high-contrast light QPalette to prevent dark mode leakage."""
    palette = QPalette()
    
    # Base background and text colors
    palette.setColor(QPalette.Window, QColor("#f8fafc"))
    palette.setColor(QPalette.WindowText, QColor("#1e293b"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f1f5f9"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#1e293b"))
    palette.setColor(QPalette.Text, QColor("#1e293b"))
    palette.setColor(QPalette.Button, QColor("#f1f5f9"))
    palette.setColor(QPalette.ButtonText, QColor("#1e293b"))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Link, QColor("#2563eb"))
    palette.setColor(QPalette.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.PlaceholderText, QColor("#94a3b8"))
    
    # Disabled state
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#94a3b8"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#94a3b8"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#94a3b8"))
    palette.setColor(QPalette.Disabled, QPalette.Highlight, QColor("#e2e8f0"))
    palette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor("#94a3b8"))
    palette.setColor(QPalette.Disabled, QPalette.Base, QColor("#f8fafc"))
    
    return palette


def setup_theme(app: QApplication):
    """Apply Fusion style, explicit light palette, and global stylesheet."""
    app.setStyle("Fusion")
    app.setPalette(create_light_palette())
    app.setStyleSheet(GLOBAL_STYLESHEET)
