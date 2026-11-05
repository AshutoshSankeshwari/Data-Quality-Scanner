"""
tests/test_mandatory_confirmation_dialog.py
Tests for V2.5 Mandatory Fields Confirmation Popup in GUI and Service Layer:
Part 1: Scrollable field list & fixed button visibility (1, 5, 20, 40+ fields).
Part 2: Explicit Proceed vs Cancel / X / Alt+F4 / Escape cancellation.
Part 3: Config retention and abortion without producing partial results.
Part 4: Medium / Low / Uncertain non-triggering.
Part 5: No new inferred fields non-triggering.
Part 6: Stale / partial result prevention on cancellation.
"""
from __future__ import annotations

import pytest
import pandas as pd
from PySide6.QtWidgets import QDialog
from PySide6.QtCore import Qt

from core.service import (
    AnalysisService,
    AnalysisConfig,
    AnalysisCancelledError,
)
from gui.mandatory_confirmation_dialog import InferredMandatoryConfirmationDialog


# ---------------------------------------------------------------------------
# Part 1: Popup Scrolling & Fixed Button Layout Tests
# ---------------------------------------------------------------------------

def test_dialog_short_list_1_field(qtbot):
    """Verify dialog with 1 field fits compactly with buttons visible."""
    dialog = InferredMandatoryConfirmationDialog(["ContractNumber"])
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.scroll_area is not None
    assert dialog.btn_proceed.isVisible()
    assert dialog.btn_cancel.isVisible()
    assert dialog.height() <= 400


def test_dialog_short_list_5_fields(qtbot):
    """Verify dialog with 5 fields displays cleanly with buttons visible."""
    fields = [f"Field_{i:03d}" for i in range(1, 6)]
    dialog = InferredMandatoryConfirmationDialog(fields)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.btn_proceed.isVisible()
    assert dialog.btn_cancel.isVisible()
    assert dialog.height() <= 500


def test_dialog_long_list_20_fields_scrollable(qtbot):
    """Verify dialog with 20 fields activates scrollbar while buttons remain visible."""
    fields = [f"Field_{i:03d}" for i in range(1, 21)]
    dialog = InferredMandatoryConfirmationDialog(fields)
    qtbot.addWidget(dialog)
    dialog.show()

    # The scroll area must be capped and have scrollable content
    assert dialog.scroll_area.maximumHeight() <= 240
    scrollbar = dialog.scroll_area.verticalScrollBar()
    assert scrollbar.maximum() > 0  # Scrollable

    # Fixed buttons and header remain visible on screen
    assert dialog.btn_proceed.isVisible()
    assert dialog.btn_cancel.isVisible()
    assert dialog.height() <= 540


def test_dialog_long_list_40_fields_scrollable_and_bounded(qtbot):
    """Verify dialog with 40+ fields stays strictly within screen bounds with scrollable list."""
    fields = [f"Field_{i:03d}" for i in range(1, 45)]
    dialog = InferredMandatoryConfirmationDialog(fields)
    qtbot.addWidget(dialog)
    dialog.show()

    # Dialog height must not exceed 540px
    assert dialog.height() <= 540
    scrollbar = dialog.scroll_area.verticalScrollBar()
    assert scrollbar.maximum() > 0

    # Buttons remain visible and enabled
    assert dialog.btn_proceed.isVisible()
    assert dialog.btn_cancel.isVisible()


def test_dialog_button_interaction_after_scrolling(qtbot):
    """Verify user can scroll down and click Proceed or Cancel."""
    fields = [f"Field_{i:03d}" for i in range(1, 40)]
    dialog = InferredMandatoryConfirmationDialog(fields)
    qtbot.addWidget(dialog)
    dialog.show()

    scrollbar = dialog.scroll_area.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())  # Scroll to bottom

    # Click Proceed after scrolling
    with qtbot.waitSignal(dialog.accepted, timeout=1000):
        qtbot.mouseClick(dialog.btn_proceed, Qt.LeftButton)
    assert dialog.result() == QDialog.Accepted


def test_dialog_cancel_after_scrolling(qtbot):
    """Verify user can scroll down and click Cancel."""
    fields = [f"Field_{i:03d}" for i in range(1, 40)]
    dialog = InferredMandatoryConfirmationDialog(fields)
    qtbot.addWidget(dialog)
    dialog.show()

    scrollbar = dialog.scroll_area.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())  # Scroll to bottom

    # Click Cancel after scrolling
    with qtbot.waitSignal(dialog.rejected, timeout=1000):
        qtbot.mouseClick(dialog.btn_cancel, Qt.LeftButton)
    assert dialog.result() == QDialog.Rejected


# ---------------------------------------------------------------------------
# Part 2: Window X, Escape, Alt+F4 Closing Behavior
# ---------------------------------------------------------------------------

def test_dialog_close_event_rejects(qtbot):
    """Verify closing via window X button triggers reject and returns QDialog.Rejected."""
    dialog = InferredMandatoryConfirmationDialog(["ContractNumber"])
    qtbot.addWidget(dialog)
    dialog.show()

    with qtbot.waitSignal(dialog.rejected, timeout=1000):
        dialog.close()

    assert dialog.result() == QDialog.Rejected


def test_dialog_escape_key_rejects(qtbot):
    """Verify pressing Escape key rejects the dialog."""
    dialog = InferredMandatoryConfirmationDialog(["ContractNumber"])
    qtbot.addWidget(dialog)
    dialog.show()

    with qtbot.waitSignal(dialog.rejected, timeout=1000):
        qtbot.keyClick(dialog, Qt.Key_Escape)

    assert dialog.result() == QDialog.Rejected


# ---------------------------------------------------------------------------
# Part 3: Proceed vs Cancel Service Layer Execution
# ---------------------------------------------------------------------------

def test_proceed_activates_inferred_mandatory_fields():
    """Verify explicit Proceed continues analysis and applies inferred fields."""
    df = pd.DataFrame({
        "ContractNumber": [f"CTR-{i:04d}" for i in range(50)],
        "City": ["London"] * 50,
    })

    service = AnalysisService()
    res = service.run(
        [("contracts", df)],
        config=None,
        mandatory_confirmation_callback=lambda fields: True,
    )

    assert res is not None
    assert len(res.mandatory_field_results) == 1
    assert "ContractNumber" in res.mandatory_field_results[0].mandatory_fields
    assert res.score is not None


def test_cancel_raises_cancellation_error_and_aborts():
    """Verify Cancel raises AnalysisCancelledError and aborts run without producing result."""
    df = pd.DataFrame({
        "ContractNumber": [f"CTR-{i:04d}" for i in range(50)],
        "City": ["London"] * 50,
    })

    service = AnalysisService()
    with pytest.raises(AnalysisCancelledError):
        service.run(
            [("contracts", df)],
            config=None,
            mandatory_confirmation_callback=lambda fields: False,
        )


def test_config_plus_inference_shows_only_new_fields_and_aborts_on_cancel():
    """
    Config: Email
    Inference: Email = High, ContractNumber = High
    Verify only ContractNumber is prompted, and Cancel aborts run.
    """
    df = pd.DataFrame({
        "Email": [f"user_{i}@test.com" for i in range(50)],
        "ContractNumber": [f"CTR-{i:04d}" for i in range(50)],
    })

    cfg = AnalysisConfig(mandatory_fields=["Email"])
    service = AnalysisService()

    presented_fields = []
    def record_and_cancel(fields):
        presented_fields.extend(fields)
        return False

    with pytest.raises(AnalysisCancelledError):
        service.run([("accounts", df)], config=cfg, mandatory_confirmation_callback=record_and_cancel)

    # Only new inferred field was presented
    assert presented_fields == ["ContractNumber"]
    assert "Email" not in presented_fields
    # Explicit config was not mutated
    assert cfg.mandatory_fields == ["Email"]


# ---------------------------------------------------------------------------
# Part 4: Non-Triggering Inferences (Medium / Low / Uncertain / No New Fields)
# ---------------------------------------------------------------------------

def test_medium_confidence_does_not_trigger_popup_and_completes():
    """Verify medium-confidence column does not trigger confirmation and analysis completes."""
    df = pd.DataFrame({
        "City": ["London", "Paris", "Tokyo", "Berlin", "Rome"] * 10,  # Score 0.50 (Medium)
        "Notes": [None] * 50,
    })

    service = AnalysisService()
    callback_called = []
    res = service.run(
        [("locations", df)],
        config=None,
        mandatory_confirmation_callback=lambda f: callback_called.append(f) or True,
    )

    assert len(callback_called) == 0
    assert res is not None


def test_all_configured_fields_does_not_trigger_popup():
    """Verify when all inferred High-confidence fields are already in config, no popup appears."""
    df = pd.DataFrame({
        "Customer_ID": [f"CUST{i:03d}" for i in range(50)],
        "City": ["London"] * 50,
    })

    cfg = AnalysisConfig(mandatory_fields=["Customer_ID"])
    service = AnalysisService()
    callback_called = []
    res = service.run(
        [("customers", df)],
        config=cfg,
        mandatory_confirmation_callback=lambda f: callback_called.append(f) or True,
    )

    assert len(callback_called) == 0
    assert res is not None
    assert res.mandatory_field_results[0].mandatory_fields == ["Customer_ID"]


# ---------------------------------------------------------------------------
# Part 5: GUI Worker Integration Tests (Proceed, Cancel, Stale Prevention)
# ---------------------------------------------------------------------------

def test_gui_proceed_executes_analysis_and_displays_result(qtbot, monkeypatch):
    """Verify clicking Proceed in GUI executes analysis and displays result."""
    from gui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)

    df = pd.DataFrame({
        "Account_Num": [f"ACC-{i:05d}" for i in range(50)],
        "City": ["London"] * 50,
    })
    window._on_datasets_changed([("accounts", df)])

    # Mock dialog to return Accepted (Proceed)
    monkeypatch.setattr(InferredMandatoryConfirmationDialog, "exec", lambda self: QDialog.Accepted)

    window._start_analysis()
    with qtbot.waitSignal(window.worker.finished, timeout=5000):
        pass
    qtbot.waitUntil(lambda: window.current_result is not None, timeout=5000)

    assert window.current_result is not None
    assert "Account_Num" in window.current_result.mandatory_field_results[0].mandatory_fields


def test_gui_cancel_aborts_run_without_producing_result(qtbot, monkeypatch):
    """Verify clicking Cancel in GUI aborts run and produces no result."""
    from gui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)

    df = pd.DataFrame({
        "Account_Num": [f"ACC-{i:05d}" for i in range(50)],
        "City": ["London"] * 50,
    })
    window._on_datasets_changed([("accounts", df)])

    # Mock dialog to return Rejected (Cancel)
    monkeypatch.setattr(InferredMandatoryConfirmationDialog, "exec", lambda self: QDialog.Rejected)

    window._start_analysis()
    with qtbot.waitSignal(window.worker.cancelled, timeout=5000):
        pass

    # No result produced
    assert window.current_result is None
    assert window.score_section.isVisible() is False


def test_gui_cancel_prevents_stale_partial_result_replacement(qtbot, monkeypatch):
    """
    Verify that when a previous analysis exists, cancelling a subsequent analysis
    does NOT overwrite or replace the existing result with a cancelled/partial result.
    """
    from gui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)

    df = pd.DataFrame({
        "Account_Num": [f"ACC-{i:05d}" for i in range(50)],
        "City": ["London"] * 50,
    })
    window._on_datasets_changed([("accounts", df)])

    # 1. Run first analysis with Proceed
    monkeypatch.setattr(InferredMandatoryConfirmationDialog, "exec", lambda self: QDialog.Accepted)
    window._start_analysis()
    with qtbot.waitSignal(window.worker.finished, timeout=5000):
        pass
    qtbot.waitUntil(lambda: window.current_result is not None, timeout=5000)

    first_result = window.current_result
    assert first_result is not None
    first_run_id = first_result.run_id

    # 2. Start a second analysis, but this time user Cancels / closes X
    monkeypatch.setattr(InferredMandatoryConfirmationDialog, "exec", lambda self: QDialog.Rejected)
    window._start_analysis()
    with qtbot.waitSignal(window.worker.cancelled, timeout=5000):
        pass

    # The previous result must remain intact and displayed
    assert window.current_result is not None
    assert window.current_result.run_id == first_run_id
    assert not window.score_section.isHidden()
    assert window.dataset_info._dataset_rows[0]._status_lbl.text() == "Analysed ✓"
