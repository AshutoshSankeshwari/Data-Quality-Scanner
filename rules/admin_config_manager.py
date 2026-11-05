"""
rules/admin_config_manager.py
Administrative configuration management utility for Data Quality Scanner V2.5.
Responsible for configuration write and update operations, asset import orchestration,
and comment-preserving modifications to config/admin_config.yaml.
"""
from __future__ import annotations
import logging
import re
import shutil
from pathlib import Path
from typing import Any
import yaml

from core.models import BrandingConfig
from rules.config_loader import get_project_root, load_branding_config, resolve_asset_path

logger = logging.getLogger(__name__)

SUPPORTED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg"}


class AdminConfigError(Exception):
    """Raised when an administrative configuration operation fails."""
    pass


def _validate_image_file(file_path: Path) -> None:
    """Validate that the given file exists, has a supported extension, and contains valid image data."""
    if not file_path.exists():
        raise AdminConfigError(f"Logo file not found: {file_path}")
    if not file_path.is_file():
        raise AdminConfigError(f"Logo path is not a file: {file_path}")

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_LOGO_EXTENSIONS:
        raise AdminConfigError(
            f"Unsupported logo format '{ext}'. Supported formats: {sorted(SUPPORTED_LOGO_EXTENSIONS)}"
        )

    # Validate image content with Qt
    try:
        if ext == ".svg":
            from PySide6.QtSvg import QSvgRenderer
            renderer = QSvgRenderer(str(file_path))
            if not renderer.isValid():
                raise AdminConfigError(f"File '{file_path.name}' is not a valid or readable SVG image.")
        else:
            from PySide6.QtGui import QImageReader
            reader = QImageReader(str(file_path))
            if not reader.canRead():
                raise AdminConfigError(f"File '{file_path.name}' is not a valid or readable raster image.")
    except ImportError:
        # If running in environment without GUI bindings, fallback to basic size check
        if file_path.stat().st_size == 0:
            raise AdminConfigError(f"File '{file_path.name}' is empty.")


def update_admin_branding_logo(
    admin_config_path: str | Path,
    logo_file_rel: str,
    enabled: bool = True,
) -> None:
    """
    Update the logo file path and enabled status under branding in admin_config.yaml.
    Preserves all comments, existing section headers, and formatting.
    """
    path = Path(admin_config_path)
    if not path.exists():
        raise AdminConfigError(f"Admin configuration file not found: {path}")

    content = path.read_text(encoding="utf-8")

    # Format values for YAML
    enabled_str = "true" if enabled else "false"
    # Ensure forward slashes for cross-platform YAML portability
    clean_logo_file = str(logo_file_rel).replace("\\", "/")

    if "branding:" in content:
        # Update enabled if present under logo
        if re.search(r"(logo:\s*\n(?:\s+#[^\n]*\n)*\s+enabled:\s*)[^\n]+", content):
            content = re.sub(
                r"(logo:\s*\n(?:\s+#[^\n]*\n)*\s+enabled:\s*)[^\n]+",
                rf"\g<1>{enabled_str}",
                content,
            )
        # Update file if present under logo
        if re.search(r"(logo:\s*\n(?:[^\n]*\n)*?\s+file:\s*)[^\n]+", content):
            content = re.sub(
                r"(\s+file:\s*)[^\n]+",
                rf'\g<1>"{clean_logo_file}"',
                content,
                count=1,
            )
        else:
            # Add file and enabled under logo if missing
            content = re.sub(
                r"(branding:\s*\n)",
                rf'\g<1>  logo:\n    enabled: {enabled_str}\n    file: "{clean_logo_file}"\n',
                content,
            )
    else:
        # Append clean branding section
        branding_block = (
            "\n\n# -----------------------------------------------------------------------------\n"
            "# 9. Application & Dashboard Branding Configuration\n"
            "# -----------------------------------------------------------------------------\n"
            "branding:\n"
            '  title: "Data Quality Scanner"\n'
            '  description: "Pre-Migration Data Quality Assessment · V2"\n'
            "  logo:\n"
            f"    enabled: {enabled_str}\n"
            f'    file: "{clean_logo_file}"\n'
            "    size: 56\n"
        )
        content += branding_block

    # Pre-validate YAML syntax before writing to disk
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as err:
        raise AdminConfigError(f"Failed to update {path}: resulting YAML is invalid: {err}")

    path.write_text(content, encoding="utf-8")
    logger.info("Updated branding logo in %s -> %s (enabled=%s)", path, clean_logo_file, enabled)


def update_admin_branding(
    admin_config_path: str | Path,
    branding_updates: dict[str, Any],
) -> None:
    """
    Update top-level branding attributes (title, description, logo) in admin_config.yaml.
    Preserves comments and formatting where possible.
    """
    path = Path(admin_config_path)
    if not path.exists():
        raise AdminConfigError(f"Admin configuration file not found: {path}")

    content = path.read_text(encoding="utf-8")

    if "title" in branding_updates:
        val = str(branding_updates["title"]).replace('"', '\\"')
        if re.search(r"(\s+title:\s*)[^\n]+", content):
            content = re.sub(r"(\s+title:\s*)[^\n]+", rf'\g<1>"{val}"', content, count=1)

    if "description" in branding_updates:
        val = str(branding_updates["description"]).replace('"', '\\"')
        if re.search(r"(\s+description:\s*)[^\n]+", content):
            content = re.sub(r"(\s+description:\s*)[^\n]+", rf'\g<1>"{val}"', content, count=1)

    if "logo" in branding_updates and isinstance(branding_updates["logo"], dict):
        logo_data = branding_updates["logo"]
        if "enabled" in logo_data:
            en_str = "true" if logo_data["enabled"] else "false"
            content = re.sub(r"(\s+enabled:\s*)[^\n]+", rf"\g<1>{en_str}", content, count=1)
        if "file" in logo_data:
            f_str = str(logo_data["file"]).replace("\\", "/")
            content = re.sub(r"(\s+file:\s*)[^\n]+", rf'\g<1>"{f_str}"', content, count=1)
        if "size" in logo_data:
            s_val = int(logo_data["size"])
            content = re.sub(r"(\s+size:\s*)[^\n]+", rf"\g<1>{s_val}", content, count=1)

    # Pre-validate
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as err:
        raise AdminConfigError(f"Resulting YAML after branding update is invalid: {err}")

    path.write_text(content, encoding="utf-8")


def import_branding_logo(
    source_path: str | Path,
    project_root: Path | None = None,
    admin_config_path: Path | None = None,
    overwrite: bool = False,
    replace_active: bool = False,
) -> BrandingConfig:
    """
    Orchestrate logo import:
    1. Validate source file format and readability.
    2. Handle collision policy:
       - If overwrite=False and target exists: generate sequential unique filename (<stem>_<n>.<ext>).
       - If overwrite=True: overwrite target file in place.
       - If replace_active=True: delete previous active file if it has a different filename (Option A).
    3. Copy asset into <project_root>/assets/branding/<filename>.
    4. Call update_admin_branding_logo to persist relative path in admin_config.yaml.
    5. Call load_branding_config via the read path to reload and return fresh BrandingConfig.
    """
    src = Path(source_path)
    _validate_image_file(src)

    root = Path(project_root) if project_root is not None else get_project_root()
    adm_cfg = (
        Path(admin_config_path)
        if admin_config_path is not None
        else (root / "config" / "admin_config.yaml")
    )

    target_dir = root / "assets" / "branding"
    target_dir.mkdir(parents=True, exist_ok=True)

    src_name = src.name
    target_file = target_dir / src_name

    # Determine currently active logo file to support Option A clean deletion if replacing active
    old_active_path: Path | None = None
    if replace_active and adm_cfg.exists():
        try:
            cur_branding = load_branding_config(adm_cfg)
            old_active_path = resolve_asset_path(cur_branding.logo_file, root)
        except Exception:
            old_active_path = None

    if overwrite:
        # In-place overwrite / replacement
        final_target = target_file
        # If replacing active and active is a different file in assets/branding/, delete old asset
        if (
            replace_active
            and old_active_path
            and old_active_path.exists()
            and old_active_path.resolve() != final_target.resolve()
            and target_dir.resolve() in old_active_path.resolve().parents
        ):
            try:
                old_active_path.unlink()
                logger.info("Deleted previous active branding logo: %s", old_active_path)
            except Exception as exc:
                logger.warning("Failed to delete previous active branding logo %s: %s", old_active_path, exc)
    else:
        # Safe collision handling: generate unique filename if target exists
        if target_file.exists():
            stem = src.stem
            suffix = src.suffix.lower()
            counter = 1
            while (target_dir / f"{stem}_{counter}{suffix}").exists():
                counter += 1
            final_target = target_dir / f"{stem}_{counter}{suffix}"
            logger.info("Asset collision detected for '%s'; saving as unique version '%s'", src_name, final_target.name)
        else:
            final_target = target_file

    # Copy source into project assets
    shutil.copy2(src, final_target)
    logger.info("Copied branding logo from %s to %s", src, final_target)

    # Update admin_config.yaml with project-relative path
    rel_path = f"assets/branding/{final_target.name}"
    update_admin_branding_logo(adm_cfg, rel_path, enabled=True)

    # Reload fresh branding config via the canonical read path
    return load_branding_config(adm_cfg)
