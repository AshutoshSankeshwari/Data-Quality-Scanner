"""
main.py
Application Entry Point for the Migration Data Quality Scanner & PMA Profiler GUI.
"""
from __future__ import annotations
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from gui.style import setup_theme
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    setup_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
