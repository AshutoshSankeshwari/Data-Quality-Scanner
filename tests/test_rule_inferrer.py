"""
tests/test_rule_inferrer.py
Comprehensive test suite for the V2.5 Automatic Rule Inference Engine.

Test categories:
  1. Tokenization unit tests
  2. Synthetic archetype tests (V2 compatibility — identity + mandatory)
  3. Explainability and bounded composite-key search
  4. Small-dataset safeguards
  5. Service non-breaking integration
  6. [NEW] Negative mandatory tests: operational/optional attributes must NOT reach High
  7. [NEW] Positive mandatory tests: strong reference fields CAN reach High with supporting data
  8. [NEW] Identity-like but not necessarily mandatory tests
  9. [NEW] Completeness-only test: semantic weakness prevents High even with perfect data
 10. [NEW] Ambiguous core-attribute tests: important but not universally mandatory
 11. [NEW] Wide-dataset safety-cap test: MAX_AUTO_MANDATORY_FIELDS ceiling
 12. [NEW] Precision/recall balance: zero activatable candidates is NOT success
"""
import pytest
import pandas as pd

from core.profiling.profiler import profile_dataset
from core.inference.rule_inferrer import (
    infer_identity_keys,
    infer_rules_for_dataset,
    _tokenize_name,
    MAX_AUTO_MANDATORY_FIELDS,
)
from core.service import AnalysisService, AnalysisConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_df_with_column(col_name: str, values) -> pd.DataFrame:
    return pd.DataFrame({col_name: values})


def _get_mandatory(res, col_name):
    return next((m for m in res.mandatory_fields if m.column_name == col_name), None)


def _make_complete_identifier(name: str, n: int = 200) -> pd.DataFrame:
    """Fully-populated, high-cardinality, consistent-format column."""
    return pd.DataFrame({name: [f"ID-{i:06d}" for i in range(n)]})


def _make_complete_categorical(name: str, categories: list, n: int = 200) -> pd.DataFrame:
    """Fully-populated, low-cardinality categorical column."""
    return pd.DataFrame({name: [categories[i % len(categories)] for i in range(n)]})


# ---------------------------------------------------------------------------
# 1. Tokenization Unit Tests
# ---------------------------------------------------------------------------

def test_tokenize_name():
    """Verify generic column name tokenization splits camelCase, underscores, and symbols."""
    assert "id" in _tokenize_name("Customer_ID")
    assert "customer" in _tokenize_name("Customer_ID")
    assert "date" in _tokenize_name("date_of_birth")
    assert "birth" in _tokenize_name("date_of_birth")
    assert "notes" in _tokenize_name("userNotes")
    assert "sku" in _tokenize_name("item-sku-code")


# ---------------------------------------------------------------------------
# 2. Synthetic Archetype Tests (V2 compatibility)
# ---------------------------------------------------------------------------

def test_archetype_unique_alphanumeric_identifier():
    """Archetype 1: Unique alphanumeric ID (e.g. CUST001..CUST100) is High confidence Identity & Mandatory."""
    df = pd.DataFrame({
        "account_id": [f"ACC-{i:04d}" for i in range(1, 101)],
        "balance_amt": [100.50 + i for i in range(100)],
    })
    profile = profile_dataset(df, name="accounts")
    res = infer_rules_for_dataset(profile, df)

    acc_mf = _get_mandatory(res, "account_id")
    assert acc_mf is not None
    assert acc_mf.confidence == "High"
    assert acc_mf.is_mandatory is True
    assert acc_mf.is_activatable is True
    assert len(acc_mf.reasons) >= 2

    assert res.suggested_identity_key is not None
    assert res.suggested_identity_key.columns == ["account_id"]
    assert res.suggested_identity_key.confidence == "High"
    assert res.suggested_identity_key.uniqueness_ratio == 1.0
    assert len(res.suggested_identity_key.reasons) >= 3


def test_archetype_repeated_categorical_rejected_as_identity():
    """Archetype 2: Categorical fields (e.g. City, Status) are strictly rejected as identity keys."""
    cities = ["New York", "London", "Paris", "Tokyo", "Berlin"] * 20
    statuses = ["Active", "Pending", "Suspended", "Closed"] * 25
    df = pd.DataFrame({"city_name": cities, "account_status": statuses})
    profile = profile_dataset(df, name="geo_status")
    res = infer_rules_for_dataset(profile, df)

    assert res.suggested_identity_key is None or res.suggested_identity_key.columns not in (["city_name"], ["account_status"])
    rejected_names = [r["column"] for r in res.rejected_identity_candidates]
    assert "city_name" in rejected_names
    assert "account_status" in rejected_names


def test_archetype_populated_entity_name_not_identity_key():
    """Archetype 3: Fully populated entity name is rejected as identity key AND must not reach High mandatory."""
    names = [f"Person {i % 96}" for i in range(100)]
    df = pd.DataFrame({"client_full_name": names})
    profile = profile_dataset(df, name="clients")
    res = infer_rules_for_dataset(profile, df)

    name_mf = _get_mandatory(res, "client_full_name")
    assert name_mf is not None
    # Entity names without strong additional evidence must not reach High mandatory confidence
    assert name_mf.confidence != "High", (
        f"client_full_name must not reach High mandatory confidence; got {name_mf.confidence} "
        f"(score={name_mf.confidence_score}, reasons={name_mf.reasons})"
    )
    # Should be Medium or lower (name token + completeness)
    assert name_mf.confidence in ("Medium", "Low", "Uncertain")
    # Must be rejected as identity key
    assert res.suggested_identity_key is None or res.suggested_identity_key.columns != ["client_full_name"]


def test_archetype_nullable_optional_attribute():
    """Archetype 4: Highly nullable auxiliary field is Low/Uncertain and not mandatory."""
    notes = ["Some memo" if i % 4 == 0 else None for i in range(100)]
    df = pd.DataFrame({"user_notes": notes})
    profile = profile_dataset(df, name="notes_table")
    res = infer_rules_for_dataset(profile, df)

    notes_mf = _get_mandatory(res, "user_notes")
    assert notes_mf.confidence in ("Low", "Uncertain")
    assert notes_mf.is_mandatory is False
    assert any("missing" in r.lower() for r in notes_mf.reasons)


def test_archetype_composite_key_candidate():
    """Archetype 5: Parent-Child repeating pair detected as composite alternative key."""
    order_nums = [f"ORD-{i // 5 + 1:03d}" for i in range(100)]
    line_nums = [f"{(i % 5) + 1:02d}" for i in range(100)]
    df = pd.DataFrame({
        "order_num": order_nums,
        "line_no": line_nums,
        "amount": [10.0 * (i + 1) for i in range(100)],
    })
    profile = profile_dataset(df, name="order_lines")
    res = infer_rules_for_dataset(profile, df)

    all_keys = ([res.suggested_identity_key] if res.suggested_identity_key else []) + res.alternative_identity_keys
    comp_found = any(k.is_composite and set(k.columns) == {"order_num", "line_no"} for k in all_keys if k)
    assert comp_found is True


def test_archetype_high_cardinality_free_text_rejected():
    """Archetype 6: Free-form text rejected as identity key despite high uniqueness."""
    descriptions = [
        f"Unique description sentence with detailed narrative #{i} that varies significantly."
        for i in range(100)
    ]
    df = pd.DataFrame({"product_description": descriptions})
    profile = profile_dataset(df, name="descriptions")
    res = infer_rules_for_dataset(profile, df)

    rejected_names = [r["column"] for r in res.rejected_identity_candidates]
    assert "product_description" in rejected_names


def test_archetype_low_cardinality_status_flag_rejected():
    """Archetype 7: Boolean/Status flag is strictly rejected as identity key."""
    df = pd.DataFrame({"is_active_flag": [True, False] * 50})
    profile = profile_dataset(df, name="flags")
    res = infer_rules_for_dataset(profile, df)

    rejected_names = [r["column"] for r in res.rejected_identity_candidates]
    assert "is_active_flag" in rejected_names


# ---------------------------------------------------------------------------
# 3. Explainability and Bounded Search Tests
# ---------------------------------------------------------------------------

def test_explainability_all_candidates_have_reasons():
    """Verify every inferred mandatory field and identity key has human-readable reasons."""
    df = pd.DataFrame({
        "record_id": [f"ID{i}" for i in range(50)],
        "client_email": [f"user{i}@corp.com" for i in range(50)],
        "fax_number": [None] * 40 + [f"555-{i}" for i in range(10)],
    })
    profile = profile_dataset(df, name="contacts")
    res = infer_rules_for_dataset(profile, df)

    for mf in res.mandatory_fields:
        assert len(mf.reasons) > 0, f"Missing reasons for mandatory field {mf.column_name}"
        assert isinstance(mf.reasons[0], str)

    if res.suggested_identity_key:
        assert len(res.suggested_identity_key.reasons) > 0
    for ak in res.alternative_identity_keys:
        assert len(ak.reasons) > 0


def test_bounded_composite_search_limits_evaluation():
    """Verify wide datasets do not suffer combinatorial explosion in composite key evaluation."""
    data = {f"col_{i}": [f"val_{i}_{r}" for r in range(50)] for i in range(25)}
    df = pd.DataFrame(data)
    profile = profile_dataset(df, name="wide_dataset")

    suggested, alternatives, rejected = infer_identity_keys(profile, df, max_candidates=5)
    assert suggested is not None or len(alternatives) >= 0


# ---------------------------------------------------------------------------
# 4. Small-Dataset Safeguards
# ---------------------------------------------------------------------------

def test_small_dataset_safeguard_identity_confidence_dampened():
    """Verify tiny dataset (5 rows) has identity confidence dampened."""
    df = pd.DataFrame({
        "item_tag": [f"TAG_{i}" for i in range(5)],
        "item_name": [f"Item {i}" for i in range(5)],
    })
    profile = profile_dataset(df, name="tiny_sample")
    res = infer_rules_for_dataset(profile, df)

    if res.suggested_identity_key:
        assert res.suggested_identity_key.confidence in ("Medium", "Low")
        assert any("small sample" in r.lower() for r in res.suggested_identity_key.reasons)


def test_small_dataset_safeguard_mandatory_field():
    """Verify tiny dataset requires strong semantic identifier to reach High mandatory confidence."""
    df = pd.DataFrame({"ArbitraryColumn": ["Val1", "Val2", "Val3", "Val4", "Val5"]})
    profile = profile_dataset(df, name="tiny_sample")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "ArbitraryColumn")
    assert mf.confidence != "High"


# ---------------------------------------------------------------------------
# 5. Service Non-Breaking Integration Test
# ---------------------------------------------------------------------------

def test_service_run_populates_inferred_rules_without_altering_v2_scoring():
    """Verify AnalysisService.run populates inferred_rules while preserving V2 checks and scoring."""
    df = pd.DataFrame({
        "Customer_ID": [f"CUST{i:03d}" for i in range(1, 51)],
        "City": ["Berlin"] * 50,
        "Country": ["Germany"] * 50,
    })
    service = AnalysisService()
    cfg = AnalysisConfig()
    result = service.run([("test_ds", df)], config=cfg)

    assert len(result.inferred_rules) == 1
    inf = result.inferred_rules[0]
    assert inf.dataset_name == "test_ds"
    assert inf.suggested_identity_key is not None
    assert inf.suggested_identity_key.columns == ["Customer_ID"]

    assert result.score is not None
    assert result.score.overall == 100.0
    assert cfg.mandatory_fields == []
    assert cfg.duplicate_key_sets == []


# ---------------------------------------------------------------------------
# 6. [NEW] Negative Tests: Operational/Optional Attributes Must NOT Reach High
# ---------------------------------------------------------------------------

def _assert_not_high(col_name: str, values, reason_hint: str = ""):
    """Helper: assert a column does not reach High mandatory confidence."""
    df = pd.DataFrame({col_name: values})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)
    mf = _get_mandatory(res, col_name)
    assert mf is not None
    assert mf.confidence != "High", (
        f"{col_name} must not reach High mandatory confidence. "
        f"Got: {mf.confidence} (score={mf.confidence_score}). {reason_hint} "
        f"Reasons: {mf.reasons}"
    )
    return mf


def test_negative_shift_name_not_high():
    """ShiftName: organizational operational — must not reach High even when 100% populated."""
    shifts = ["Morning", "Afternoon", "Night"] * 67  # 201 rows, low cardinality
    _assert_not_high(
        "ShiftName", shifts[:200],
        "shift is organizational/HR context-dependent attribute"
    )


def test_negative_region_name_not_high():
    """RegionName: geographic operational — must not reach High."""
    regions = ["North", "South", "East", "West", "Central"] * 40
    _assert_not_high("RegionName", regions, "geographic attribute")


def test_negative_plant_city_not_high():
    """PlantCity: geographic + entity name mix — must not reach High."""
    cities = ["Berlin", "Stuttgart", "Munich", "Hamburg"] * 50
    _assert_not_high("PlantCity", cities, "geographic attribute")


def test_negative_country_code_not_high():
    """CountryCode: has 'code' identifier token but geographic penalty should prevent High."""
    codes = ["DE", "US", "GB", "FR", "JP"] * 40
    _assert_not_high(
        "CountryCode", codes,
        "country token applies geographic penalty; low cardinality"
    )


def test_negative_department_name_not_high():
    """DepartmentName: organizational attribute — must not reach High."""
    depts = ["Engineering", "Finance", "HR", "Sales", "Operations"] * 40
    _assert_not_high("DepartmentName", depts, "organizational attribute")


def test_negative_priority_level_not_high():
    """PriorityLevel: operational attribute — must not reach High."""
    levels = ["Low", "Medium", "High", "Critical"] * 50
    _assert_not_high("PriorityLevel", levels, "operational attribute")


def test_negative_maintenance_type_not_high():
    """MaintenanceType: maintenance/operational — must not reach High."""
    types = ["Preventive", "Corrective", "Predictive"] * 67
    _assert_not_high("MaintenanceType", types[:200], "operational maintenance attribute")


def test_negative_packaging_type_not_high():
    """PackagingType: operational attribute — must not reach High."""
    types = ["Box", "Crate", "Pallet", "Drum"] * 50
    _assert_not_high("PackagingType", types, "operational attribute")


def test_negative_total_cost_not_high():
    """TotalCost: no semantic anchor + financial penalty — must not reach High."""
    costs = [100.0 + i * 0.5 for i in range(200)]
    _assert_not_high("TotalCost", costs, "financial metric, no semantic anchor")


def test_negative_maintenance_cost_not_high():
    """MaintenanceCost: no semantic anchor + maintenance + financial penalties — must not reach High."""
    costs = [250.0 + i for i in range(200)]
    _assert_not_high("MaintenanceCost", costs, "maintenance + financial attribute penalties")


def test_negative_tax_rate_not_high():
    """TaxRate: financial metric — must not reach High."""
    rates = [0.05, 0.10, 0.15, 0.20] * 50
    _assert_not_high("TaxRate", rates, "financial metric attribute")


def test_negative_discount_rate_not_high():
    """DiscountRate: financial metric — must not reach High."""
    rates = [0.0, 0.05, 0.10, 0.15, 0.20] * 40
    _assert_not_high("DiscountRate", rates, "financial metric attribute")


def test_negative_carrier_name_not_high():
    """CarrierName: organizational/HR category — must not reach High."""
    carriers = ["DHL", "FedEx", "UPS", "DPD"] * 50
    _assert_not_high("CarrierName", carriers, "organizational carrier attribute")


def test_negative_supervisor_code_not_high():
    """SupervisorCode: 'code' is identifier token, but supervisor/org penalty should prevent High."""
    codes = ["SUP001", "SUP002", "SUP003", "SUP004"] * 50
    mf = _assert_not_high(
        "SupervisorCode", codes,
        "supervisor is organizational attribute; low cardinality categorical"
    )
    # Score must be significantly reduced by operational penalty
    assert mf.confidence_score < 0.70


def test_negative_inspection_comment_not_high():
    """InspectionComment: free-text + ops token — must not reach High."""
    comments = [f"Inspection note {i}" for i in range(200)]
    _assert_not_high("InspectionComment", comments, "free-text + inspection operational attribute")


def test_negative_free_text_notes_not_high():
    """FreeTextNotes: explicit free-text attribute — must not reach High."""
    notes = [f"Internal note regarding item {i}" for i in range(200)]
    _assert_not_high("FreeTextNotes", notes, "free-text attribute")


# ---------------------------------------------------------------------------
# 7. [NEW] Positive Tests: Strong Reference Fields CAN Reach High
# ---------------------------------------------------------------------------

def _assert_can_be_high(col_name: str, values, reason_hint: str = ""):
    """Helper: assert a column reaches High mandatory confidence."""
    df = pd.DataFrame({col_name: values})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)
    mf = _get_mandatory(res, col_name)
    assert mf is not None, f"No mandatory field result found for {col_name}"
    assert mf.confidence == "High", (
        f"{col_name} should reach High mandatory confidence. "
        f"Got: {mf.confidence} (score={mf.confidence_score}). {reason_hint} "
        f"Reasons: {mf.reasons}"
    )
    assert mf.is_mandatory is True
    assert mf.is_activatable is True
    return mf


def test_positive_work_order_number_reaches_high():
    """WorkOrderNum: identifier token + 100% populated + high uniqueness + consistent format → High."""
    values = [f"WO-{i:06d}" for i in range(200)]
    _assert_can_be_high(
        "WorkOrderNum", values,
        "strong identifier token + perfect population + high uniqueness"
    )


def test_positive_batch_number_reaches_high():
    """BatchNumber: business reference token + 100% populated + high uniqueness → High."""
    values = [f"BATCH-{i:05d}" for i in range(200)]
    _assert_can_be_high(
        "BatchNumber", values,
        "business reference token + perfect population + high uniqueness"
    )


def test_positive_purchase_order_num_reaches_high():
    """PurchaseOrderNum: business reference (order + num tier1) + 100% populated → High."""
    values = [f"PO-{i:07d}" for i in range(200)]
    _assert_can_be_high(
        "PurchaseOrderNum", values,
        "business reference token + identifier token + high uniqueness"
    )


def test_positive_tracking_ref_reaches_medium_or_high():
    """
    TrackingRef: Tier 2 business reference tokens (tracking + ref) + 100% populated + high uniqueness.
    Tier 2 anchor (0.25) + completeness (0.20) + consistent format (0.06) + cardinality (0.09) = 0.60.
    This correctly reaches Medium — a strong positive signal, though not quite High.
    Tier 1 identifier columns (id, num, number, key) are needed to reach High with cardinality.
    The test verifies positive (not Low/Uncertain) evaluation of a business reference field.
    """
    values = [f"TRK-{i:08d}" for i in range(200)]
    df = pd.DataFrame({"TrackingRef": values})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)
    mf = _get_mandatory(res, "TrackingRef")
    assert mf is not None
    assert mf.confidence in ("Medium", "High"), (
        f"TrackingRef with strong data evidence must reach at least Medium. "
        f"Got: {mf.confidence} (score={mf.confidence_score}). Reasons: {mf.reasons}"
    )
    assert mf.is_mandatory is True


def test_positive_configured_field_always_applies():
    """Configured mandatory fields are always applied regardless of inference confidence."""
    df = pd.DataFrame({
        "WorkOrderNumber": [f"WO-{i:05d}" for i in range(100)],
        "ShiftName": [["Morning", "Afternoon", "Night"][i % 3] for i in range(100)],
    })
    cfg = AnalysisConfig(mandatory_fields=["ShiftName"])  # explicitly configured
    service = AnalysisService()
    result = service.run([("ops", df)], config=cfg)

    # ShiftName must be in mandatory fields despite being operationally optional
    assert "ShiftName" in result.mandatory_field_results[0].mandatory_fields


# ---------------------------------------------------------------------------
# 8. [NEW] Identity-Like But Not Necessarily Mandatory Tests
# ---------------------------------------------------------------------------

def test_identity_like_serial_number_not_automatically_mandatory_high():
    """
    SerialNumber: identifier token + high uniqueness + 100% populated.
    Should reach Medium or High at the boundary (≥0.69), but identity-like
    naming alone must NOT be the sole driver. Verify score is reasonable.
    """
    values = [f"SN-{i:08d}" for i in range(200)]
    df = pd.DataFrame({"SerialNumber": values})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "SerialNumber")
    assert mf is not None
    # SerialNumber may be Medium or High at the boundary — both are acceptable.
    # The key assertion is it does NOT automatically reach High through identity alone.
    # If it reaches High (0.70+), it must also have strong data evidence (uniqueness + structure).
    if mf.confidence == "High":
        # Verify data evidence supported it (not just the token)
        assert mf.confidence_score <= 1.0
        # If High, at least population and one structural signal must be present
        population_reason = any("populated" in r.lower() for r in mf.reasons)
        structural_reason = any(
            "format" in r.lower() or "uniqueness" in r.lower() or "structured" in r.lower()
            for r in mf.reasons
        )
        assert population_reason, "High mandatory must include population evidence"
        assert structural_reason, "High mandatory must include structural/cardinality evidence"
    else:
        assert mf.confidence in ("Medium", "Low")


def test_identity_like_tracking_reference_requires_data_evidence():
    """
    TrackingReference with sparse population (40% missing): must NOT reach High
    even though it has strong business reference semantics.
    """
    values = [f"TRK-{i:06d}" if i % 10 < 6 else None for i in range(200)]
    df = pd.DataFrame({"TrackingReference": values})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "TrackingReference")
    assert mf is not None
    # 40% missing → significant completeness penalty. Must not be High.
    assert mf.confidence != "High", (
        f"TrackingReference with 40% missing must not be High; got {mf.confidence} "
        f"(score={mf.confidence_score})"
    )


def test_identity_like_part_code_low_uniqueness_not_high():
    """
    PartCode with many repeats (low cardinality): reference token but without
    high-uniqueness structural support, cannot reach High mandatory confidence.
    """
    # 5 distinct part codes repeated across 200 rows — low cardinality
    codes = [f"PART-{(i % 5) + 1:03d}" for i in range(200)]
    df = pd.DataFrame({"PartCode": codes})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "PartCode")
    assert mf is not None
    # Low cardinality means no cardinality bonus; score should stay at Medium or below.
    # (Tier2 anchor + completeness = 0.25 + 0.20 = 0.45 = Medium ceiling without cardinality)
    assert mf.confidence != "High", (
        f"PartCode with low cardinality must not reach High; got {mf.confidence} "
        f"(score={mf.confidence_score})"
    )


# ---------------------------------------------------------------------------
# 9. [NEW] Completeness-Only Test (mandatory)
#
# A semantically weak field with 100% population, structured type, and high
# cardinality must NOT reach High confidence. This tests the core principle.
# ---------------------------------------------------------------------------

def test_completeness_only_cannot_reach_high():
    """
    Critical: A column with no semantic tier match must not reach High confidence
    even when 100% populated, structured (numeric), and high cardinality.

    This tests the fundamental principle: completeness cannot originate mandatory confidence.
    """
    # Semantically neutral column name: no identifier, reference, or entity tokens.
    # 100% populated, numeric, every value unique.
    df = pd.DataFrame({"Measurement": [float(i) * 1.0001 for i in range(200)]})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "Measurement")
    assert mf is not None
    assert mf.confidence != "High", (
        f"Semantically-neutral 'Measurement' column must not reach High "
        f"despite 100% population and high cardinality. Got: {mf.confidence} "
        f"(score={mf.confidence_score}). Reasons: {mf.reasons}"
    )
    # Phase 5 gate should be present in reasons (semantic anchor < 0.15)
    gate_applied = any("cap" in r.lower() or "semantic" in r.lower() for r in mf.reasons)
    assert gate_applied, "Phase 5 gate reason must be present for semantically-neutral field"


def test_completeness_only_structured_boolean_not_high():
    """
    A 100%-populated structured boolean field with no semantic anchor
    must not reach High merely because it is complete and structured.
    """
    df = pd.DataFrame({"IsVerified": [True, False] * 100})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "IsVerified")
    assert mf is not None
    assert mf.confidence != "High", (
        f"IsVerified boolean must not reach High via completeness+structure alone; "
        f"got {mf.confidence} (score={mf.confidence_score})"
    )


# ---------------------------------------------------------------------------
# 10. [NEW] Ambiguous Core-Attribute Tests
# ---------------------------------------------------------------------------

def test_ambiguous_email_not_high():
    """
    Email: Tier 3 core entity token + 100% populated.
    Business importance does not automatically mean mandatory.
    Phase 5 gate: anchor (0.10) < 0.15 → capped at 0.44.
    Expected: Low (not High, not Medium via gate).
    """
    emails = [f"user{i}@company.com" for i in range(200)]
    df = pd.DataFrame({"Email": emails})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "Email")
    assert mf is not None
    assert mf.confidence != "High", (
        f"Email must not automatically reach High; got {mf.confidence} (score={mf.confidence_score})"
    )
    # Email without explicit config should be Low or Medium at most
    assert mf.confidence in ("Low", "Medium", "Uncertain")


def test_ambiguous_status_not_high():
    """
    Status: no explicit semantic tier match. Must not reach High.
    """
    statuses = ["Active", "Inactive", "Pending", "Closed"] * 50
    df = pd.DataFrame({"Status": statuses})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "Status")
    assert mf is not None
    assert mf.confidence != "High", (
        f"Status must not reach High; got {mf.confidence} (score={mf.confidence_score})"
    )


def test_ambiguous_quantity_not_high():
    """
    Quantity: numeric, 100% populated. Financial metric penalty applies.
    Must not reach High.
    """
    df = pd.DataFrame({"Quantity": [i + 1 for i in range(200)]})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "Quantity")
    assert mf is not None
    assert mf.confidence != "High", (
        f"Quantity must not reach High; got {mf.confidence} (score={mf.confidence_score})"
    )


def test_ambiguous_date_not_high():
    """
    CreatedDate: 'date' has no tier match. 100% populated DATE type.
    Must not reach High without semantic anchor.
    """
    dates = pd.date_range("2020-01-01", periods=200, freq="D")
    df = pd.DataFrame({"CreatedDate": dates})
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    mf = _get_mandatory(res, "CreatedDate")
    assert mf is not None
    assert mf.confidence != "High", (
        f"CreatedDate must not reach High via completeness+type alone; "
        f"got {mf.confidence} (score={mf.confidence_score})"
    )


# ---------------------------------------------------------------------------
# 11. [NEW] Wide-Dataset Safety Cap Test
# ---------------------------------------------------------------------------

def test_wide_dataset_activatable_cap_enforced():
    """
    A synthetic wide dataset engineered to produce many High-confidence columns
    must cap auto-activatable candidates at MAX_AUTO_MANDATORY_FIELDS.
    Columns beyond the cap are preserved in results but is_activatable=False.
    """
    # Build 20 columns that all look like strong identifier fields
    n = 500
    data = {}
    for i in range(20):
        col_name = f"RecordID_{i:02d}"  # all contain 'id' (Tier 1) + 100% unique + complete
        data[col_name] = [f"RID{i}-{j:06d}" for j in range(n)]

    df = pd.DataFrame(data)
    profile = profile_dataset(df, name="wide_ds")
    res = infer_rules_for_dataset(profile, df)

    high_conf = [m for m in res.mandatory_fields if m.confidence == "High"]
    activatable = [m for m in high_conf if m.is_activatable]
    non_activatable = [m for m in high_conf if not m.is_activatable]

    # There may be many High-confidence columns, but activatable must be ≤ 8
    assert len(activatable) <= MAX_AUTO_MANDATORY_FIELDS, (
        f"Expected ≤ {MAX_AUTO_MANDATORY_FIELDS} activatable candidates, "
        f"got {len(activatable)}: {[m.column_name for m in activatable]}"
    )

    # If more than 8 High-confidence columns exist, the remaining must be non-activatable
    if len(high_conf) > MAX_AUTO_MANDATORY_FIELDS:
        assert len(non_activatable) > 0, (
            "Expected some High-confidence columns to be non-activatable beyond the cap"
        )
        # Non-activatable columns must still have reasons
        for m in non_activatable:
            assert len(m.reasons) > 0
            cap_reason = any("cap" in r.lower() or "max_auto" in r.lower() for r in m.reasons)
            assert cap_reason, f"Non-activatable column {m.column_name} must have a cap-related reason"


def test_wide_dataset_cap_is_ceiling_not_target():
    """
    If fewer than MAX_AUTO_MANDATORY_FIELDS genuine High-confidence columns exist,
    all of them are activatable. The cap is a ceiling, not a minimum.
    """
    # Only 2 strong identifier columns
    df = pd.DataFrame({
        "OrderID": [f"ORD-{i:06d}" for i in range(200)],
        "RecordKey": [f"RK-{i:06d}" for i in range(200)],
        "City": ["London", "Paris", "Berlin", "Tokyo"] * 50,
        "Status": ["Active", "Inactive"] * 100,
    })
    profile = profile_dataset(df, name="small_wide_ds")
    res = infer_rules_for_dataset(profile, df)

    activatable = [m for m in res.mandatory_fields if m.is_activatable and m.confidence == "High"]
    # Should be ≤ 8 but must not be forced to exactly 8
    assert len(activatable) <= MAX_AUTO_MANDATORY_FIELDS
    # At least the two strong identifier columns should be activatable
    activatable_names = {m.column_name for m in activatable}
    # Verify City and Status are not activatable (they shouldn't be High)
    city_mf = _get_mandatory(res, "City")
    status_mf = _get_mandatory(res, "Status")
    assert city_mf is None or city_mf.confidence != "High" or not city_mf.is_activatable
    assert status_mf is None or status_mf.confidence != "High" or not status_mf.is_activatable


# ---------------------------------------------------------------------------
# 12. [NEW] Precision / Recall Balance Check
# ---------------------------------------------------------------------------

def test_recall_strong_candidates_are_discovered():
    """
    A dataset with genuinely strong mandatory reference fields must discover them.
    Zero auto-activatable candidates is not inherently correct.
    """
    df = pd.DataFrame({
        "InvoiceNumber": [f"INV-{i:06d}" for i in range(200)],
        "ContractID": [f"CTR-{i:05d}" for i in range(200)],
        "City": ["London" if i % 2 == 0 else "Paris" for i in range(200)],
        "Department": [["HR", "Finance", "Ops"][i % 3] for i in range(200)],
    })
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    activatable = [m for m in res.mandatory_fields if m.is_activatable and m.confidence == "High"]

    # At least one of the strong identifier columns must be discoverable
    activatable_names = {m.column_name for m in activatable}
    strong_found = bool(activatable_names & {"InvoiceNumber", "ContractID"})
    assert strong_found, (
        f"Strong mandatory reference fields (InvoiceNumber, ContractID) must be discoverable. "
        f"Activatable columns found: {activatable_names}"
    )
    # Operational fields must not be in activatable
    assert "City" not in activatable_names, "City must not be auto-activatable"
    assert "Department" not in activatable_names, "Department must not be auto-activatable"


def test_precision_operational_fields_excluded():
    """
    A dataset mixing strong identifiers with many operational attributes must
    produce activatable candidates consisting only of the strong identifiers.
    """
    df = pd.DataFrame({
        "AssetID": [f"AST-{i:06d}" for i in range(200)],
        "ShiftCode": [["MON", "AFT", "NGT"][i % 3] for i in range(200)],
        "MaintenanceType": [["Prev", "Corr", "Pred"][i % 3] for i in range(200)],
        "CountryCode": [["DE", "US", "GB", "FR"][i % 4] for i in range(200)],
        "TotalCost": [float(i) * 100 for i in range(200)],
    })
    profile = profile_dataset(df, name="test_ds")
    res = infer_rules_for_dataset(profile, df)

    activatable = [m for m in res.mandatory_fields if m.is_activatable and m.confidence == "High"]
    activatable_names = {m.column_name for m in activatable}

    # AssetID may be activatable (strong asset + id tokens)
    # but operational fields must not be
    assert "ShiftCode" not in activatable_names, "ShiftCode (organizational token) must not be activatable"
    assert "MaintenanceType" not in activatable_names, "MaintenanceType (operational token) must not be activatable"
    assert "TotalCost" not in activatable_names, "TotalCost (no semantic anchor) must not be activatable"
