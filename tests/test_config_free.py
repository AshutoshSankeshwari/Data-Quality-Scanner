"""
tests/test_config_free.py
Automated test suite verifying that the scanner runs smoothly in config-free mode
when config/config.yaml is absent, non-existent, or moved.
"""
import pytest
import tempfile
import pandas as pd
from pathlib import Path
from PySide6.QtWidgets import QMessageBox

from rules.config_loader import build_analysis_config_from_v2, get_config_hash
from core.service import AnalysisService, AnalysisConfig
from batch_runner import run_batch
from gui.main_window import MainWindow

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def test_build_analysis_config_missing_path_returns_default():
    """Verify build_analysis_config_from_v2 returns a valid default AnalysisConfig if file is missing."""
    cfg = build_analysis_config_from_v2("non_existent_config_path_123.yaml")
    assert isinstance(cfg, AnalysisConfig)
    assert "duplicates" in cfg.enabled_checks
    assert "nulls" in cfg.enabled_checks
    assert cfg.duplicate_high_threshold == 5.0

    cfg_none = build_analysis_config_from_v2(None)
    assert isinstance(cfg_none, AnalysisConfig)


def test_get_config_hash_missing_path():
    """Verify get_config_hash returns 'none' when file is absent."""
    h = get_config_hash("non_existent_file.yaml")
    assert h == "none"


def test_service_run_config_free_with_inferred_rules():
    """Verify AnalysisService runs cleanly with default AnalysisConfig and infers rules."""
    df = pd.DataFrame({
        "emp_id": [f"E{i:03d}" for i in range(20)],
        "department": ["Finance"] * 20,
    })
    service = AnalysisService()
    result = service.run([("employees", df)], config=AnalysisConfig())

    assert result.run_id is not None
    assert len(result.datasets) == 1
    assert len(result.inferred_rules) == 1
    inf = result.inferred_rules[0]
    assert inf.suggested_identity_key is not None
    assert inf.suggested_identity_key.columns == ["emp_id"]
    assert result.score is not None
    assert result.score.overall == 100.0


def test_batch_runner_config_free(tmp_path):
    """Verify batch runner operates when no config file is passed or present."""
    out_dir = tmp_path / "reports"
    exit_code = run_batch([
        str(SAMPLES_DIR / "customers_clean_100pct.csv"),
        "--output", str(out_dir),
        "--json",
        "--no-db",
    ])
    assert exit_code == 0
    assert (out_dir / "customers_clean_100pct_data_quality_report.json").exists()


def test_gui_main_window_config_free_execution(qtbot, monkeypatch):
    """Verify GUI MainWindow can instantiate, run analysis, and render inferred rules in config-free mode."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: QMessageBox.Ok)

    window = MainWindow()
    qtbot.addWidget(window)

    df = pd.DataFrame({
        "User_ID": [f"U{i:04d}" for i in range(30)],
        "User_Name": [f"User {i}" for i in range(30)],
        "City": ["Berlin"] * 30,
    })
    window.upload_section._add_dataset_entry("users_test", df)

    # Run analysis with default config
    cfg = AnalysisConfig()
    result = AnalysisService().run(window.current_datasets, cfg)
    window._on_analysis_finished(result)

    # Standard results sections are visible
    assert not window.score_section.isHidden()
    assert not window.dimensions_section.isHidden()
    assert not window.issues_section.isHidden()
    assert len(result.inferred_rules) == 1
    assert result.inferred_rules[0].suggested_identity_key.columns == ["User_ID"]
    assert result.score.overall == 100.0
