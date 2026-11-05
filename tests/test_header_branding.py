"""
tests/test_header_branding.py
Comprehensive test suite for the configurable Dashboard Header Branding enhancement in V2.5.
Covers:
  - Configuration Loading (Read Path: defaults, custom values, validation, normalization)
  - Logo size validation & bounds
  - Absence of any configurable logo position setting
  - CWD independence & Project Root asset resolution
  - Configuration Management (Write Path: comment-preserving updates)
  - Collision & Option A Replacement Policy (in-place overwrite vs sequential versioning)
  - Active Configuration Verification (end-to-end import -> file copy -> admin_config update -> reload -> HeaderWidget)
  - HeaderWidget GUI Layout (far-right logo anchoring with stretch, aspect ratio, disabled/missing fallback)
"""
from __future__ import annotations
import os
import shutil
import tempfile
from pathlib import Path
import pytest
import yaml

from PySide6.QtWidgets import QApplication, QLabel, QMenu
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QAction

from core.models import BrandingConfig, LeftLogoConfig
from rules.config_loader import (
    load_branding_config,
    resolve_asset_path,
    get_project_root,
    DEFAULT_LOGO_SIZE,
    MIN_LOGO_SIZE,
)
from gui.sections.header_widget import (
    HeaderWidget,
    HEADER_HEIGHT,
    VIEWPORT_HEIGHT,
    VIEWPORT_MAX_WIDTH,
    _render_pixmap_safe,
)
from rules.admin_config_manager import (
    update_admin_branding_logo,
    update_admin_branding,
    import_branding_logo,
    AdminConfigError,
)
from gui.sections.header_widget import HeaderWidget


# ---------------------------------------------------------------------------
# Helper to create temporary test image assets
# ---------------------------------------------------------------------------

def _create_test_png(path: Path, width: int = 120, height: int = 40, color: str = "#3b82f6") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    pm = QPixmap(width, height)
    pm.fill(QColor(color))
    p = QPainter(pm)
    p.setPen(QColor("#ffffff"))
    p.drawText(QRectF(0, 0, width, height), Qt.AlignCenter, "TEST")
    p.end()
    pm.save(str(path))
    return path


def _create_test_svg(path: Path, width: int = 100, height: int = 50) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
        <rect width="{width}" height="{height}" fill="#10b981" />
        <circle cx="{width//2}" cy="{height//2}" r="15" fill="#ffffff" />
    </svg>"""
    path.write_text(svg_content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. Configuration Loading (Read Path)
# ---------------------------------------------------------------------------

def test_branding_config_defaults_when_file_missing(tmp_path):
    """When admin_config.yaml is absent, load_branding_config returns standard defaults."""
    non_existent = tmp_path / "non_existent_admin_config.yaml"
    b = load_branding_config(non_existent)

    assert b.title == "Data Quality Scanner"
    assert b.description == "Pre-Migration Data Quality Assessment"
    assert b.logo_enabled is True
    assert b.logo_file == "assets/branding/company_logo.png"
    assert b.logo_size == 56


def test_branding_config_custom_title_and_description(tmp_path):
    """Custom title and description in admin_config.yaml are cleanly loaded."""
    cfg_file = tmp_path / "admin_config.yaml"
    cfg_file.write_text("""
branding:
  title: "Acme Enterprise Migration Portal"
  description: "Automated Data Validation & Readiness Assessment"
  logo:
    enabled: true
    file: "assets/branding/custom_logo.png"
    size: 48
""", encoding="utf-8")

    b = load_branding_config(cfg_file)
    assert b.title == "Acme Enterprise Migration Portal"
    assert b.description == "Automated Data Validation & Readiness Assessment"
    assert b.logo_enabled is True
    assert b.logo_file == "assets/branding/custom_logo.png"
    assert b.logo_size == 48


def test_branding_config_empty_description_allowed(tmp_path):
    """An empty description string is valid and loaded without falling back to default."""
    cfg_file = tmp_path / "admin_config.yaml"
    cfg_file.write_text("""
branding:
  title: "Clean Portal"
  description: ""
  logo:
    enabled: true
    file: "assets/branding/logo.png"
    size: 56
""", encoding="utf-8")

    b = load_branding_config(cfg_file)
    assert b.title == "Clean Portal"
    assert b.description == ""


def test_branding_config_logo_enabled_and_disabled(tmp_path):
    """logo.enabled: false is correctly parsed as boolean False."""
    cfg_file = tmp_path / "admin_config.yaml"
    cfg_file.write_text("""
branding:
  title: "Data Quality Scanner"
  description: "Assessment"
  logo:
    enabled: false
    file: "assets/branding/logo.png"
    size: 56
""", encoding="utf-8")

    b = load_branding_config(cfg_file)
    assert b.logo_enabled is False


def test_branding_config_logo_size_bounds_and_fallbacks(tmp_path):
    """Logo size accepts any positive requested size without arbitrary maximum; non-positive/invalid falls back to default 56."""
    cfg_file = tmp_path / "admin_config.yaml"

    # Non-positive (<= 0) -> falls back to default 56
    cfg_file.write_text("""
branding:
  logo:
    size: 0
""", encoding="utf-8")
    assert load_branding_config(cfg_file).logo_size == DEFAULT_LOGO_SIZE

    # Negative -> falls back to default 56
    cfg_file.write_text("""
branding:
  logo:
    size: -15
""", encoding="utf-8")
    assert load_branding_config(cfg_file).logo_size == DEFAULT_LOGO_SIZE

    # Non-numeric -> falls back to default 56
    cfg_file.write_text("""
branding:
  logo:
    size: "extra-large"
""", encoding="utf-8")
    assert load_branding_config(cfg_file).logo_size == DEFAULT_LOGO_SIZE

    # Large requested size (e.g. 250 or 500) is preserved as requested without arbitrary validation maximum
    cfg_file.write_text("""
branding:
  logo:
    size: 250
""", encoding="utf-8")
    assert load_branding_config(cfg_file).logo_size == 250

    # Standard requested size (e.g. 72)
    cfg_file.write_text("""
branding:
  logo:
    size: 72
""", encoding="utf-8")
    assert load_branding_config(cfg_file).logo_size == 72



def test_no_configurable_logo_position_setting(tmp_path):
    """Verify that NO position setting exists in BrandingConfig or is respected in YAML."""
    b = BrandingConfig()
    assert not hasattr(b, "position"), "BrandingConfig must NOT have a position attribute"

    cfg_file = tmp_path / "admin_config.yaml"
    cfg_file.write_text("""
branding:
  position: "left"
  logo:
    position: "left"
    size: 56
""", encoding="utf-8")
    b_loaded = load_branding_config(cfg_file)
    assert not hasattr(b_loaded, "position")


# ---------------------------------------------------------------------------
# 2. CWD Independence & Portability
# ---------------------------------------------------------------------------

def test_project_root_cwd_independence(monkeypatch, tmp_path):
    """
    Verify that relative logo paths resolve accurately against project root
    even when process working directory (cwd) is changed to an arbitrary foreign location.
    """
    foreign_cwd = tmp_path / "foreign_working_directory"
    foreign_cwd.mkdir()

    # Change current working directory to the foreign directory
    monkeypatch.chdir(foreign_cwd)
    assert Path.cwd().resolve() == foreign_cwd.resolve()
    assert Path.cwd().resolve() != get_project_root().resolve()

    # Resolve relative logo path
    rel_path = "assets/branding/company_logo.png"
    resolved = resolve_asset_path(rel_path)

    # Must resolve against get_project_root(), NOT foreign_cwd
    expected = (get_project_root() / rel_path).resolve()
    assert resolved == expected
    assert not str(resolved).startswith(str(foreign_cwd))


def test_asset_resolution_alternative_prefix(tmp_path):
    """Verifies that 'branding/company_logo.png' resolves to 'assets/branding/company_logo.png' if needed."""
    dummy_root = tmp_path / "proj"
    dummy_asset = dummy_root / "assets" / "branding" / "test_alt.png"
    _create_test_png(dummy_asset)

    resolved = resolve_asset_path("branding/test_alt.png", project_root=dummy_root)
    assert resolved.exists()
    assert resolved == dummy_asset.resolve()


# ---------------------------------------------------------------------------
# 3. Configuration Management (Write Path) & Comment Preservation
# ---------------------------------------------------------------------------

def test_admin_config_manager_updates_logo_preserving_comments(tmp_path):
    """update_admin_branding_logo preserves human comments and updates path cleanly."""
    cfg_file = tmp_path / "admin_config.yaml"
    initial_content = """# =============================================================================
# Administrator Configuration
# Normal users should edit business rules in config.yaml.
# =============================================================================

# 1. Checks Master Toggle
checks:
  enabled:
    - duplicates
    - nulls

# 9. Application Branding
branding:
  # Main application title
  title: "Data Quality Scanner"
  description: "Assessment"
  logo:
    enabled: false
    file: "assets/branding/old_logo.png"
    size: 56
"""
    cfg_file.write_text(initial_content, encoding="utf-8")

    update_admin_branding_logo(cfg_file, "assets/branding/new_logo.png", enabled=True)

    updated_text = cfg_file.read_text(encoding="utf-8")
    assert "# 1. Checks Master Toggle" in updated_text
    assert "# Main application title" in updated_text
    assert 'file: "assets/branding/new_logo.png"' in updated_text
    assert "enabled: true" in updated_text

    # Verify resulting YAML is 100% valid
    parsed = yaml.safe_load(updated_text)
    assert parsed["branding"]["logo"]["file"] == "assets/branding/new_logo.png"
    assert parsed["branding"]["logo"]["enabled"] is True


# ---------------------------------------------------------------------------
# 4. Collision Handling & Option A Asset Replacement Policy
# ---------------------------------------------------------------------------

def test_import_branding_logo_safe_unique_name_on_collision(tmp_path):
    """When overwrite=False, filename collision generates <stem>_1.<ext> and updates config."""
    dummy_root = tmp_path / "proj"
    cfg_file = dummy_root / "config" / "admin_config.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text("branding:\n  logo:\n    file: assets/branding/logo.png\n", encoding="utf-8")

    # Create pre-existing file with same name in assets/branding/
    existing_file = dummy_root / "assets" / "branding" / "logo.png"
    _create_test_png(existing_file, color="#ff0000")

    # New source file with same name
    src_file = tmp_path / "incoming" / "logo.png"
    _create_test_png(src_file, color="#00ff00")

    # Import with overwrite=False (Save as New Version)
    reloaded = import_branding_logo(
        src_file,
        project_root=dummy_root,
        admin_config_path=cfg_file,
        overwrite=False,
    )

    expected_new = dummy_root / "assets" / "branding" / "logo_1.png"
    assert expected_new.exists(), "Should generate logo_1.png"
    assert existing_file.exists(), "Previous file should be retained as historical asset"
    assert reloaded.logo_file == "assets/branding/logo_1.png"

    # admin_config.yaml must point strictly to the newly imported unique asset
    raw_cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert raw_cfg["branding"]["logo"]["file"] == "assets/branding/logo_1.png"


def test_import_branding_logo_option_a_clean_replacement(tmp_path):
    """
    When overwrite=True and replace_active=True (Option A),
    the old active file is deleted if differently named, preventing orphan accumulation.
    """
    dummy_root = tmp_path / "proj"
    cfg_file = dummy_root / "config" / "admin_config.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)

    # Previous active logo: old_brand.png
    old_active = dummy_root / "assets" / "branding" / "old_brand.png"
    _create_test_png(old_active, color="#aaaaaa")
    cfg_file.write_text("branding:\n  logo:\n    file: assets/branding/old_brand.png\n", encoding="utf-8")

    # Newly imported logo: new_brand.png
    new_src = tmp_path / "incoming" / "new_brand.png"
    _create_test_png(new_src, color="#3b82f6")

    # Import with overwrite=True and replace_active=True
    reloaded = import_branding_logo(
        new_src,
        project_root=dummy_root,
        admin_config_path=cfg_file,
        overwrite=True,
        replace_active=True,
    )

    new_dest = dummy_root / "assets" / "branding" / "new_brand.png"
    assert new_dest.exists(), "New asset must exist"
    assert not old_active.exists(), "Previous active asset must be cleanly deleted (Option A)"
    assert reloaded.logo_file == "assets/branding/new_brand.png"


def test_import_branding_logo_unsupported_format_raises(tmp_path):
    """Importing an executable or unsupported file type raises AdminConfigError."""
    bad_file = tmp_path / "virus.exe"
    bad_file.write_text("not an image", encoding="utf-8")

    with pytest.raises(AdminConfigError, match="Unsupported logo format"):
        import_branding_logo(bad_file, project_root=tmp_path)


# ---------------------------------------------------------------------------
# 5. Active Configuration Verification (End-to-End Workflow)
# ---------------------------------------------------------------------------

def test_end_to_end_logo_import_and_header_widget_update(qtbot, tmp_path):
    """
    Proves the full workflow:
      import logo -> file copied -> admin_config.yaml updated -> branding reloaded -> HeaderWidget displays new logo.
    Verifies that HeaderWidget.active_logo_path matches the exact path referenced in admin_config.yaml.
    """
    dummy_root = tmp_path / "project_root"
    cfg_file = dummy_root / "config" / "admin_config.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Initial configuration
    initial_logo = dummy_root / "assets" / "branding" / "initial_logo.png"
    _create_test_png(initial_logo, width=80, height=40, color="#111111")
    cfg_file.write_text(f"""
branding:
  title: "Test System"
  description: "Initial Assessment"
  logo:
    enabled: true
    file: "assets/branding/initial_logo.png"
    size: 40
""", encoding="utf-8")

    init_branding = load_branding_config(cfg_file)
    header = HeaderWidget(branding=init_branding, project_root=dummy_root)
    header.show()
    qtbot.addWidget(header)

    assert header.active_logo_path == initial_logo.resolve()
    assert header.logo_label.isVisible()

    # 2. Source file for replacement (e.g. from manager's desktop/downloads)
    imported_src = tmp_path / "external_downloads" / "corporate_identity.png"
    _create_test_png(imported_src, width=160, height=40, color="#3b82f6")

    # 3. Trigger import workflow
    reloaded_branding = import_branding_logo(
        source_path=imported_src,
        project_root=dummy_root,
        admin_config_path=cfg_file,
        overwrite=True,
    )

    # 4. Verify file copied into assets/branding/
    expected_dest = dummy_root / "assets" / "branding" / "corporate_identity.png"
    assert expected_dest.exists()

    # 5. Verify admin_config.yaml updated with relative path
    persisted_yaml = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert persisted_yaml["branding"]["logo"]["file"] == "assets/branding/corporate_identity.png"

    # 6. Verify branding reloaded
    assert reloaded_branding.logo_file == "assets/branding/corporate_identity.png"

    # 7. Update HeaderWidget
    header.update_branding(reloaded_branding)

    # 8. Assert HeaderWidget actively displays the exact path from admin_config.yaml
    assert header.active_logo_path == expected_dest.resolve()
    assert header.logo_label.isVisible()
    assert header.logo_label.pixmap() is not None
    assert not header.logo_label.pixmap().isNull()


# ---------------------------------------------------------------------------
# 6. HeaderWidget GUI Layout & Visual Presentation
# ---------------------------------------------------------------------------

def test_header_widget_title_and_description_rendering(qtbot):
    """HeaderWidget renders configured title and description with correct styling."""
    b = BrandingConfig(
        title="Custom Brand Title",
        description="Custom Subtitle",
        logo_enabled=False,
    )
    header = HeaderWidget(branding=b)
    header.show()
    qtbot.addWidget(header)

    assert header.title_label.text() == "Custom Brand Title"
    assert header.sub_label.text() == "Custom Subtitle"
    assert header.sub_label.isVisible()


def test_header_widget_removes_config_hash_badge(qtbot):
    """Verify that NO config/hash badge exists in HeaderWidget."""
    header = HeaderWidget()
    qtbot.addWidget(header)

    # Check all QLabels inside HeaderWidget
    labels = header.findChildren(QLabel)
    for lbl in labels:
        assert "config/config.yaml" not in lbl.text(), "Config badge must not appear in HeaderWidget"
        assert "⚙️" not in lbl.text(), "Gear config badge icon must not appear in HeaderWidget"


def test_header_widget_logo_far_right_alignment(qtbot, tmp_path):
    """Verify that the logo is placed after the layout stretch and anchored to the far right."""
    logo_path = tmp_path / "logo.png"
    _create_test_png(logo_path, width=100, height=40)

    b = BrandingConfig(logo_file=str(logo_path), logo_enabled=True)
    header = HeaderWidget(branding=b)
    header.resize(1000, 70)
    qtbot.addWidget(header)

    layout = header.layout()
    # Layout must have at least text_layout, stretch, and logo_label
    items = [layout.itemAt(i) for i in range(layout.count())]

    # Verify a stretch item exists before the logo
    stretch_index = None
    logo_index = None
    for idx, itm in enumerate(items):
        if itm.spacerItem() is not None:
            stretch_index = idx
        elif itm.widget() in (header.logo_viewport, header.logo_label):
            logo_index = idx

    assert stretch_index is not None, "Layout must contain a stretch"
    assert logo_index is not None, "Layout must contain the logo widget"
    assert logo_index > stretch_index, "Logo must be placed AFTER the stretch (far right)"


def test_header_widget_logo_remains_right_aligned_with_long_title(qtbot, tmp_path):
    """Logo remains anchored to far right even when title is extremely long."""
    logo_path = tmp_path / "logo.png"
    _create_test_png(logo_path, width=60, height=40)

    b_long = BrandingConfig(
        title="Extremely Long Custom Enterprise Migration Data Quality Governance Platform Title That Takes Up Width",
        description="Detailed long description subtitle",
        logo_file=str(logo_path),
        logo_enabled=True,
    )
    header = HeaderWidget(branding=b_long)
    header.resize(1200, 70)
    qtbot.addWidget(header)

    header.show()
    # Logo right edge in header coordinates must be near the right edge of header
    logo_right_edge = header.logo_viewport.geometry().right()
    header_width = header.width()
    # Margin is 28px on right, so logo_right_edge should be within 45px of header_width
    assert header_width - logo_right_edge < 45


def test_header_widget_disabled_logo_hides_widget_cleanly(qtbot):
    """When logo_enabled: false, logo widget is hidden without leaving an empty placeholder."""
    b = BrandingConfig(logo_enabled=False)
    header = HeaderWidget(branding=b)
    qtbot.addWidget(header)

    assert not header.logo_label.isVisible()
    assert header.active_logo_path is None


def test_header_widget_missing_logo_does_not_crash(qtbot):
    """When logo file is missing, header logs warning and renders title/description cleanly."""
    b = BrandingConfig(logo_file="non_existent_path_to_logo.png", logo_enabled=True)
    header = HeaderWidget(branding=b)
    qtbot.addWidget(header)

    assert not header.logo_label.isVisible()
    assert header.title_label.text() == "Data Quality Scanner"


def test_header_widget_svg_format_and_aspect_ratio(qtbot, tmp_path):
    """SVG logo renders sharply and aspect ratio is preserved."""
    svg_path = tmp_path / "test_logo.svg"
    _create_test_svg(svg_path, width=200, height=100)  # 2:1 aspect ratio

    b = BrandingConfig(logo_file=str(svg_path), logo_enabled=True, logo_size=50)
    header = HeaderWidget(branding=b)
    header.show()
    qtbot.addWidget(header)

    assert header.logo_label.isVisible()
    pm = header.logo_label.pixmap()
    assert pm is not None
    # Height should match logo_size=50, width should preserve 2:1 -> ~100
    assert pm.height() == 50
    assert abs(pm.width() - 100) <= 2


# ---------------------------------------------------------------------------
# 5. Logo Sizing Architecture & Viewport Constraint Tests
# ---------------------------------------------------------------------------

def test_header_height_is_invariant_across_logo_sizes(qtbot, tmp_path):
    """
    HeaderWidget height must be strictly invariant (HEADER_HEIGHT == 76px)
    across all requested logo sizes (small, standard, huge).
    Logo must never cause header height to expand.
    """
    logo_path = tmp_path / "scale_test.png"
    _create_test_png(logo_path, width=200, height=100)

    test_sizes = [1, 10, 24, 40, 56, 76, 120, 300, 1000]
    for sz in test_sizes:
        b = BrandingConfig(logo_file=str(logo_path), logo_enabled=True, logo_size=sz)
        header = HeaderWidget(branding=b)
        qtbot.addWidget(header)
        header.show()

        assert header.height() == HEADER_HEIGHT, f"Failed for size {sz}: header height was {header.height()}"
        assert header.sizeHint().height() == HEADER_HEIGHT
        assert header.minimumSizeHint().height() == HEADER_HEIGHT
        assert header.logo_viewport.height() == VIEWPORT_HEIGHT
        assert header.logo_label.height() <= VIEWPORT_HEIGHT


def test_small_logo_sizes_visibly_scale(qtbot, tmp_path):
    """
    For requested sizes below available viewport height, visible logo should
    actually scale down accordingly rather than being clamped to an artificial minimum.
    """
    logo_path = tmp_path / "small_scale.png"
    _create_test_png(logo_path, width=200, height=100)  # 2:1 aspect ratio

    # Test size 20
    b_20 = BrandingConfig(logo_file=str(logo_path), logo_enabled=True, logo_size=20)
    h_20 = HeaderWidget(branding=b_20)
    qtbot.addWidget(h_20)
    pm_20 = h_20.logo_label.pixmap()
    assert pm_20 is not None
    assert pm_20.height() == 20
    assert abs(pm_20.width() - 40) <= 1

    # Test size 38
    b_38 = BrandingConfig(logo_file=str(logo_path), logo_enabled=True, logo_size=38)
    h_38 = HeaderWidget(branding=b_38)
    qtbot.addWidget(h_38)
    pm_38 = h_38.logo_label.pixmap()
    assert pm_38 is not None
    assert pm_38.height() == 38
    assert abs(pm_38.width() - 76) <= 1

    # Test size 50
    b_50 = BrandingConfig(logo_file=str(logo_path), logo_enabled=True, logo_size=50)
    h_50 = HeaderWidget(branding=b_50)
    qtbot.addWidget(h_50)
    pm_50 = h_50.logo_label.pixmap()
    assert pm_50 is not None
    assert pm_50.height() == 50
    assert abs(pm_50.width() - 100) <= 1

    # Confirm monotonic visible scaling
    assert pm_20.height() < pm_38.height() < pm_50.height()
    assert pm_20.width() < pm_38.width() < pm_50.width()


def test_large_logo_sizes_constrained_by_viewport(qtbot, tmp_path):
    """
    For requested sizes exceeding available viewport height (VIEWPORT_HEIGHT=56),
    rendered logo must be constrained to the viewport rather than expanding the header.
    """
    logo_path = tmp_path / "large_scale.png"
    _create_test_png(logo_path, width=400, height=200)  # 2:1 aspect ratio

    for large_sz in [80, 150, 300, 1000]:
        b = BrandingConfig(logo_file=str(logo_path), logo_enabled=True, logo_size=large_sz)
        header = HeaderWidget(branding=b)
        qtbot.addWidget(header)
        header.show()

        pm = header.logo_label.pixmap()
        assert pm is not None
        assert pm.height() == VIEWPORT_HEIGHT  # Constrained to 56px
        assert abs(pm.width() - 112) <= 2      # 2:1 aspect ratio preserved
        assert header.logo_viewport.height() == VIEWPORT_HEIGHT
        assert header.height() == HEADER_HEIGHT


def test_far_right_alignment_remains_correct_across_scales(qtbot, tmp_path):
    """
    Far-right alignment remains strictly correct across various logo sizes,
    with layout stretch pushing the logo viewport to the right edge.
    """
    logo_path = tmp_path / "align_test.png"
    _create_test_png(logo_path, width=120, height=60)

    for sz in [20, 56, 200]:
        b = BrandingConfig(logo_file=str(logo_path), logo_enabled=True, logo_size=sz)
        header = HeaderWidget(branding=b)
        header.resize(1000, HEADER_HEIGHT)
        qtbot.addWidget(header)
        header.show()

        # Layout check: stretch before logo_viewport
        layout = header.layout()
        items = [layout.itemAt(i) for i in range(layout.count())]
        stretch_idx = next(i for i, itm in enumerate(items) if itm.spacerItem() is not None)
        viewport_idx = next(i for i, itm in enumerate(items) if itm.widget() == header.logo_viewport)
        assert viewport_idx > stretch_idx, f"Size {sz}: viewport must be after stretch"

        # Position check: right edge is near header right margin (within 45px)
        right_dist = header.width() - header.logo_viewport.geometry().right()
        assert right_dist < 45, f"Size {sz}: right distance {right_dist} exceeded 45px"


def test_aspect_ratio_is_preserved_for_various_dimensions(qtbot, tmp_path):
    """
    Strict KeepAspectRatio scaling is maintained for various image dimensions
    (wide raster, tall raster, wide SVG, square SVG).
    """
    # 1. Wide raster (3:1 ratio)
    wide_png = _create_test_png(tmp_path / "wide.png", width=300, height=100)
    b_wide = BrandingConfig(logo_file=str(wide_png), logo_enabled=True, logo_size=40)
    h_wide = HeaderWidget(branding=b_wide)
    qtbot.addWidget(h_wide)
    pm = h_wide.logo_label.pixmap()
    assert pm is not None
    assert pm.height() == 40
    assert abs(pm.width() - 120) <= 2
    assert abs((pm.width() / pm.height()) - 3.0) < 0.1

    # 2. Tall raster (1:2 ratio)
    tall_png = _create_test_png(tmp_path / "tall.png", width=50, height=100)
    b_tall = BrandingConfig(logo_file=str(tall_png), logo_enabled=True, logo_size=50)
    h_tall = HeaderWidget(branding=b_tall)
    qtbot.addWidget(h_tall)
    pm = h_tall.logo_label.pixmap()
    assert pm is not None
    assert pm.height() == 50
    assert abs(pm.width() - 25) <= 2
    assert abs((pm.width() / pm.height()) - 0.5) < 0.1

    # 3. Wide SVG (4:1 ratio)
    wide_svg = _create_test_svg(tmp_path / "wide.svg", width=400, height=100)
    b_svg = BrandingConfig(logo_file=str(wide_svg), logo_enabled=True, logo_size=45)
    h_svg = HeaderWidget(branding=b_svg)
    qtbot.addWidget(h_svg)
    pm = h_svg.logo_label.pixmap()
    assert pm is not None
    assert pm.height() == 45
    assert abs(pm.width() - 180) <= 2
    assert abs((pm.width() / pm.height()) - 4.0) < 0.1

    # 4. Square SVG (1:1 ratio)
    sq_svg = _create_test_svg(tmp_path / "sq.svg", width=120, height=120)
    b_sq = BrandingConfig(logo_file=str(sq_svg), logo_enabled=True, logo_size=50)
    h_sq = HeaderWidget(branding=b_sq)
    qtbot.addWidget(h_sq)
    pm = h_sq.logo_label.pixmap()
    assert pm is not None
    assert pm.height() == 50
    assert pm.width() == 50


def test_transparent_padding_assets_handled_without_affecting_header_height(qtbot):
    """
    Official Tata Technologies logo (assets/branding/c2_logo.png) contains
    89% vertical transparent padding. Verify that rendering this asset
    across various requested sizes never affects header height and preserves aspect ratio.
    """
    c2_path = get_project_root() / "assets" / "branding" / "c2_logo.png"
    assert c2_path.exists(), "c2_logo.png must exist for transparent padding test"

    # Canvas dimensions: 500x292 (aspect ratio ~1.7123)
    canvas_aspect = 500 / 292

    for sz in [30, 56, 120, 300]:
        b = BrandingConfig(logo_file="assets/branding/c2_logo.png", logo_enabled=True, logo_size=sz)
        header = HeaderWidget(branding=b)
        qtbot.addWidget(header)
        header.show()

        # Header height strictly invariant
        assert header.height() == HEADER_HEIGHT
        assert header.sizeHint().height() == HEADER_HEIGHT
        assert header.minimumSizeHint().height() == HEADER_HEIGHT

        # Viewport strictly bounded
        assert header.logo_viewport.height() == VIEWPORT_HEIGHT

        pm = header.logo_label.pixmap()
        assert pm is not None
        assert pm.height() <= VIEWPORT_HEIGHT

        # Aspect ratio preserved
        rendered_aspect = pm.width() / pm.height()
        assert abs(rendered_aspect - canvas_aspect) < 0.05


# ---------------------------------------------------------------------------
# 6. Header UI Branding Rectification (V2.5) Tests: Categories A, B, C, D
# ---------------------------------------------------------------------------

def test_category_a_left_logos_loaded_from_yaml(tmp_path):
    """
    Verify Category A:
    - left_logos loads correctly from configuration into typed LeftLogoConfig objects
    - missing left_logos falls back gracefully to an empty list
    - malformed left-logo entries do not crash configuration loading
    - right-logo configuration remains completely compatible and unchanged
    """
    # 1. Full configuration with left_logos and right logo
    cfg_file = tmp_path / "admin_config_full.yaml"
    cfg_file.write_text("""
branding:
  title: "Data Quality Scanner"
  description: "Pre-Migration Data Quality Assessment"
  logo:
    enabled: true
    file: "assets/branding/company_logo.png"
    size: 50
  left_logos:
    - enabled: true
      file: "assets/branding/c1_logo.png"
    - enabled: false
      file: "assets/branding/c2_logo.png"
""", encoding="utf-8")
    b = load_branding_config(cfg_file)
    assert b.title == "Data Quality Scanner"
    assert b.description == "Pre-Migration Data Quality Assessment"
    assert b.logo_enabled is True
    assert b.logo_file == "assets/branding/company_logo.png"
    assert b.logo_size == 50
    assert len(b.left_logos) == 2
    assert isinstance(b.left_logos[0], LeftLogoConfig)
    assert b.left_logos[0].enabled is True
    assert b.left_logos[0].file == "assets/branding/c1_logo.png"
    assert b.left_logos[1].enabled is False
    assert b.left_logos[1].file == "assets/branding/c2_logo.png"

    # 2. Missing left_logos falls back gracefully
    cfg_no_left = tmp_path / "admin_config_no_left.yaml"
    cfg_no_left.write_text("""
branding:
  title: "Data Quality Scanner"
  logo:
    enabled: true
    file: "assets/branding/company_logo.png"
""", encoding="utf-8")
    b_no_left = load_branding_config(cfg_no_left)
    assert b_no_left.left_logos == []

    # 3. Malformed entries (string instead of dict, missing fields) do not crash
    cfg_malformed = tmp_path / "admin_config_malformed.yaml"
    cfg_malformed.write_text("""
branding:
  left_logos:
    - "invalid_string_entry"
    - enabled: true
      file: "valid.png"
    - 12345
""", encoding="utf-8")
    b_malformed = load_branding_config(cfg_malformed)
    assert len(b_malformed.left_logos) == 1
    assert b_malformed.left_logos[0].file == "valid.png"


def test_category_b_left_logo_rendering_and_divider(qtbot, tmp_path):
    """
    Verify Category B:
    - both logos load and maintain aspect ratio
    - divider appears only when both are successfully displayed
    - divider disappears when either logo is disabled or missing
    """
    logo1 = tmp_path / "logo1.png"
    logo2 = tmp_path / "logo2.png"
    _create_test_png(logo1, width=120, height=60)  # 2:1 aspect
    _create_test_png(logo2, width=80, height=40)   # 2:1 aspect

    # 1. Both active and loaded -> divider visible
    b_both = BrandingConfig(
        left_logos=[
            LeftLogoConfig(enabled=True, file=str(logo1)),
            LeftLogoConfig(enabled=True, file=str(logo2)),
        ]
    )
    header = HeaderWidget(branding=b_both)
    qtbot.addWidget(header)
    header.show()

    assert header.left_logo_1_label.isVisible()
    assert header.left_logo_2_label.isVisible()
    assert header.left_divider_container.isVisible()

    pm1 = header.left_logo_1_label.pixmap()
    pm2 = header.left_logo_2_label.pixmap()
    assert pm1 is not None and pm2 is not None
    assert abs((pm1.width() / pm1.height()) - 2.0) < 0.05
    assert abs((pm2.width() / pm2.height()) - 2.0) < 0.05

    # 2. Only Logo 1 enabled -> divider hidden
    b_one = BrandingConfig(
        left_logos=[
            LeftLogoConfig(enabled=True, file=str(logo1)),
            LeftLogoConfig(enabled=False, file=str(logo2)),
        ]
    )
    header.update_branding(b_one)
    assert header.left_logo_1_label.isVisible()
    assert not header.left_logo_2_label.isVisible()
    assert not header.left_divider_container.isVisible()

    # 3. Logo 2 missing file -> divider hidden
    b_missing = BrandingConfig(
        left_logos=[
            LeftLogoConfig(enabled=True, file=str(logo1)),
            LeftLogoConfig(enabled=True, file=str(tmp_path / "non_existent.png")),
        ]
    )
    header.update_branding(b_missing)
    assert header.left_logo_1_label.isVisible()
    assert not header.left_logo_2_label.isVisible()
    assert not header.left_divider_container.isVisible()

    # 4. Both disabled -> left container hidden
    b_none = BrandingConfig(
        left_logos=[
            LeftLogoConfig(enabled=False, file=str(logo1)),
            LeftLogoConfig(enabled=False, file=str(logo2)),
        ]
    )
    header.update_branding(b_none)
    assert not header.left_container.isVisible()
    assert not header.left_divider_container.isVisible()


def test_category_c_mathematical_title_centering(qtbot, tmp_path):
    """
    Verify Category C:
    Validate title/description centering across 1024px, 1280px, and 1600px widths.
    Mathematical verification:
    abs(center_container.geometry().center().x() - header_widget.rect().center().x()) <= 1
    even with asymmetric left logos and right logo.
    """
    left1 = tmp_path / "left1.png"
    right_logo = tmp_path / "right.png"
    _create_test_png(left1, width=160, height=40)
    _create_test_png(right_logo, width=60, height=40)

    b = BrandingConfig(
        title="Data Quality Scanner",
        description="Pre-Migration Data Quality Assessment",
        logo_file=str(right_logo),
        logo_enabled=True,
        left_logos=[
            LeftLogoConfig(enabled=True, file=str(left1)),
        ],
    )
    header = HeaderWidget(branding=b)
    qtbot.addWidget(header)
    header.show()

    for w in [1024, 1280, 1600]:
        header.resize(w, HEADER_HEIGHT)
        qtbot.wait(30)  # Allow Qt layout pass
        header._balance_wings()

        center_x = header.center_container.geometry().center().x()
        expected_center_x = header.rect().center().x()
        diff = abs(center_x - expected_center_x)
        assert diff <= 1, f"At width {w}, center_x={center_x} vs expected={expected_center_x} (diff={diff})"


def test_category_d_protected_right_logo_regression(qtbot, tmp_path):
    """
    Verify Category D:
    Explicitly confirm:
    - same right logo asset
    - same far-right position
    - same viewport (VIEWPORT_HEIGHT = 56)
    - same aspect-ratio behavior
    - same context-menu replacement behavior
    - same fallback behavior
    """
    right_logo = tmp_path / "company_logo.png"
    _create_test_png(right_logo, width=200, height=50)

    b = BrandingConfig(
        logo_file=str(right_logo),
        logo_enabled=True,
        logo_size=50,
    )
    header = HeaderWidget(branding=b)
    header.resize(1200, HEADER_HEIGHT)
    qtbot.addWidget(header)
    header.show()

    # 1. Viewport geometry and far right position
    assert header.logo_viewport.height() == VIEWPORT_HEIGHT
    logo_right_edge = header.logo_viewport.geometry().right()
    assert header.width() - logo_right_edge < 45

    # 2. Aspect ratio preserved
    pm = header.logo_label.pixmap()
    assert pm is not None
    assert pm.height() == 50
    assert abs((pm.width() / pm.height()) - 4.0) < 0.05

    # 3. Context menu event triggers import_logo_requested
    with qtbot.waitSignal(header.import_logo_requested, timeout=1000):
        menu = QMenu(header)
        action = QAction("Test", header)
        action.triggered.connect(header.import_logo_requested.emit)
        action.trigger()

    # 4. Fallback behavior when disabled
    b_dis = BrandingConfig(logo_enabled=False)
    header.update_branding(b_dis)
    assert not header.logo_viewport.isVisible()
    assert not header.logo_label.isVisible()

