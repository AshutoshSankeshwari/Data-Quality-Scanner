"""
core/inference/rule_inferrer.py
Intelligent, profile-driven heuristic inference engine for V2.5.

Automatically infers candidate mandatory fields and record-identity / duplicate keys
from dataset profiling and generic column properties without hardcoded dataset rules.

=== MANDATORY-FIELD INFERENCE (recalibrated V2.5) ===

Uses a five-phase scoring pipeline:

  Phase 1 — Semantic / Business-Role Anchor   (primary driver)
  Phase 2 — Population / Completeness Modifier
  Phase 3 — Structural / Cardinality Modifier
  Phase 4 — Optional / Operational Penalties
  Phase 5 — Minimum Semantic-Anchor Gate

Core principles:
  - Completeness strengthens a semantically credible candidate; it cannot create one.
  - Identity-likeness ≠ Mandatory-ness. The two concepts share vocabulary but not logic.
  - Phase 3 structural signals are gated: they contribute nothing when Phase 1 anchor == 0.
  - Phase 4 operational tokens are weighted negative evidence, not hard exclusions.
  - The Phase 5 gate caps non-semantic fields at Medium ceiling (0.44), regardless of data.

=== IDENTITY-KEY INFERENCE (unchanged from V2) ===

Uses separate, independent multi-signal scoring for record identity and composite-key search.
Small-dataset safeguards, false-positive rejections, and bounded composite-key exploration
are preserved exactly as implemented in V2.
"""
from __future__ import annotations
import re
from typing import Optional
import pandas as pd

from core.models import ColumnProfile, DatasetProfile, ColumnType
from core.inference.models import (
    InferredMandatoryField,
    InferredIdentityKey,
    InferredRulesResult,
)


# ---------------------------------------------------------------------------
# Safety cap: maximum number of auto-activatable High-confidence mandatory
# candidates per dataset. A safety ceiling, not a target.
# ---------------------------------------------------------------------------

MAX_AUTO_MANDATORY_FIELDS = 8


# ---------------------------------------------------------------------------
# Generic Token Sets (Normalized lowercase tokens)
# Used for BOTH mandatory-field and identity-key inference.
# Shared vocabulary; separate scoring logic and weights.
# ---------------------------------------------------------------------------

# --- Mandatory inference token sets ---

# Tier 1 (Phase 1 anchor +0.35): Core record / entity key semantics.
# Identity signal — necessary but not sufficient for mandatory status.
_MANDATORY_TIER1_TOKENS = {
    "id", "identifier", "code", "num", "number", "no", "key", "pk", "uuid", "guid",
}

# Tier 2 (Phase 1 anchor +0.25): Business transaction / operation reference handles.
# These name patterns suggest a field is a primary handle for a business object.
_MANDATORY_TIER2_TOKENS = {
    "ref", "reference", "sku", "serial", "order", "workorder",
    "batch", "invoice", "tracking", "asset", "contract", "purchase",
}

# Tier 3 (Phase 1 anchor +0.10): Core entity attribute names.
# Important but weaker mandatory evidence; often non-unique across populations.
_MANDATORY_TIER3_TOKENS = {
    "name", "title", "email", "phone",
}

# Phase 4 operational penalty sub-groups.
# These tokens reduce mandatory confidence. They are negative evidence, not hard exclusions.
# Penalties from multiple matching sub-groups stack.

_OPERATIONAL_GEO_TOKENS = {
    "city", "country", "region", "province", "zone", "territory", "district",
}

_OPERATIONAL_ORG_TOKENS = {
    "shift", "department", "dept", "supervisor", "inspector",
    "operator", "carrier", "driver",
}

_OPERATIONAL_FINANCIAL_TOKENS = {
    "cost", "tax", "discount", "rate", "margin", "fee", "budget", "revenue",
}

_OPERATIONAL_OPS_TOKENS = {
    "maintenance", "inspection", "packaging", "priority", "warranty",
}

_FREE_TEXT_TOKENS = {
    "note", "notes", "desc", "description", "comment", "comments",
    "remark", "remarks", "feedback", "memo", "summary", "details",
    "reason", "explanation", "message", "text", "body", "narrative",
}

# Used only for optional penalty (combined)
_OPTIONAL_TOKENS = {
    "alt", "secondary", "fax", "middle", "suffix", "prefix",
    "addr2", "address2", "line2", "optional", "temp", "extra",
    "misc", "promo",
}

# --- Identity inference token sets (unchanged from V2) ---

_STRONG_ID_TOKENS = {
    "id", "identifier", "code", "num", "number", "no", "key", "pk", "fk",
    "uuid", "guid", "ref", "reference", "sku", "ssn", "account_no", "acct_no",
    "cust_id", "customer_id", "order_id", "product_id", "emp_id", "user_id",
}

_CATEGORICAL_NON_IDENTITY_TOKENS = {
    "city", "state", "country", "status", "type", "category", "gender",
    "sex", "age", "date", "notes", "description", "amount", "price",
    "quantity", "total", "balance", "zip", "postal", "department", "dept",
    "role", "region", "province", "flag", "active", "enabled", "is_active",
    "marital_status", "tier", "level", "division", "territory", "zone",
}

_NAME_TOKENS = {
    "name", "first_name", "last_name", "firstname", "lastname", "fname",
    "lname", "full_name", "fullname", "client_name", "customer_name",
    "employee_name", "holder_name", "holdername", "user_name", "username",
}

_METRIC_TOKENS = {
    "amount", "price", "total", "balance", "cost", "rate", "quantity", "qty",
    "sum", "subtotal", "tax", "discount", "fee", "margin", "weight", "height",
}


def _tokenize_name(name: str) -> set[str]:
    """Split column name into normalized lowercase semantic tokens."""
    # Split on underscore, hyphen, space, dot
    parts = re.split(r"[_\-\s\.]+", name)
    tokens = set()
    for part in parts:
        if not part:
            continue
        # Split CamelCase tokens (e.g. CustomerID -> Customer, ID)
        camel_parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", part)
        if camel_parts:
            for cp in camel_parts:
                tokens.add(cp.lower())
        else:
            tokens.add(part.lower())
    # Also add full normalized name as token
    tokens.add(name.lower().replace(" ", "_").replace("-", "_"))
    return tokens


# ---------------------------------------------------------------------------
# Mandatory-Field Inference: Five-Phase Pipeline
# ---------------------------------------------------------------------------

def infer_mandatory_fields(
    profile: DatasetProfile,
    df: pd.DataFrame | None = None,
) -> list[InferredMandatoryField]:
    """
    Infer candidate mandatory fields for every column using a five-phase scoring pipeline.

    Pipeline:
      Phase 1 — Semantic / Business-Role Anchor     (primary driver; stored as semantic_anchor)
      Phase 2 — Population / Completeness Modifier
      Phase 3 — Structural / Cardinality Modifier   (gated on semantic_anchor > 0)
      Phase 4 — Optional / Operational Penalties    (negative evidence, not hard exclusions)
      Phase 5 — Minimum Semantic-Anchor Gate        (cap at 0.44 if semantic_anchor < 0.15)

    The is_activatable flag is set by the caller (infer_rules_for_dataset) after applying
    the MAX_AUTO_MANDATORY_FIELDS cap.
    """
    results: list[InferredMandatoryField] = []
    row_count = profile.row_count

    for col in profile.columns:
        tokens = _tokenize_name(col.name)
        total_missing_pct = col.null_pct + col.blank_pct + col.whitespace_only_pct
        reasons: list[str] = []
        score = 0.0

        # ----------------------------------------------------------------
        # Phase 1 — Semantic / Business-Role Anchor
        # Tiers are mutually exclusive, evaluated in priority order.
        # Only the highest-priority matching tier contributes.
        # ----------------------------------------------------------------
        semantic_anchor = 0.0

        if tokens & _MANDATORY_TIER1_TOKENS:
            semantic_anchor = 0.35
            matched = sorted(tokens & _MANDATORY_TIER1_TOKENS)
            reasons.append(f"Identifier / record-key naming semantics ({', '.join(matched)})")
        elif tokens & _MANDATORY_TIER2_TOKENS:
            semantic_anchor = 0.25
            matched = sorted(tokens & _MANDATORY_TIER2_TOKENS)
            reasons.append(f"Business reference / transaction handle semantics ({', '.join(matched)})")
        elif tokens & _MANDATORY_TIER3_TOKENS:
            semantic_anchor = 0.10
            matched = sorted(tokens & _MANDATORY_TIER3_TOKENS)
            reasons.append(f"Core entity attribute naming ({', '.join(matched)})")
        # Tier 4 (no match): semantic_anchor remains 0.0

        score = semantic_anchor

        # ----------------------------------------------------------------
        # Phase 2 — Population / Completeness Modifier
        # Completeness modulates the anchor; it does not originate it.
        # Maximum contribution is +0.20 (100% populated).
        # ----------------------------------------------------------------
        if total_missing_pct == 0.0:
            if row_count < 10:
                score += 0.12
                reasons.append(f"100% populated in small sample ({row_count} rows)")
            else:
                score += 0.20
                reasons.append("100% populated (0.0% missing values)")
        elif total_missing_pct <= 1.0:
            score += 0.12
            reasons.append(f"Near-complete population ({total_missing_pct:.1f}% missing)")
        elif total_missing_pct <= 5.0:
            score += 0.04
            reasons.append(f"Mostly populated ({total_missing_pct:.1f}% missing)")
        elif total_missing_pct <= 15.0:
            score -= 0.20
            reasons.append(f"{total_missing_pct:.1f}% missing values indicates optional or un-enforced attribute")
        elif total_missing_pct <= 30.0:
            score -= 0.45
            reasons.append(f"High missing rate ({total_missing_pct:.1f}%) strongly suggests optional field")
        else:
            score -= 0.75
            reasons.append(f"Very high missing rate ({total_missing_pct:.1f}%) confirms optional attribute")

        # ----------------------------------------------------------------
        # Phase 3 — Structural / Cardinality Modifier
        # These signals strengthen a credible semantic candidate.
        # GATE: contributes nothing when semantic_anchor == 0.0.
        # The cardinality bonus requires semantic_anchor >= 0.25 because
        # high cardinality is an identity signal, not a mandatory-role signal.
        # ----------------------------------------------------------------
        if semantic_anchor > 0.0:
            if col.inferred_type in (ColumnType.DATE, ColumnType.INTEGER,
                                     ColumnType.FLOAT, ColumnType.BOOLEAN):
                if total_missing_pct == 0.0:
                    score += 0.08
                    reasons.append(f"Structured {col.inferred_type.value} type with complete population")
            elif col.inferred_type == ColumnType.STRING:
                min_l = col.str_min_len or 0
                max_l = col.str_max_len or 0
                if max_l > 0 and (max_l - min_l <= 5) and total_missing_pct == 0.0:
                    score += 0.06
                    reasons.append("Consistent, fixed-width string format with complete population")
                elif max_l > 100 or (max_l - min_l > 40):
                    score -= 0.20
                    reasons.append("Variable-length free text format suggests descriptive notes")

            # Cardinality bonus only when anchor indicates a reference/key role
            # Use 0.09 so Tier-1 + complete + consistent-format + high-cardinality reaches
            # exactly 0.70 (High): 0.35 + 0.20 + 0.06 + 0.09 = 0.70
            if semantic_anchor >= 0.25 and col.cardinality_ratio >= 0.90 and total_missing_pct == 0.0:
                score += 0.09
                reasons.append(f"High uniqueness ratio ({col.cardinality_ratio:.2f}) consistent with primary reference")

        # Phase 3 explicitly contributes nothing when semantic_anchor == 0.0.
        # numeric + 100% populated + high cardinality alone cannot imply mandatory status.

        # ----------------------------------------------------------------
        # Phase 4 — Optional / Operational Penalties
        # Negative evidence: reduces confidence but is NOT a hard exclusion.
        # Multiple matching sub-groups stack.
        # ----------------------------------------------------------------
        if tokens & _OPERATIONAL_GEO_TOKENS:
            score -= 0.30
            matched = sorted(tokens & _OPERATIONAL_GEO_TOKENS)
            reasons.append(f"Geographic / regional attribute ({', '.join(matched)}): less likely to be universally mandatory")

        if tokens & _OPERATIONAL_ORG_TOKENS:
            score -= 0.30
            matched = sorted(tokens & _OPERATIONAL_ORG_TOKENS)
            reasons.append(f"Organizational / HR attribute ({', '.join(matched)}): context-dependent, not typically mandatory")

        if tokens & _OPERATIONAL_FINANCIAL_TOKENS:
            score -= 0.25
            matched = sorted(tokens & _OPERATIONAL_FINANCIAL_TOKENS)
            reasons.append(f"Financial metric attribute ({', '.join(matched)}): often optional or computed")

        if tokens & _OPERATIONAL_OPS_TOKENS:
            score -= 0.25
            matched = sorted(tokens & _OPERATIONAL_OPS_TOKENS)
            reasons.append(f"Operational / maintenance attribute ({', '.join(matched)}): context-dependent field")

        if tokens & _FREE_TEXT_TOKENS:
            score -= 0.35
            matched = sorted(tokens & _FREE_TEXT_TOKENS)
            reasons.append(f"Free-text / auxiliary attribute ({', '.join(matched)}): descriptive, not typically mandatory")

        if tokens & _OPTIONAL_TOKENS:
            score -= 0.25
            matched = sorted(tokens & _OPTIONAL_TOKENS)
            reasons.append(f"Optional / auxiliary attribute naming ({', '.join(matched)})")

        # ----------------------------------------------------------------
        # Phase 5 — Minimum Semantic-Anchor Gate
        # Applied AFTER all modifiers, using the PRE-MODIFIER semantic_anchor
        # (stored from Phase 1). Completeness and structure cannot bypass
        # the semantic requirement.
        # ----------------------------------------------------------------
        if semantic_anchor < 0.15:
            score = min(score, 0.44)
            if semantic_anchor == 0.0:
                reasons.append("No semantic business-role evidence; capped at Medium ceiling regardless of population/structure")
            else:
                reasons.append("Insufficient semantic anchor for High confidence; capped at Medium ceiling")

        # Small-dataset safeguard on mandatory confidence (preserved from V2)
        if row_count < 10 and score > 0.55 and semantic_anchor < 0.35:
            score = 0.50
            reasons.append("Small sample (< 10 rows) limits statistical confidence without explicit strong ID semantics")

        # Normalize and clamp
        confidence_score = round(max(0.0, min(1.0, score)), 2)

        # Confidence tiers (thresholds unchanged from V2)
        if confidence_score >= 0.70:
            confidence = "High"
            is_mandatory = True
        elif confidence_score >= 0.45:
            confidence = "Medium"
            is_mandatory = True
        elif confidence_score >= 0.20:
            confidence = "Low"
            is_mandatory = False
        else:
            confidence = "Uncertain"
            is_mandatory = False

        results.append(InferredMandatoryField(
            column_name=col.name,
            confidence=confidence,
            confidence_score=confidence_score,
            is_mandatory=is_mandatory,
            is_activatable=True,  # set by infer_rules_for_dataset after cap is applied
            reasons=reasons,
        ))

    # Sort: High confidence first, then Medium, Low, Uncertain; break ties by score desc then name
    conf_order = {"High": 0, "Medium": 1, "Low": 2, "Uncertain": 3}
    results.sort(key=lambda r: (conf_order.get(r.confidence, 4), -r.confidence_score, r.column_name))
    return results


def _apply_activatable_cap(
    mandatory_fields: list[InferredMandatoryField],
) -> list[InferredMandatoryField]:
    """
    Apply the MAX_AUTO_MANDATORY_FIELDS safety ceiling.

    Only the top MAX_AUTO_MANDATORY_FIELDS High-confidence results (by score) are marked
    is_activatable=True. Remaining High-confidence results beyond the cap are preserved
    in the list for diagnostics/testing but marked is_activatable=False.

    This is a ceiling, not a target. If fewer than MAX_AUTO_MANDATORY_FIELDS genuine
    High-confidence columns exist, all of them are activatable.
    """
    high_confidence_count = 0
    for field in mandatory_fields:
        if field.confidence == "High":
            if high_confidence_count < MAX_AUTO_MANDATORY_FIELDS:
                field.is_activatable = True
                high_confidence_count += 1
            else:
                field.is_activatable = False
                field.reasons.append(
                    f"Beyond MAX_AUTO_MANDATORY_FIELDS cap ({MAX_AUTO_MANDATORY_FIELDS}): "
                    f"available for diagnostics but not auto-activated"
                )
        else:
            # Medium / Low / Uncertain: never auto-activatable
            field.is_activatable = False
    return mandatory_fields


# ---------------------------------------------------------------------------
# Identity / Duplicate-Key Inference (unchanged from V2)
# ---------------------------------------------------------------------------

def _score_single_identity_candidate(
    col: ColumnProfile,
    row_count: int = 100,
) -> tuple[float, list[str], bool]:
    """
    Score a single column as an identity key candidate.
    Returns (score, reasons, is_rejected).
    Includes strict categorical/name rejections and small-sample safeguards.
    THIS FUNCTION IS UNCHANGED FROM V2.
    """
    tokens = _tokenize_name(col.name)
    total_missing_pct = col.null_pct + col.blank_pct + col.whitespace_only_pct
    reasons: list[str] = []

    has_strong_id = bool(tokens & _STRONG_ID_TOKENS)
    has_categorical = bool(tokens & _CATEGORICAL_NON_IDENTITY_TOKENS)
    has_name = bool(tokens & _NAME_TOKENS)
    has_free_text = bool(tokens & _FREE_TEXT_TOKENS)

    # Rejection Rule 1: High missing values
    if total_missing_pct > 2.0:
        return 0.0, [f"High missing rate ({total_missing_pct:.1f}% nulls/blanks); identity keys must not have nulls"], True

    # Rejection Rule 2: Low uniqueness / categorical attribute
    if col.cardinality_ratio < 0.50:
        return 0.0, [f"Low uniqueness ratio ({col.cardinality_ratio:.1%}, many repeated values); categorical attribute"], True

    # Rejection Rule 3: Categorical semantics without strong ID token
    if has_categorical and not has_strong_id:
        return 0.0, [f"Categorical attribute semantics ({', '.join(sorted(tokens & _CATEGORICAL_NON_IDENTITY_TOKENS))})"], True

    # Rejection Rule 4: Free-form long text
    if has_free_text:
        return 0.0, ["Descriptive / free-text attribute semantics"], True

    if col.inferred_type == ColumnType.STRING:
        min_l = col.str_min_len or 0
        max_l = col.str_max_len or 0
        if max_l > 80 or (max_l - min_l > 50):
            return 0.0, [f"High text length variance ({min_l}-{max_l} chars); free-form text is not an identity key"], True

    # Rejection Rule 5: Pure names without strong ID semantics
    if has_name and not has_strong_id:
        return 0.0, ["Entity/person name attribute (names are descriptive and can repeat legitimately in populations)"], True

    # Multi-signal affinity scoring
    score = 0.0

    # 1. Uniqueness Signal (0.0 to 0.45)
    score += col.cardinality_ratio * 0.45
    reasons.append(f"{col.cardinality_ratio:.1%} uniqueness ratio ({col.unique_count:,} distinct values)")

    # 2. Completeness Signal (0.0 to 0.20)
    score += (1.0 - total_missing_pct / 100.0) * 0.20
    reasons.append(f"{100.0 - total_missing_pct:.1f}% populated (0% nulls)")

    # 3. Semantic Token Signal
    if has_strong_id:
        score += 0.25
        reasons.append("Strong identifier naming semantics (e.g. 'ID', 'Code', 'Key')")
    elif "email" in tokens:
        score += 0.10
        reasons.append("Email contact attribute (potential secondary identifier)")
    elif has_name:
        score -= 0.15
        reasons.append("Entity name attribute (secondary identifying power)")

    # 4. Value Pattern / Mask Signal
    if col.inferred_type in (ColumnType.INTEGER, ColumnType.STRING):
        min_l = col.str_min_len or 0
        max_l = col.str_max_len or 0
        if max_l > 0 and (max_l - min_l <= 4):
            score += 0.10
            reasons.append("Consistent identifier length and format")

    # 5. Small-Dataset Safeguard
    if row_count < 10:
        score = min(0.40, score - 0.35)
        reasons.append(f"Small sample size ({row_count} rows) severely limits statistical uniqueness certainty")
    elif row_count < 30:
        score -= 0.15
        reasons.append(f"Moderate sample size ({row_count} rows) reduces statistical uniqueness certainty")

    final_score = round(max(0.0, min(1.0, score)), 2)
    return final_score, reasons, False


def infer_identity_keys(
    profile: DatasetProfile,
    df: pd.DataFrame | None = None,
    max_candidates: int = 5,
) -> tuple[Optional[InferredIdentityKey], list[InferredIdentityKey], list[dict]]:
    """
    Infer suggested and alternative identity keys using multi-signal heuristics.
    Includes bounded composite-key search among top K candidate columns and small-sample safeguards.
    Returns (suggested_key, alternative_keys, rejected_candidates).
    THIS FUNCTION IS UNCHANGED FROM V2.
    """
    candidate_keys: list[InferredIdentityKey] = []
    rejected_candidates: list[dict] = []
    viable_single_columns: list[tuple[ColumnProfile, float, list[str]]] = []
    row_count = profile.row_count

    # 1. Evaluate single columns
    for col in profile.columns:
        score, reasons, is_rejected = _score_single_identity_candidate(col, row_count=row_count)
        total_missing = col.null_pct + col.blank_pct + col.whitespace_only_pct

        if is_rejected:
            rejected_candidates.append({
                "column": col.name,
                "reason": reasons[0] if reasons else "Rejected",
                "uniqueness_ratio": col.cardinality_ratio,
            })
            continue

        confidence = "High" if score >= 0.70 else "Medium" if score >= 0.45 else "Low"
        key = InferredIdentityKey(
            columns=[col.name],
            is_composite=False,
            confidence=confidence,
            confidence_score=score,
            uniqueness_ratio=round(col.cardinality_ratio, 4),
            null_rate=round(total_missing, 2),
            reasons=reasons,
        )
        candidate_keys.append(key)
        viable_single_columns.append((col, score, reasons))

    # 2. Bounded Composite-Key Search
    if df is not None and len(df) > 0:
        composite_pool: list[ColumnProfile] = []
        for col in profile.columns:
            total_missing = col.null_pct + col.blank_pct + col.whitespace_only_pct
            tokens = _tokenize_name(col.name)
            has_metric = bool(tokens & _METRIC_TOKENS) and not bool(tokens & _STRONG_ID_TOKENS)
            if total_missing <= 2.0 and col.cardinality_ratio >= 0.05 and col.inferred_type != ColumnType.UNKNOWN:
                if not (tokens & _FREE_TEXT_TOKENS) and not has_metric:
                    min_l = col.str_min_len or 0
                    max_l = col.str_max_len or 0
                    if max_l - min_l <= 50:
                        composite_pool.append(col)

        def _pool_rank(c: ColumnProfile) -> float:
            toks = _tokenize_name(c.name)
            bonus = 0.3 if toks & _STRONG_ID_TOKENS else 0.1 if toks & _NAME_TOKENS else 0.0
            return c.cardinality_ratio + bonus

        composite_pool.sort(key=_pool_rank, reverse=True)
        bounded_pool = composite_pool[:max_candidates]

        n_pool = len(bounded_pool)
        for i in range(n_pool):
            for j in range(i + 1, n_pool):
                col_a = bounded_pool[i]
                col_b = bounded_pool[j]

                if col_a.name not in df.columns or col_b.name not in df.columns:
                    continue

                joint_distinct = df[[col_a.name, col_b.name]].drop_duplicates().shape[0]
                joint_uniqueness = round(joint_distinct / len(df), 4)

                if joint_uniqueness >= 0.95 and col_a.cardinality_ratio < 0.98 and col_b.cardinality_ratio < 0.98:
                    tokens_a = _tokenize_name(col_a.name)
                    tokens_b = _tokenize_name(col_b.name)
                    comp_score = joint_uniqueness * 0.40

                    reasons = [
                        f"{joint_uniqueness:.1%} combined uniqueness ratio across record pairs",
                        f"Combines {col_a.name} ({col_a.cardinality_ratio:.1%} unique) and {col_b.name} ({col_b.cardinality_ratio:.1%} unique)",
                        "Complete population across both attributes",
                    ]

                    if (tokens_a & _STRONG_ID_TOKENS) or (tokens_b & _STRONG_ID_TOKENS):
                        comp_score += 0.35
                        reasons.append("Contains structured identifier component")

                    if row_count < 10:
                        comp_score = min(0.35, comp_score - 0.35)
                        reasons.append("Small sample (< 10 rows) limits composite uniqueness significance")
                    elif row_count < 30:
                        comp_score -= 0.15
                        reasons.append("Moderate sample (< 30 rows) reduces composite uniqueness certainty")

                    comp_score = round(max(0.0, min(1.0, comp_score)), 2)
                    conf = "High" if comp_score >= 0.70 else "Medium" if comp_score >= 0.45 else "Low"

                    comp_key = InferredIdentityKey(
                        columns=[col_a.name, col_b.name],
                        is_composite=True,
                        confidence=conf,
                        confidence_score=comp_score,
                        uniqueness_ratio=joint_uniqueness,
                        null_rate=round(max(col_a.null_pct, col_b.null_pct), 2),
                        reasons=reasons,
                    )
                    candidate_keys.append(comp_key)

    # 3. Sort candidates
    candidate_keys.sort(key=lambda k: (-k.confidence_score, k.is_composite, -k.uniqueness_ratio))

    suggested_key: Optional[InferredIdentityKey] = None
    alternative_keys: list[InferredIdentityKey] = []

    if candidate_keys:
        suggested_key = candidate_keys[0]
        alternative_keys = candidate_keys[1:4]

    return suggested_key, alternative_keys, rejected_candidates


# ---------------------------------------------------------------------------
# Dataset Inferrer Orchestration
# ---------------------------------------------------------------------------

def infer_rules_for_dataset(
    profile: DatasetProfile,
    df: pd.DataFrame | None = None,
    max_composite_candidates: int = 5,
) -> InferredRulesResult:
    """
    Run full automatic business-rule inference for a single dataset.
    Returns InferredRulesResult containing mandatory field and identity key recommendations.

    Mandatory fields are scored via the 5-phase pipeline and the MAX_AUTO_MANDATORY_FIELDS
    safety cap is applied before returning.
    """
    mandatory = infer_mandatory_fields(profile, df)
    mandatory = _apply_activatable_cap(mandatory)

    suggested_id, alt_ids, rejected = infer_identity_keys(profile, df, max_candidates=max_composite_candidates)

    return InferredRulesResult(
        dataset_name=profile.name,
        mandatory_fields=mandatory,
        suggested_identity_key=suggested_id,
        alternative_identity_keys=alt_ids,
        rejected_identity_candidates=rejected,
    )
