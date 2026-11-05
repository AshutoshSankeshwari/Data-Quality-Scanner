"""
tests/test_config_loader.py
Unit tests for V3 user/admin configuration loader and validation.
"""
import pytest
from pathlib import Path

from rules.config_loader import (
    load_v2_config,
    build_analysis_config_from_v2,
    get_config_hash,
    ConfigError,
)
from core.service import AnalysisConfig

CONFIG_DIR = Path(__file__).parent.parent / "config"


def test_load_non_existent_config():
    with pytest.raises(ConfigError, match="Configuration file not found"):
        load_v2_config("non_existent_config_file_xyz.yaml")


def test_load_v2_config_merges_user_and_admin():
    """Verify load_v2_config merges user business rules with admin technical parameters."""
    cfg_data = load_v2_config(CONFIG_DIR / "config.yaml")
    
    # User business rules
    assert "datasets" in cfg_data
    assert "Customer_Master" in cfg_data["datasets"]
    assert "relationships" in cfg_data
    assert "field_character_rules" in cfg_data
    
    # Admin technical parameters
    assert "checks" in cfg_data
    assert len(cfg_data["checks"]["enabled"]) == 8
    assert "scoring" in cfg_data
    assert cfg_data["scoring"]["severity_weights"]["critical"] == 15.0
    assert "$" in cfg_data["special_chars"]["anomaly_characters"]


def test_build_analysis_config_from_v3_datasets():
    """Verify build_analysis_config_from_v2 extracts mandatory fields and duplicate keys from datasets:."""
    cfg = build_analysis_config_from_v2(
        CONFIG_DIR / "config.yaml",
        mandatory_fields_profile="Customer_Master",
    )
    assert "duplicates" in cfg.enabled_checks
    assert "Customer_ID" in cfg.mandatory_fields
    assert "Email" in cfg.mandatory_fields
    
    # Duplicate keys must be normalized into list of lists
    assert ["Customer_ID"] in cfg.duplicate_key_sets
    assert ["Email"] in cfg.duplicate_key_sets
    
    # Special character rules & anomaly chars
    assert cfg.field_character_rules.get("Customer_ID") == "alpha_numeric_only"
    assert "$" in cfg.anomaly_characters
    assert "@" in cfg.anomaly_characters
    
    # Scoring severity weights
    assert cfg.severity_weights is not None
    assert cfg.severity_weights["critical"] == 15.0
    assert isinstance(cfg.relationships, list)


def test_duplicate_key_normalization(tmp_path):
    """Verify simple string duplicate keys and composite lists normalize correctly."""
    user_cfg = tmp_path / "config.yaml"
    user_cfg.write_text("""
datasets:
  MyDataset:
    mandatory_fields:
      - FieldA
    duplicate_keys:
      - SimpleKey1
      - [CompositeA, CompositeB]
""", encoding="utf-8")

    cfg = build_analysis_config_from_v2(user_cfg, mandatory_fields_profile="MyDataset")
    assert cfg.mandatory_fields == ["FieldA"]
    assert cfg.duplicate_key_sets == [["SimpleKey1"], ["CompositeA", "CompositeB"]]


def test_explicit_empty_checks_list(tmp_path):
    """Verify explicit empty checks list results in empty enabled_checks set (no checks)."""
    adm_cfg = tmp_path / "admin_config.yaml"
    adm_cfg.write_text("checks:\n  enabled: []\n", encoding="utf-8")
    user_cfg = tmp_path / "config.yaml"
    user_cfg.write_text("datasets:\n  DS:\n    mandatory_fields: [A]\n", encoding="utf-8")

    cfg = build_analysis_config_from_v2(user_cfg, admin_config_path=adm_cfg)
    assert cfg.enabled_checks == set()


def test_omitted_checks_list_uses_defaults():
    """Verify omitting enabled_checks defaults to all 8 standard checks."""
    cfg = AnalysisConfig()
    assert len(cfg.enabled_checks) == 8
    assert "duplicates" in cfg.enabled_checks
    assert "relationships" in cfg.enabled_checks


def test_v2_config_validation_unknown_check(tmp_path):
    bad_cfg = tmp_path / "bad_config.yaml"
    bad_cfg.write_text("checks:\n  enabled:\n    - non_existent_check\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unknown check name"):
        load_v2_config(bad_cfg)


def test_v2_config_validation_threshold_order(tmp_path):
    bad_cfg = tmp_path / "bad_thresh.yaml"
    bad_cfg.write_text(
        "scoring:\n  readiness_thresholds:\n    ready: 50\n    minor_cleansing: 75\n    needs_cleansing: 90\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="descending order"):
        load_v2_config(bad_cfg)


def test_v2_config_validation_relationship_missing_keys(tmp_path):
    bad_cfg = tmp_path / "bad_rel.yaml"
    bad_cfg.write_text(
        "relationships:\n  - parent_dataset: p\n    child_dataset: c\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="missing required keys"):
        load_v2_config(bad_cfg)


def test_get_config_hash_changes_with_either_file(tmp_path):
    """Verify get_config_hash changes if user config OR admin config is modified."""
    u_cfg = tmp_path / "config.yaml"
    a_cfg = tmp_path / "admin_config.yaml"
    
    u_cfg.write_text("datasets: {}\n", encoding="utf-8")
    a_cfg.write_text("scoring: {}\n", encoding="utf-8")
    
    h1 = get_config_hash(u_cfg, admin_config_path=a_cfg)
    assert len(h1) == 12
    
    # Modify user config
    u_cfg.write_text("datasets: {New: {}}\n", encoding="utf-8")
    h2 = get_config_hash(u_cfg, admin_config_path=a_cfg)
    assert h1 != h2
    
    # Modify admin config
    a_cfg.write_text("scoring: {severity_weights: {}}\n", encoding="utf-8")
    h3 = get_config_hash(u_cfg, admin_config_path=a_cfg)
    assert h2 != h3
