"""
core/inference/models.py
Data models for the V2.5 Automatic Rule Inference prototype.
All models are pure in-memory dataclasses used for evaluation and recommendation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InferredMandatoryField:
    """
    Recommendation for a single column regarding whether it should be treated as mandatory.

    is_mandatory:    inference believes the field has mandatory characteristics
                     (True for High and Medium confidence).
    is_activatable:  inference believes it is safe to automatically activate this field
                     (True only for High-confidence fields within the MAX_AUTO_MANDATORY_FIELDS cap).
                     Only activatable fields enter the user confirmation popup and
                     resolve_effective_rules() automatic activation workflow.
    """
    column_name: str
    confidence: str          # "High", "Medium", "Low", "Uncertain"
    confidence_score: float  # 0.0 to 1.0
    is_mandatory: bool       # True if the engine recommends treating this as mandatory
    is_activatable: bool = True   # True if eligible for automatic confirmation popup / activation
    reasons: list[str] = field(default_factory=list)  # Human-readable rationale bullet points


@dataclass
class InferredIdentityKey:
    """
    Recommendation for a candidate record-identity / duplicate-detection key.
    Can be a single column or a composite key combination.
    """
    columns: list[str]       # List of column names (e.g. ["Customer_ID"] or ["Order_ID", "Line_No"])
    is_composite: bool
    confidence: str          # "High", "Medium", "Low"
    confidence_score: float  # 0.0 to 1.0
    uniqueness_ratio: float  # Distinct count / total count (or joint distinct ratio for composite)
    null_rate: float         # Missing value percentage (0.0 to 100.0)
    reasons: list[str] = field(default_factory=list)  # Human-readable rationale bullet points


@dataclass
class InferredRulesResult:
    """
    Container for all inferred rule recommendations for a single dataset.
    """
    dataset_name: str
    mandatory_fields: list[InferredMandatoryField] = field(default_factory=list)
    suggested_identity_key: Optional[InferredIdentityKey] = None
    alternative_identity_keys: list[InferredIdentityKey] = field(default_factory=list)
    rejected_identity_candidates: list[dict] = field(default_factory=list)
