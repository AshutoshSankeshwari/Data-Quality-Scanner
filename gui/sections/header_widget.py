"""
gui/sections/header_widget.py
Top application header bar with configurable company branding.
Layout Arrangement:
[ LEFT LOGO 1 ] | [ LEFT LOGO 2 ]        [ CENTERED TITLE / DESCRIPTION ]        [ EXISTING RIGHT LOGO ]

Features:
- Left Wing: Corporate logos (c1_logo.png and c2_logo.png) with subtle 1px divider.
- Center Container: Mathematically centered application title and description.
- Right Viewport (PROTECTED REGION): Unchanged right-side company logo anchored far right.
- Symmetric dynamic wing balancing (_balance_wings) guarantees true geometric centering.
- Safe rendering (_render_pixmap_safe) preserving aspect ratio without increasing header height.
"""
from __future__ import annotations
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QMenu, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QAction

from core.models import BrandingConfig, LeftLogoConfig
from rules.config_loader import load_branding_config, resolve_asset_path

logger = logging.getLogger(__name__)

# Fixed header and viewport geometry specifications
HEADER_HEIGHT = 76
HEADER_MARGIN_TOP = 10
HEADER_MARGIN_BOTTOM = 10
HEADER_MARGIN_LEFT = 28
HEADER_MARGIN_RIGHT = 28
VIEWPORT_HEIGHT = HEADER_HEIGHT - HEADER_MARGIN_TOP - HEADER_MARGIN_BOTTOM  # 56px
VIEWPORT_MAX_WIDTH = 320
LEFT_LOGO_MAX_HEIGHT = 40
LEFT_LOGO_MAX_WIDTH = 160


def _render_pixmap_safe(
    path: Path | str,
    max_w: int,
    max_h: int,
) -> QPixmap | None:
    """
    Safely load and render an image preserving exact aspect ratio.
    Supports SVG (via QSvgRenderer) and supported raster formats (.png, .jpg, .jpeg).
    Prevents distortion and guarantees dimensions never exceed (max_w, max_h).
    Gracefully returns None on invalid/missing files or rendering errors.
    """
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None

    ext = p.suffix.lower()
    if ext not in (".svg", ".png", ".jpg", ".jpeg"):
        return None

    try:
        if ext == ".svg":
            from PySide6.QtSvg import QSvgRenderer
            renderer = QSvgRenderer(str(p))
            if not renderer.isValid():
                logger.warning("Invalid SVG branding logo file: %s", p)
                return None
            def_sz = renderer.defaultSize()
            aspect = (def_sz.width() / def_sz.height()) if def_sz.height() > 0 else 1.0
            target_h = max_h
            target_w = max(1, int(target_h * aspect))
            if target_w > max_w:
                target_w = max_w
                target_h = max(1, int(target_w / aspect))

            pm = QPixmap(target_w, target_h)
            pm.fill(Qt.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            renderer.render(painter)
            painter.end()
            return pm
        else:
            pm_raw = QPixmap(str(p))
            if pm_raw.isNull():
                logger.warning("Failed to load raster branding logo file: %s", p)
                return None
            aspect = (pm_raw.width() / pm_raw.height()) if pm_raw.height() > 0 else 1.0
            target_h = max_h
            target_w = max(1, int(target_h * aspect))
            if target_w > max_w:
                target_w = max_w
                target_h = max(1, int(target_w / aspect))

            return pm_raw.scaled(
                target_w, target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    except Exception as exc:
        logger.warning("Error rendering pixmap from %s: %s", p, exc)
        return None


class HeaderWidget(QFrame):
    """
    Application top header bar displaying configurable company branding.
    Layout: [Left Wing] [Left Balance] [Stretch] [Center Container] [Stretch] [Right Balance] [Right Viewport]
    Header height is strictly invariant across all logo sizes and asset dimensions.
    """
    import_logo_requested = Signal()

    def __init__(
        self,
        branding: BrandingConfig | None = None,
        cfg_hash: str | None = None,
        project_root: Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("appHeader")
        self.project_root = project_root

        # Fixed, stable header height - will NEVER expand
        self.setFixedHeight(HEADER_HEIGHT)
        self.setMinimumHeight(HEADER_HEIGHT)
        self.setMaximumHeight(HEADER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setStyleSheet("""
            QFrame#appHeader {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0f172a, stop:0.7 #1e3a8a, stop:1 #1e40af
                );
                border-bottom: 1px solid #172554;
            }
        """)

        self.active_logo_path: Path | None = None
        self.current_branding: BrandingConfig | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            HEADER_MARGIN_LEFT,
            HEADER_MARGIN_TOP,
            HEADER_MARGIN_RIGHT,
            HEADER_MARGIN_BOTTOM,
        )
        layout.setSpacing(0)

        # ── Region 1: Left Wing (Left Logos & Subtle Divider) ────────
        self.left_container = QWidget(self)
        self.left_container.setObjectName("headerLeftWing")
        self.left_container.setFixedHeight(VIEWPORT_HEIGHT)
        self.left_container.setStyleSheet("background: transparent;")

        self.left_layout = QHBoxLayout(self.left_container)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(12)
        self.left_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.left_logo_1_label = QLabel(self.left_container)
        self.left_logo_1_label.setObjectName("headerLeftLogo1")
        self.left_logo_1_label.setStyleSheet("background: transparent;")
        self.left_logo_1_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.left_divider_container = QWidget(self.left_container)
        self.left_divider_container.setObjectName("headerLeftDividerContainer")
        self.left_divider_container.setFixedWidth(1)
        self.left_divider_container.setFixedHeight(VIEWPORT_HEIGHT)
        self.left_divider_container.setStyleSheet("background: transparent;")

        div_layout = QVBoxLayout(self.left_divider_container)
        div_layout.setContentsMargins(0, 0, 0, 0)
        div_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.left_divider = QFrame(self.left_divider_container)
        self.left_divider.setObjectName("headerLeftDivider")
        self.left_divider.setFrameShape(QFrame.Shape.VLine)
        self.left_divider.setFrameShadow(QFrame.Shadow.Plain)
        self.left_divider.setFixedWidth(1)
        self.left_divider.setFixedHeight(30)
        self.left_divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.18); border: none;")
        div_layout.addWidget(self.left_divider)

        self.left_logo_2_label = QLabel(self.left_container)
        self.left_logo_2_label.setObjectName("headerLeftLogo2")
        self.left_logo_2_label.setStyleSheet("background: transparent;")
        self.left_logo_2_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.left_layout.addWidget(self.left_logo_1_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.left_layout.addWidget(self.left_divider_container, 0, Qt.AlignmentFlag.AlignCenter)
        self.left_layout.addWidget(self.left_logo_2_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.left_container, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # ── Left Balance Widget (Expands when right wing is wider) ──
        self.left_balance = QWidget(self)
        self.left_balance.setObjectName("headerLeftBalance")
        self.left_balance.setFixedHeight(VIEWPORT_HEIGHT)
        self.left_balance.setFixedWidth(0)
        self.left_balance.setStyleSheet("background: transparent;")
        layout.addWidget(self.left_balance, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # ── Stretch 1: Left push for mathematical centering ─────────
        layout.addStretch(1)

        # ── Region 2: Center Container (Title & Subtitle) ───────────
        self.center_container = QWidget(self)
        self.center_container.setObjectName("headerCenterContainer")
        self.center_container.setStyleSheet("background: transparent;")

        center_layout = QVBoxLayout(self.center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(1)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(self.center_container)
        self.title_label.setObjectName("headerTitle")
        self.title_label.setStyleSheet(
            "color: #ffffff; font-size: 19px; font-weight: 700; background: transparent; letter-spacing: -0.2px;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sub_label = QLabel(self.center_container)
        self.sub_label.setObjectName("headerDescription")
        self.sub_label.setStyleSheet(
            "color: #93c5fd; font-size: 11px; font-weight: 500; background: transparent; margin-top: 1px;"
        )
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        center_layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignHCenter)
        center_layout.addWidget(self.sub_label, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(self.center_container, 0, Qt.AlignmentFlag.AlignCenter)

        # ── Stretch 2: Right push for mathematical centering ────────
        layout.addStretch(1)

        # ── Right Balance Widget (Expands when left wing is wider) ──
        self.right_balance = QWidget(self)
        self.right_balance.setObjectName("headerRightBalance")
        self.right_balance.setFixedHeight(VIEWPORT_HEIGHT)
        self.right_balance.setFixedWidth(0)
        self.right_balance.setStyleSheet("background: transparent;")
        layout.addWidget(self.right_balance, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # ── Region 3: Dedicated Right Logo Viewport (PROTECTED REGION) ──
        self.logo_viewport = QWidget(self)
        self.logo_viewport.setObjectName("headerLogoViewport")
        self.logo_viewport.setFixedHeight(VIEWPORT_HEIGHT)
        self.logo_viewport.setMaximumWidth(VIEWPORT_MAX_WIDTH)
        self.logo_viewport.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        viewport_layout = QHBoxLayout(self.logo_viewport)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setSpacing(0)

        self.logo_label = QLabel(self.logo_viewport)
        self.logo_label.setObjectName("headerLogo")
        self.logo_label.setStyleSheet("background: transparent;")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.logo_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.logo_label.setMaximumHeight(VIEWPORT_HEIGHT)
        self.logo_label.setToolTip("Company Logo (Right-click to change)")

        viewport_layout.addWidget(self.logo_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.logo_viewport, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Initial render
        cfg = branding if branding is not None else load_branding_config()
        self.update_branding(cfg)

    def contextMenuEvent(self, event):
        """Allow administrator to right-click header to import/change company logo."""
        menu = QMenu(self)
        change_action = QAction("🎨 Change Company Logo…", self)
        change_action.triggered.connect(self.import_logo_requested.emit)
        menu.addAction(change_action)
        menu.exec(event.globalPos())

    def update_branding(self, branding: BrandingConfig) -> None:
        """Update header title, description, and logos live from a BrandingConfig instance."""
        self.current_branding = branding

        title_text = branding.title.strip() if branding.title else "Data Quality Scanner V2.5"
        self.title_label.setText(title_text)

        if branding.description and branding.description.strip():
            self.sub_label.setText(branding.description.strip())
            self.sub_label.setVisible(True)
        else:
            self.sub_label.setText("")
            self.sub_label.setVisible(False)

        self._render_left_logos(branding)
        self._render_logo(branding)
        self._balance_wings()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._balance_wings()

    def sizeHint(self) -> QSize:
        """HeaderWidget maintains invariant height across all logo sizes."""
        return QSize(super().sizeHint().width(), HEADER_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """HeaderWidget minimum size hint is fixed at HEADER_HEIGHT."""
        return QSize(0, HEADER_HEIGHT)

    def _render_left_logos(self, branding: BrandingConfig) -> None:
        """
        Render the left corporate logos (c1 and c2) and manage the subtle divider.
        Divider is visible only when both left logos are active and successfully loaded.
        """
        left_configs = getattr(branding, "left_logos", []) or []

        # Left logo 1
        pm1 = None
        if len(left_configs) > 0 and left_configs[0].enabled and left_configs[0].file:
            p1 = resolve_asset_path(left_configs[0].file, self.project_root)
            pm1 = _render_pixmap_safe(p1, max_w=LEFT_LOGO_MAX_WIDTH, max_h=LEFT_LOGO_MAX_HEIGHT)

        if pm1 is not None:
            self.left_logo_1_label.setPixmap(pm1)
            self.left_logo_1_label.setFixedSize(pm1.size())
            self.left_logo_1_label.setVisible(True)
        else:
            self.left_logo_1_label.clear()
            self.left_logo_1_label.setFixedSize(0, 0)
            self.left_logo_1_label.setVisible(False)

        # Left logo 2
        pm2 = None
        if len(left_configs) > 1 and left_configs[1].enabled and left_configs[1].file:
            p2 = resolve_asset_path(left_configs[1].file, self.project_root)
            pm2 = _render_pixmap_safe(p2, max_w=LEFT_LOGO_MAX_WIDTH, max_h=LEFT_LOGO_MAX_HEIGHT)

        if pm2 is not None:
            self.left_logo_2_label.setPixmap(pm2)
            self.left_logo_2_label.setFixedSize(pm2.size())
            self.left_logo_2_label.setVisible(True)
        else:
            self.left_logo_2_label.clear()
            self.left_logo_2_label.setFixedSize(0, 0)
            self.left_logo_2_label.setVisible(False)

        # Divider shown only when both left logos are active and successfully displayed
        both_active = (pm1 is not None) and (pm2 is not None)
        self.left_divider_container.setVisible(both_active)

        # Container visibility and size
        visible_widths = []
        if pm1 is not None:
            visible_widths.append(pm1.width())
        if both_active:
            visible_widths.append(1)
        if pm2 is not None:
            visible_widths.append(pm2.width())

        if not visible_widths:
            self.left_container.setFixedWidth(0)
            self.left_container.setVisible(False)
        else:
            left_w = sum(visible_widths) + (len(visible_widths) - 1) * self.left_layout.spacing()
            self.left_container.setFixedWidth(left_w)
            self.left_container.setVisible(True)

    def _get_left_wing_width(self) -> int:
        """Calculate exact width occupied by the left wing widgets and spacing."""
        if self.left_container.isHidden():
            return 0
        return self.left_container.width()

    def _get_right_wing_width(self) -> int:
        """Calculate exact width occupied by the right logo viewport."""
        if self.logo_viewport.isHidden():
            return 0
        return self.logo_viewport.width()

    def _balance_wings(self) -> None:
        """
        Dynamically adjust left and right balance widgets to ensure the center container
        remains mathematically centered relative to the whole header window.
        """
        left_w = self._get_left_wing_width()
        right_w = self._get_right_wing_width()

        if left_w > right_w:
            self.right_balance.setFixedWidth(left_w - right_w)
            self.left_balance.setFixedWidth(0)
        elif right_w > left_w:
            self.left_balance.setFixedWidth(right_w - left_w)
            self.right_balance.setFixedWidth(0)
        else:
            self.left_balance.setFixedWidth(0)
            self.right_balance.setFixedWidth(0)

    def _render_logo(self, branding: BrandingConfig) -> None:
        """
        Render the right branding logo inside the viewport preserving exact aspect ratio.
        PROTECTED REGION:
        The rendered logo may scale up to VIEWPORT_HEIGHT, but will never force
        the viewport or parent header to grow.
        """
        if not branding.logo_enabled:
            self.logo_label.setVisible(False)
            self.logo_viewport.setVisible(False)
            self.logo_viewport.setFixedWidth(0)
            self.active_logo_path = None
            return

        if not branding.logo_file:
            self.logo_label.setVisible(False)
            self.logo_viewport.setVisible(False)
            self.logo_viewport.setFixedWidth(0)
            self.active_logo_path = None
            return

        resolved = resolve_asset_path(branding.logo_file, self.project_root)
        if not resolved.exists():
            logger.warning("Branding logo file not found: %s", resolved)
            self.logo_label.setVisible(False)
            self.logo_viewport.setVisible(False)
            self.logo_viewport.setFixedWidth(0)
            self.active_logo_path = None
            return

        # Constrain rendered dimensions strictly to available viewport geometry
        available_h = VIEWPORT_HEIGHT
        available_w = VIEWPORT_MAX_WIDTH

        requested_size = (
            int(branding.logo_size)
            if branding.logo_size and int(branding.logo_size) > 0
            else available_h
        )

        target_max_h = min(requested_size, available_h)
        ext = resolved.suffix.lower()

        try:
            if ext == ".svg":
                from PySide6.QtSvg import QSvgRenderer
                renderer = QSvgRenderer(str(resolved))
                if not renderer.isValid():
                    logger.warning("Invalid SVG branding logo file: %s", resolved)
                    self.logo_label.setVisible(False)
                    self.logo_viewport.setVisible(False)
                    self.active_logo_path = None
                    return

                def_sz = renderer.defaultSize()
                aspect = (def_sz.width() / def_sz.height()) if def_sz.height() > 0 else 1.0
                target_h = target_max_h
                target_w = max(1, int(target_h * aspect))
                if target_w > available_w:
                    target_w = available_w
                    target_h = max(1, int(target_w / aspect))

                pm = QPixmap(target_w, target_h)
                pm.fill(Qt.transparent)
                painter = QPainter(pm)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)
                renderer.render(painter)
                painter.end()
            else:
                pm_raw = QPixmap(str(resolved))
                if pm_raw.isNull():
                    logger.warning("Failed to load raster branding logo file: %s", resolved)
                    self.logo_label.setVisible(False)
                    self.logo_viewport.setVisible(False)
                    self.active_logo_path = None
                    return

                aspect = (pm_raw.width() / pm_raw.height()) if pm_raw.height() > 0 else 1.0
                target_h = target_max_h
                target_w = max(1, int(target_h * aspect))
                if target_w > available_w:
                    target_w = available_w
                    target_h = max(1, int(target_w / aspect))

                pm = pm_raw.scaled(
                    target_w, target_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            actual_w = pm.width()
            actual_h = pm.height()
            self.logo_viewport.setFixedWidth(actual_w)
            self.logo_label.setFixedSize(actual_w, actual_h)
            self.logo_label.setPixmap(pm)
            self.logo_label.setVisible(True)
            self.logo_viewport.setVisible(True)
            self.active_logo_path = resolved

        except Exception as exc:
            logger.warning("Failed to render branding logo from %s: %s", resolved, exc)
            self.logo_label.setVisible(False)
            self.logo_viewport.setVisible(False)
            self.logo_viewport.setFixedWidth(0)
            self.active_logo_path = None
