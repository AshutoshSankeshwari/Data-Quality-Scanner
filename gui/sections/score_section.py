"""
gui/sections/score_section.py
Section E — Overall Data Quality Result.

Primary dashboard summary featuring the circular readiness gauge,
overall readiness category, and compact, borderless KPI statistics.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PySide6.QtCore import Qt

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.models import AnalysisResult
from gui.sections.section_helpers import make_section_card, make_section_header


class ScoreSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stat_cards: dict[str, QFrame] = {}
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card, layout = make_section_card()
        layout.addWidget(
            make_section_header(
                "Overall Data Quality Result",
                accent_color="#2563eb",
            )
        )

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_layout = QHBoxLayout(body)
        b_layout.setContentsMargins(20, 16, 20, 18)
        b_layout.setSpacing(28)

        # ── Circular Readiness Gauge ──────────────────────────────────
        self._gauge_fig = Figure(figsize=(2.5, 2.5), dpi=100, facecolor="#ffffff")
        self._gauge_canvas = FigureCanvas(self._gauge_fig)
        self._gauge_canvas.setFixedSize(220, 180)
        self._gauge_canvas.setStyleSheet("background: transparent; border: none;")
        b_layout.addWidget(self._gauge_canvas, alignment=Qt.AlignVCenter)

        # ── Right Side: Compact Metrics ──────────────────────────────
        right = QWidget()
        right.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 4, 0, 4)
        right_layout.setSpacing(16)
        right_layout.addStretch()

        # Compact statistics row (no nested heavy cards)
        stats_strip = QFrame()
        stats_strip.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
        """)
        strip_layout = QHBoxLayout(stats_strip)
        strip_layout.setContentsMargins(16, 12, 16, 12)
        strip_layout.setSpacing(0)

        metrics = [
            ("score",         "Readiness Score", "—", "#2563eb"),
            ("critical",      "Critical Issues", "0", "#ef4444"),
            ("high",          "High Issues",     "0", "#f97316"),
            ("total",         "Total Issues",    "0", "#0284c7"),
            ("affected_rows", "Affected Rows",   "—", "#7c3aed"),
            ("datasets",      "Datasets",        "0", "#475569"),
        ]

        for i, (key, label, default_val, accent) in enumerate(metrics):
            item_frame = QFrame()
            item_frame.setStyleSheet("background: transparent; border: none;")
            i_layout = QVBoxLayout(item_frame)
            i_layout.setContentsMargins(10, 0, 10, 0)
            i_layout.setSpacing(2)

            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                "font-size: 10px; font-weight: 700; color: #64748b; background: transparent; letter-spacing: 0.3px;"
            )
            val = QLabel(default_val)
            val.setStyleSheet(
                f"font-size: 20px; font-weight: 800; color: {accent}; background: transparent;"
            )
            i_layout.addWidget(lbl)
            i_layout.addWidget(val)

            item_frame._val_label = val
            self._stat_cards[key] = item_frame
            strip_layout.addWidget(item_frame, 1)

            # Divider between metrics
            if i < len(metrics) - 1:
                divider = QFrame()
                divider.setFixedWidth(1)
                divider.setStyleSheet("background: #e2e8f0; border: none;")
                strip_layout.addWidget(divider)

        right_layout.addWidget(stats_strip)
        right_layout.addStretch()
        b_layout.addWidget(right, 1)

        layout.addWidget(body)
        outer.addWidget(card)

    def set_result(self, result: AnalysisResult):
        from reports.summary_builder import count_affected_rows

        sc = result.score
        if not sc:
            return

        # Draw gauge chart
        self._draw_gauge(sc.overall)

        # Update metric numbers
        total = sc.blocker_count + sc.high_count + sc.medium_count + sc.low_count
        self._stat_cards["score"]._val_label.setText(f"{sc.overall:.1f}")
        self._stat_cards["critical"]._val_label.setText(str(sc.blocker_count))
        self._stat_cards["high"]._val_label.setText(str(sc.high_count))
        self._stat_cards["total"]._val_label.setText(str(total))
        aff = count_affected_rows(result)
        self._stat_cards["affected_rows"]._val_label.setText(f"{aff:,}" if aff is not None else "—")
        self._stat_cards["datasets"]._val_label.setText(str(len(result.datasets)))

    def _draw_gauge(self, score: float, category: str = ""):
        if score >= 90:
            color = "#10b981"
        elif score >= 75:
            color = "#84cc16"
        elif score >= 50:
            color = "#f59e0b"
        else:
            color = "#ef4444"

        self._gauge_fig.clear()
        ax = self._gauge_fig.add_subplot(111)

        remainder = max(0.0, 100.0 - score)
        ax.pie(
            [score, remainder],
            colors=[color, "#f1f5f9"],
            startangle=90,
            counterclock=False,
            wedgeprops={"width": 0.24, "edgecolor": "white", "linewidth": 1.5},
        )
        # Centered score text
        ax.text(0, 0.08, f"{score:.1f}", ha="center", va="center",
                fontsize=24, fontweight="bold", color="#0f172a")
        ax.text(0, -0.22, "SCORE / 100", ha="center", va="center",
                fontsize=7, fontweight="bold", color="#94a3b8")

        ax.axis("equal")
        self._gauge_fig.tight_layout(pad=0.1)
        self._gauge_canvas.draw()
