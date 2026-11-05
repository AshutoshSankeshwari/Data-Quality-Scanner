"""
gui/sections/relationships_section.py
Section H — Relationship Integrity & Detection.

Displays:
  - Relationship Detected: YES / NO (with origin badge)
  - Parent & Child linkage visualization (Parent ➔ Child)
  - Integrity Status: PASSED / FAILED
  - Metric strip (Child Records, Invalid References, Invalid Rate) matching dashboard styling
  - Clean, full-width table of exact problematic child row numbers and invalid key values
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.models import AnalysisResult, RelationshipResult
from gui.sections.section_helpers import make_section_card, make_section_header


class RelationshipsSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card, card_layout = make_section_card()
        card_layout.addWidget(
            make_section_header(
                "Relationship Integrity & Detection",
                subtitle="Automatic parent-child relationship detection and referential integrity validation",
                accent_color="#7c3aed",
            )
        )

        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._b_layout = QVBoxLayout(self._body)
        self._b_layout.setContentsMargins(20, 16, 20, 20)
        self._b_layout.setSpacing(14)

        card_layout.addWidget(self._body)
        outer.addWidget(self._card)

    def set_result(self, result: AnalysisResult):
        # Clear existing widgets
        while self._b_layout.count():
            item = self._b_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rels = result.relationship_results

        if not rels:
            # Clean informational empty state when no relationship is detected
            no_rel_card = QFrame()
            no_rel_card.setStyleSheet("""
                QFrame {
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                }
            """)
            no_layout = QVBoxLayout(no_rel_card)
            no_layout.setContentsMargins(18, 14, 18, 14)
            no_layout.setSpacing(4)

            det_lbl = QLabel("<b>Relationship Detected:</b> <span style='color: #64748b; font-weight: 700;'>NO</span>")
            det_lbl.setStyleSheet("font-size: 13px; color: #1e293b; background: transparent;")
            no_layout.addWidget(det_lbl)

            msg_lbl = QLabel("No relationship detected between the currently loaded datasets.")
            msg_lbl.setStyleSheet("font-size: 12px; color: #64748b; background: transparent;")
            no_layout.addWidget(msg_lbl)

            self._b_layout.addWidget(no_rel_card)
            return

        # Relationship Detected: YES
        for rel in rels:
            self._b_layout.addWidget(self._make_relationship_card(rel))

    def _make_relationship_card(self, rel: RelationshipResult) -> QFrame:
        card = QFrame()
        is_passed = (rel.orphan_count == 0)

        # Primary relationship card matching dashboard border and radius scale
        card.setStyleSheet("""
            QFrame#primaryRelCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        card.setObjectName("primaryRelCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # ── 1. Header Row: Relationship Detected + Origin & Integrity Status Badge ──
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        det_title = QLabel("<b>Relationship Detected:</b>")
        det_title.setStyleSheet("font-size: 13px; color: #1e293b; background: transparent;")
        header_row.addWidget(det_title)

        det_val = QLabel("YES")
        det_val.setStyleSheet("font-size: 13px; font-weight: 800; color: #0f172a; background: transparent;")
        header_row.addWidget(det_val)

        origin_str = rel.origin_display
        origin_badge = QLabel(origin_str)
        origin_badge.setStyleSheet("""
            font-size: 11px;
            color: #475569;
            background: #f1f5f9;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 2px 8px;
            font-weight: 500;
        """)
        header_row.addWidget(origin_badge)

        header_row.addStretch()

        status_text = "PASSED" if is_passed else "FAILED"
        status_bg = "#dcfce7" if is_passed else "#fee2e2"
        status_fg = "#15803d" if is_passed else "#b91c1c"
        status_border = "#bbf7d0" if is_passed else "#fecaca"
        status_badge = QLabel(f"Integrity Status:  {status_text}")
        status_badge.setStyleSheet(f"""
            background: {status_bg};
            color: {status_fg};
            border: 1px solid {status_border};
            font-size: 11px;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 4px;
        """)
        header_row.addWidget(status_badge)
        layout.addLayout(header_row)

        # ── 2. Parent ➔ Child Relationship Linkage Visualization ─────
        p_key = ", ".join(rel.parent_key) if isinstance(rel.parent_key, list) else str(rel.parent_key)
        c_key = ", ".join(rel.child_key) if isinstance(rel.child_key, list) else str(rel.child_key)

        link_container = QHBoxLayout()
        link_container.setSpacing(12)

        # Parent Card
        parent_card = QFrame()
        parent_card.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #edf2f7;
                border-radius: 6px;
            }
        """)
        p_layout = QVBoxLayout(parent_card)
        p_layout.setContentsMargins(14, 10, 14, 10)
        p_layout.setSpacing(2)
        p_lbl = QLabel("PARENT DATASET & KEY")
        p_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; background: transparent; letter-spacing: 0.3px;")
        p_val = QLabel(f"{rel.parent_dataset}.{p_key}")
        p_val.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e293b; background: transparent;")
        p_layout.addWidget(p_lbl)
        p_layout.addWidget(p_val)
        link_container.addWidget(parent_card, 1)

        # Connector Arrow
        arrow_lbl = QLabel("➔")
        arrow_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #7c3aed; background: transparent;")
        arrow_lbl.setAlignment(Qt.AlignCenter)
        link_container.addWidget(arrow_lbl)

        # Child Card
        child_card = QFrame()
        child_card.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #edf2f7;
                border-radius: 6px;
            }
        """)
        c_layout = QVBoxLayout(child_card)
        c_layout.setContentsMargins(14, 10, 14, 10)
        c_layout.setSpacing(2)
        c_lbl = QLabel("CHILD DATASET & KEY")
        c_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; background: transparent; letter-spacing: 0.3px;")
        c_val = QLabel(f"{rel.child_dataset}.{c_key}")
        c_val.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e293b; background: transparent;")
        c_layout.addWidget(c_lbl)
        c_layout.addWidget(c_val)
        link_container.addWidget(child_card, 1)

        layout.addLayout(link_container)

        # ── 3. Metric Strip (Matching Dashboard Metric Cards) ─────────
        metrics_strip = QFrame()
        metrics_strip.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
        """)
        strip_layout = QHBoxLayout(metrics_strip)
        strip_layout.setContentsMargins(16, 12, 16, 12)
        strip_layout.setSpacing(0)

        metric_defs = [
            ("CHILD RECORDS", f"{rel.total_child_records:,}", "#0f172a"),
            ("INVALID REFERENCES", f"{rel.orphan_count:,}", "#dc2626" if rel.orphan_count > 0 else "#0f172a"),
            ("INVALID RATE", f"{rel.orphan_pct:.1f}%", "#dc2626" if rel.orphan_pct > 0 else "#0f172a"),
        ]

        for i, (label, val_str, accent) in enumerate(metric_defs):
            m_frame = QFrame()
            m_frame.setStyleSheet("background: transparent; border: none;")
            m_vbox = QVBoxLayout(m_frame)
            m_vbox.setContentsMargins(12, 0, 12, 0)
            m_vbox.setSpacing(2)

            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; background: transparent; letter-spacing: 0.3px;")
            val = QLabel(val_str)
            val.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {accent}; background: transparent;")
            m_vbox.addWidget(lbl)
            m_vbox.addWidget(val)

            strip_layout.addWidget(m_frame, 1)

            if i < len(metric_defs) - 1:
                divider = QFrame()
                divider.setFixedWidth(1)
                divider.setStyleSheet("background: #e2e8f0; border: none;")
                strip_layout.addWidget(divider)

        layout.addWidget(metrics_strip)

        # ── 4. Invalid References Table (Shown only when failed) ───────
        if rel.orphan_count > 0 and rel.sample_orphan_records:
            sec_title = QLabel("Invalid References")
            sec_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e293b; margin-top: 4px;")
            layout.addWidget(sec_title)

            records_to_show = rel.sample_orphan_records[:10]
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Row", "Field", "Invalid Value", "Reason"])
            table.setRowCount(len(records_to_show))
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionMode(QTableWidget.NoSelection)
            table.setShowGrid(True)

            # Table styling matching dashboard tables
            table.setStyleSheet("""
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    gridline-color: #f1f5f9;
                }
                QHeaderView::section {
                    background-color: #f8fafc;
                    color: #475569;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 6px 10px;
                    border: none;
                    border-bottom: 1px solid #e2e8f0;
                    border-right: 1px solid #f1f5f9;
                }
                QTableWidget::item {
                    padding: 5px 10px;
                    color: #334155;
                    font-size: 11px;
                    border-bottom: 1px solid #f1f5f9;
                }
            """)

            h_header = table.horizontalHeader()
            h_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(3, QHeaderView.Stretch)
            h_header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(28)

            for row_idx, s in enumerate(records_to_show):
                r_num = s.get("row_number", "?")
                k_val = s.get("key_value", "?")
                fld = s.get("child_key", c_key)

                # Row item
                row_item = QTableWidgetItem(str(r_num))
                row_item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_idx, 0, row_item)

                # Field item
                field_item = QTableWidgetItem(str(fld))
                table.setItem(row_idx, 1, field_item)

                # Invalid Value item
                val_item = QTableWidgetItem(str(k_val))
                font = val_item.font()
                font.setBold(True)
                val_item.setFont(font)
                val_item.setForeground(QColor("#dc2626"))
                table.setItem(row_idx, 2, val_item)

                # Reason item
                reason_item = QTableWidgetItem(f"Value does not exist in {rel.parent_dataset}.{p_key}")
                reason_item.setForeground(QColor("#475569"))
                table.setItem(row_idx, 3, reason_item)

            total_height = 32 + (len(records_to_show) * 28) + 4
            table.setFixedHeight(total_height)
            layout.addWidget(table)

            # Subtle footer note
            if rel.orphan_count > 10:
                footer_text = f"Showing 10 of {rel.orphan_count} invalid records. Full details are available in exported reports."
            else:
                footer_text = f"Showing all {rel.orphan_count} invalid records. Full details are available in exported reports."
            footer_lbl = QLabel(footer_text)
            footer_lbl.setStyleSheet("font-size: 11px; color: #64748b; font-style: italic; background: transparent;")
            layout.addWidget(footer_lbl)

        return card
