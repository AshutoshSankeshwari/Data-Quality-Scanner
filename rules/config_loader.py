"""
rules/config_loader.py
Loads and validates YAML configuration files (User config.yaml & Admin admin_config.yaml).
Returns typed AnalysisConfig objects the service layer can consume directly.
"""
from __future__ import annotations
import hashlib
import logging
from pathlib import Path
from typing import Any
import yaml

from core.service import AnalysisConfig
from core.models import BrandingConfig, LeftLogoConfig

logger = logging.getLogger(__name__)

DEFAULT_LOGO_SIZE = 56
MIN_LOGO_SIZE = 1


class ConfigError(Exception):
    """Raised when a configuration file is missing, malformed, or invalid."""
    pass


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML in '{path}': {e}")


VALID_CHECKS = {
    "duplicates", "nulls", "mandatory_fields", "whitespace",
    "special_chars", "patterns", "dates", "relationships",
}


def load_v2_config(
    config_path: str | Path,
    admin_config_path: str | Path | None = None,
) -> dict:
    """
    Load and validate user configuration (config.yaml) and optional admin configuration (admin_config.yaml).
    Merges user business rules with technical/system parameters.
    """
    user_path = Path(config_path)
    user_data = _load_yaml(user_path)
    if not isinstance(user_data, dict):
        raise ConfigError(f"Configuration file '{user_path}' must be a YAML mapping, got: {type(user_data)}")

    # 1. Resolve and load admin config if present
    admin_data: dict = {}
    if admin_config_path is not None:
        adm_path = Path(admin_config_path)
        if adm_path.exists():
            admin_data = _load_yaml(adm_path)
            if not isinstance(admin_data, dict):
                raise ConfigError(f"Admin configuration file '{adm_path}' must be a YAML mapping, got: {type(admin_data)}")
    else:
        default_admin_path = user_path.parent / "admin_config.yaml"
        if default_admin_path.exists():
            admin_data = _load_yaml(default_admin_path) or {}

    # Merge admin settings into merged_data (user settings take precedence for overlapping business rules)
    merged = {}

    # Default technical parameters
    merged["checks"] = admin_data.get("checks", user_data.get("checks", {"enabled": list(VALID_CHECKS)}))
    merged["null_rules"] = admin_data.get("null_rules", user_data.get("null_rules", {"high_threshold": 20.0, "medium_threshold": 5.0}))
    merged["pattern_rules"] = admin_data.get("pattern_rules", user_data.get("pattern_rules", {"min_cluster_size": 2, "max_cardinality_ratio": 0.95, "exclude_columns": []}))
    merged["scoring"] = admin_data.get("scoring", user_data.get("scoring", {
        "severity_weights": {"critical": 15.0, "high": 8.0, "medium": 3.0, "low": 1.0},
        "readiness_thresholds": {"ready": 90, "minor_cleansing": 75, "needs_cleansing": 50},
    }))
    merged["row_count_warning_threshold"] = admin_data.get(
        "row_count_warning_threshold",
        user_data.get("row_count_warning_threshold", 500_000),
    )

    # Special characters: admin anomaly characters + user/admin presets & rules
    admin_sc = admin_data.get("special_chars", {})
    user_sc = user_data.get("special_chars", {})
    merged["special_chars"] = {
        "anomaly_characters": admin_sc.get("anomaly_characters", user_sc.get("anomaly_characters", ["$", "@", "#", "%", "&", "*"])),
        "presets": user_sc.get("presets", admin_sc.get("presets", {})),
        "field_rules": user_sc.get("field_rules", {}),
    }

    # Duplicate rules: admin thresholds + user duplicate key sets
    admin_dup = admin_data.get("duplicate_rules", {})
    user_dup = user_data.get("duplicate_rules", {})
    merged["duplicate_rules"] = {
        "key_sets": user_dup.get("key_sets", []),
        "thresholds": admin_dup.get("thresholds", user_dup.get("thresholds", {"high": 5.0, "medium": 1.0})),
    }

    # User business rules
    merged["datasets"] = user_data.get("datasets", {})
    merged["mandatory_fields"] = user_data.get("mandatory_fields", {})
    merged["field_character_rules"] = user_data.get("field_character_rules", {})
    merged["date_rules"] = user_data.get("date_rules", {"accepted_formats": ["%Y-%m-%d", "%m/%d/%Y"], "column_hints": []})
    merged["relationships"] = user_data.get("relationships", [])

    # 2. Validate checks.enabled
    checks_cfg = merged.get("checks", {})
    if isinstance(checks_cfg, dict) and "enabled" in checks_cfg:
        enabled = checks_cfg["enabled"]
        if not isinstance(enabled, list):
            raise ConfigError("'checks.enabled' must be a list of check names.")
        unknown = set(enabled) - VALID_CHECKS
        if unknown:
            raise ConfigError(
                f"Unknown check name(s): {sorted(unknown)}. "
                f"Valid checks: {sorted(VALID_CHECKS)}"
            )

    # 3. Validate scoring readiness thresholds
    scoring = merged.get("scoring", {})
    if isinstance(scoring, dict):
        thresholds = scoring.get("readiness_thresholds", {})
        if isinstance(thresholds, dict) and all(k in thresholds for k in ("ready", "minor_cleansing", "needs_cleansing")):
            ready = thresholds["ready"]
            minor = thresholds["minor_cleansing"]
            needs = thresholds["needs_cleansing"]
            if not (ready > minor > needs):
                raise ConfigError(
                    f"Readiness thresholds must be in descending order: "
                    f"ready ({ready}) > minor_cleansing ({minor}) > needs_cleansing ({needs})"
                )

    # 4. Validate relationships list format
    rels = merged.get("relationships", [])
    if isinstance(rels, list):
        required_keys = {"parent_dataset", "parent_key", "child_dataset", "child_key"}
        for i, rel in enumerate(rels):
            if isinstance(rel, dict):
                missing = required_keys - set(rel.keys())
                if missing:
                    raise ConfigError(f"Relationship #{i + 1} is missing required keys: {sorted(missing)}")

    return merged


def get_config_hash(
    config_path: str | Path,
    admin_config_path: str | Path | None = None,
) -> str:
    """
    Return a deterministic SHA-256 hash of the configuration content (user config + admin config).
    Changing either file changes the effective configuration hash.
    """
    user_path = Path(config_path)
    if not user_path.exists():
        return "none"

    hasher = hashlib.sha256()
    try:
        hasher.update(user_path.read_bytes())
    except Exception:
        return "unknown"

    # Also incorporate admin config if present
    if admin_config_path is not None:
        adm_path = Path(admin_config_path)
        if adm_path.exists():
            try:
                hasher.update(b"|admin|")
                hasher.update(adm_path.read_bytes())
            except Exception:
                pass
    else:
        default_adm = user_path.parent / "admin_config.yaml"
        if default_adm.exists():
            try:
                hasher.update(b"|admin|")
                hasher.update(default_adm.read_bytes())
            except Exception:
                pass

    return hasher.hexdigest()[:12]


def build_analysis_config_from_v2(
    config_path: str | Path | None,
    mandatory_fields_profile: str | None = None,
    admin_config_path: str | Path | None = None,
) -> AnalysisConfig:
    """
    Build an AnalysisConfig instance directly from configuration files.
    Translates user business rules and admin parameters into AnalysisConfig.
    Gracefully falls back to default AnalysisConfig() if config_path is None or non-existent.
    """
    if config_path is None or not Path(config_path).exists():
        return AnalysisConfig()

    cfg_data = load_v2_config(config_path, admin_config_path=admin_config_path)

    # 1. Resolve Mandatory Fields & Duplicate Keys from datasets: or legacy structures
    mandatory_fields: list[str] = []
    dup_key_sets: list[list[str]] = []

    datasets_cfg = cfg_data.get("datasets", {})
    if isinstance(datasets_cfg, dict) and datasets_cfg:
        # User defined datasets: {Dataset_Name: {mandatory_fields: [...], duplicate_keys: [...]}}
        target_profile = None
        if mandatory_fields_profile and mandatory_fields_profile in datasets_cfg:
            target_profile = datasets_cfg[mandatory_fields_profile]
        else:
            first_ds = next(iter(datasets_cfg.values()))
            if isinstance(first_ds, dict):
                target_profile = first_ds

        if isinstance(target_profile, dict):
            # Extract mandatory fields
            mf_list = target_profile.get("mandatory_fields", [])
            if isinstance(mf_list, list):
                mandatory_fields = [str(f) for f in mf_list]

            # Extract duplicate keys and normalize to list of lists: [["Col1"], ["Col2"]]
            dk_list = target_profile.get("duplicate_keys", [])
            if isinstance(dk_list, list):
                for dk in dk_list:
                    if isinstance(dk, list):
                        dup_key_sets.append([str(c) for c in dk])
                    elif isinstance(dk, str):
                        dup_key_sets.append([dk])
    else:
        # Fallback to top-level mandatory_fields: mapping/list
        mandatory_fields_raw = cfg_data.get("mandatory_fields", {})
        if isinstance(mandatory_fields_raw, dict):
            if mandatory_fields_profile and mandatory_fields_profile in mandatory_fields_raw:
                mandatory_fields = list(mandatory_fields_raw[mandatory_fields_profile])
            elif mandatory_fields_raw:
                first_profile = next(iter(mandatory_fields_raw.values()))
                mandatory_fields = list(first_profile) if isinstance(first_profile, list) else []
        elif isinstance(mandatory_fields_raw, list):
            mandatory_fields = list(mandatory_fields_raw)

        # Fallback to top-level duplicate_rules.key_sets:
        dup_cfg = cfg_data.get("duplicate_rules", {})
        raw_key_sets = dup_cfg.get("key_sets", [])
        if isinstance(raw_key_sets, list):
            for ks in raw_key_sets:
                if isinstance(ks, list):
                    dup_key_sets.append([str(c) for c in ks])
                elif isinstance(ks, str):
                    dup_key_sets.append([ks])

    # 2. Checks master toggle
    checks_cfg = cfg_data.get("checks", {})
    enabled_checks = checks_cfg.get("enabled") if isinstance(checks_cfg, dict) else None

    # 3. Special characters & character rules
    sc_cfg = cfg_data.get("special_chars", {})
    presets = sc_cfg.get("presets", {})
    field_rules = cfg_data.get("field_character_rules") or sc_cfg.get("field_rules", {})
    anomaly_chars = sc_cfg.get("anomaly_characters", ["$", "@", "#", "%", "&", "*"])

    # 4. Duplicate thresholds
    dup_cfg = cfg_data.get("duplicate_rules", {})
    dup_thresholds = dup_cfg.get("thresholds", {})
    dup_high = float(dup_thresholds.get("high", 5.0))
    dup_med = float(dup_thresholds.get("medium", 1.0))

    # 5. Null thresholds
    null_cfg = cfg_data.get("null_rules", {})
    null_high = float(null_cfg.get("high_threshold", 20.0))
    null_med = float(null_cfg.get("medium_threshold", 5.0))

    # 6. Pattern rules
    pat_cfg = cfg_data.get("pattern_rules", {})
    pat_exclude = pat_cfg.get("exclude_columns", [])
    pat_min_cluster = int(pat_cfg.get("min_cluster_size", 2))
    pat_max_card = float(pat_cfg.get("max_cardinality_ratio", 0.95))

    # 7. Date rules
    date_cfg = cfg_data.get("date_rules", {})
    accepted_dates = date_cfg.get("accepted_formats")
    date_hints = date_cfg.get("column_hints") or cfg_data.get("date_column_hints")

    # 8. Relationships
    relationships = cfg_data.get("relationships", [])

    # 9. Scoring parameters
    scoring = cfg_data.get("scoring", {})
    severity_weights = scoring.get("severity_weights")
    thresholds = scoring.get("readiness_thresholds")

    row_warning = int(cfg_data.get("row_count_warning_threshold", 500_000))

    return AnalysisConfig(
        enabled_checks=enabled_checks,
        mandatory_fields=mandatory_fields,
        duplicate_key_sets=dup_key_sets,
        duplicate_high_threshold=dup_high,
        duplicate_medium_threshold=dup_med,
        field_character_rules=field_rules,
        character_rule_presets=presets,
        anomaly_characters=anomaly_chars,
        date_columns=None,
        accepted_date_formats=accepted_dates,
        date_column_hints=date_hints,
        pattern_exclude_columns=pat_exclude,
        min_pattern_cluster_size=pat_min_cluster,
        max_cardinality_ratio=pat_max_card,
        relationships=relationships,
        severity_weights=severity_weights,
        readiness_thresholds=thresholds,
        null_high_threshold=null_high,
        null_medium_threshold=null_med,
        row_count_warning_threshold=row_warning,
    )


# ---------------------------------------------------------------------------
# Branding Configuration Loader (Read Path Only)
# ---------------------------------------------------------------------------

def get_project_root() -> Path:
    """
    Return the canonical project root directory based on the location of this module.
    Completely independent of the process current working directory (os.getcwd() / Path.cwd()).
    """
    return Path(__file__).resolve().parent.parent


def resolve_asset_path(rel_or_abs_path: str | Path, project_root: Path | None = None) -> Path:
    """
    Resolve an asset path against project root if relative.
    Guaranteed to resolve accurately even if cwd != project root.
    """
    p = Path(rel_or_abs_path)
    if p.is_absolute():
        return p
    root = project_root if project_root is not None else get_project_root()
    resolved = (root / p).resolve()
    if resolved.exists():
        return resolved
    # Fallback if path was specified as 'branding/...' instead of 'assets/branding/...'
    alt = (root / "assets" / p).resolve()
    if alt.exists():
        return alt
    return resolved


def load_branding_config(admin_config_path: str | Path | None = None) -> BrandingConfig:
    """
    Load, validate, and normalize branding configuration from admin_config.yaml.
    Guarantees safe fallbacks for missing files, invalid sizes, and defaults.
    Strictly read-only; does not write or mutate any files.
    """
    default_cfg = BrandingConfig()
    adm_path = (
        Path(admin_config_path)
        if admin_config_path is not None
        else (get_project_root() / "config" / "admin_config.yaml")
    )

    if not adm_path.exists():
        logger.debug("Admin config not found at %s, using default BrandingConfig", adm_path)
        return default_cfg

    try:
        data = _load_yaml(adm_path)
    except Exception as exc:
        logger.warning("Failed to load admin config from %s: %s. Using default BrandingConfig", adm_path, exc)
        return default_cfg

    if not isinstance(data, dict):
        return default_cfg

    branding_raw = data.get("branding")
    if not isinstance(branding_raw, dict):
        return default_cfg

    # Title: editable, non-empty fallback
    raw_title = branding_raw.get("title")
    title = str(raw_title).strip() if raw_title is not None and str(raw_title).strip() else default_cfg.title

    # Description: editable, allow empty string without breaking layout
    raw_desc = branding_raw.get("description")
    description = str(raw_desc).strip() if raw_desc is not None else default_cfg.description

    # Logo dictionary
    logo_dict = branding_raw.get("logo")
    if isinstance(logo_dict, dict):
        logo_enabled = bool(logo_dict.get("enabled", True))
        raw_file = logo_dict.get("file")
        logo_file = str(raw_file).strip() if raw_file is not None and str(raw_file).strip() else default_cfg.logo_file
        raw_size = logo_dict.get("size")
        try:
            size_int = int(raw_size)
            if size_int > 0:
                logo_size = size_int
            else:
                logger.warning(
                    "Branding logo size %s must be positive. Falling back to default %d.",
                    raw_size, DEFAULT_LOGO_SIZE,
                )
                logo_size = DEFAULT_LOGO_SIZE
        except (ValueError, TypeError):
            if raw_size is not None:
                logger.warning(
                    "Invalid branding logo size '%s'. Falling back to default %d.",
                    raw_size, DEFAULT_LOGO_SIZE,
                )
            logo_size = DEFAULT_LOGO_SIZE
    else:
        logo_enabled = default_cfg.logo_enabled
        logo_file = default_cfg.logo_file
        logo_size = default_cfg.logo_size

    # Left logos list
    left_logos: list[LeftLogoConfig] = []
    raw_left_logos = branding_raw.get("left_logos")
    if isinstance(raw_left_logos, list):
        for item in raw_left_logos:
            if isinstance(item, dict):
                enabled = bool(item.get("enabled", True))
                raw_item_file = item.get("file")
                file_str = str(raw_item_file).strip() if raw_item_file is not None else ""
                left_logos.append(LeftLogoConfig(enabled=enabled, file=file_str))
            else:
                logger.warning("Ignoring malformed left-logo entry: %s (expected dict)", item)

    return BrandingConfig(
        title=title,
        description=description,
        logo_enabled=logo_enabled,
        logo_file=logo_file,
        logo_size=logo_size,
        left_logos=left_logos,
    )

