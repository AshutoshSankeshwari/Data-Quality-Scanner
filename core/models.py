"""
core/models.py
Shared result data model for the Migration Data Quality Scanner.
All dataclasses are JSON-serializable via dataclasses.asdict().
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class ReadinessCategory(str, Enum):
    READY = "READY"
    MINOR_CLEANSING = "READY WITH MINOR CLEANSING"
    NEEDS_CLEANSING = "NEEDS CLEANSING"
    NOT_READY = "NOT READY"


class ColumnType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    BOOLEAN = "boolean"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class QualityDimension(str, Enum):
    COMPLETENESS = "Completeness"
    UNIQUENESS = "Uniqueness"
    VALIDITY = "Validity"
    CONSISTENCY = "Consistency"
    INTEGRITY = "Integrity"
    CLEANLINESS = "Cleanliness"


# Authoritative mapping from issue check categories to Quality Dimensions
CATEGORY_TO_DIMENSION: dict[str, str] = {
    # Duplicates -> Uniqueness (derived from _score_uniqueness)
    "Duplicates": QualityDimension.UNIQUENESS.value,

    # Mandatory & Missing values -> Completeness (derived from _score_completeness)
    "Mandatory Fields": QualityDimension.COMPLETENESS.value,
    "Nulls/Blanks": QualityDimension.COMPLETENESS.value,
    "Nulls": QualityDimension.COMPLETENESS.value,

    # Formatting noise -> Cleanliness (derived from _score_cleanliness)
    "Whitespace": QualityDimension.CLEANLINESS.value,

    # Conformance & Invalid entries -> Validity (derived from _score_validity)
    "Dates": QualityDimension.VALIDITY.value,
    "Special Characters": QualityDimension.VALIDITY.value,

    # Uniformity of representations -> Consistency (derived from _score_consistency)
    "Date Formats": QualityDimension.CONSISTENCY.value,
    "Patterns": QualityDimension.CONSISTENCY.value,

    # Relational integrity -> Integrity (derived from _score_integrity)
    "Relationships": QualityDimension.INTEGRITY.value,
}


def get_dimension_for_category(category: str) -> str:
    """
    Resolve authoritative Quality Dimension for a given issue category.
    Explicitly returns 'Unclassified' if category is unmapped to prevent silent misclassification.
    """
    dim = CATEGORY_TO_DIMENSION.get(category)
    if dim is None:
        return "Unclassified"
    return dim


# ---------------------------------------------------------------------------
# Column-level Profile
# ---------------------------------------------------------------------------

@dataclass
class ColumnProfile:
    name: str
    inferred_type: ColumnType
    total_count: int
    null_count: int
    null_pct: float
    blank_count: int           # empty-string count
    blank_pct: float
    whitespace_only_count: int
    whitespace_only_pct: float
    unique_count: int
    cardinality_ratio: float   # unique / total
    top_values: list[dict]     # [{"value": x, "count": n}]

    # Numeric stats (filled only when inferred_type in {INTEGER, FLOAT})
    numeric_min: Optional[float] = None
    numeric_max: Optional[float] = None
    numeric_mean: Optional[float] = None
    numeric_median: Optional[float] = None
    numeric_std: Optional[float] = None

    # String stats (filled only when inferred_type == STRING)
    str_min_len: Optional[int] = None
    str_max_len: Optional[int] = None

    # Date stats (filled only when inferred_type == DATE)
    date_min: Optional[str] = None
    date_max: Optional[str] = None
    date_invalid_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Dataset-level Profile
# ---------------------------------------------------------------------------

@dataclass
class DatasetProfile:
    name: str                  # filename stem or user-assigned name
    row_count: int
    column_count: int
    columns: list[ColumnProfile] = field(default_factory=list)
    duplicate_row_count: int = 0
    duplicate_row_pct: float = 0.0
    overall_null_pct: float = 0.0
    size_bytes: Optional[int] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    is_primary: bool = False


# ---------------------------------------------------------------------------
# Check Results
# ---------------------------------------------------------------------------

@dataclass
class DuplicateResult:
    dataset_name: str
    full_row_duplicate_count: int
    full_row_duplicate_pct: float
    key_based_results: list[dict] = field(default_factory=list)
    # key_based_results: [{"key_columns": [...], "duplicate_count": n, "duplicate_pct": f, "samples": [...]}]
    severity: Severity = Severity.INFO
    sample_duplicates: list[dict] = field(default_factory=list)
    affected_row_indices: list[int] = field(default_factory=list)

    def has_issues(self) -> bool:
        return self.full_row_duplicate_count > 0 or any(
            r.get("duplicate_count", 0) > 0 for r in self.key_based_results
        )


@dataclass
class NullBlankResult:
    dataset_name: str
    # per_column: [{"column": name, "null_count": n, "null_pct": f,
    #               "blank_count": n, "blank_pct": f,
    #               "whitespace_only_count": n, "whitespace_only_pct": f,
    #               "severity": Severity}]
    per_column: list[dict] = field(default_factory=list)
    affected_row_indices: list[int] = field(default_factory=list)

    def has_issues(self) -> bool:
        return any(
            c.get("null_count", 0) > 0 or c.get("blank_count", 0) > 0 or c.get("whitespace_only_count", 0) > 0
            for c in self.per_column
        )


@dataclass
class MandatoryFieldResult:
    dataset_name: str
    mandatory_fields: list[str]
    failing_record_count: int
    total_records: int
    failing_pct: float
    # per_field: [{"field": name, "missing_count": n, "missing_pct": f}]
    per_field: list[dict] = field(default_factory=list)
    severity: Severity = Severity.INFO
    affected_row_indices: list[int] = field(default_factory=list)

    def has_issues(self) -> bool:
        return self.failing_record_count > 0


@dataclass
class WhitespaceResult:
    dataset_name: str
    # per_column: [{"column": name, "leading_count": n, "trailing_count": n,
    #               "multi_internal_count": n, "sample_values": [...], "severity": "Low"}]
    per_column: list[dict] = field(default_factory=list)
    severity: Severity = Severity.LOW
    affected_row_indices: list[int] = field(default_factory=list)

    def has_issues(self) -> bool:
        return any(
            c.get("leading_count", 0) + c.get("trailing_count", 0) + c.get("multi_internal_count", 0) > 0
            for c in self.per_column
        )


@dataclass
class SpecialCharResult:
    dataset_name: str
    # per_column: [{"column": name, "rule_name": str, "violation_count": n,
    #               "violation_pct": f, "sample_offenders": [...], "severity": Severity}]
    per_column: list[dict] = field(default_factory=list)
    affected_row_indices: list[int] = field(default_factory=list)

    def has_issues(self) -> bool:
        return any(c.get("violation_count", 0) > 0 for c in self.per_column)


@dataclass
class PatternResult:
    dataset_name: str
    # per_column: [{"column": name,
    #               "clusters": [{"pattern": str, "count": n, "pct": f, "is_dominant": bool}],
    #               "dominant_pattern": str,
    #               "has_case_inconsistency": bool,
    #               "has_structural_inconsistency": bool, "severity": "Low"}]
    per_column: list[dict] = field(default_factory=list)
    severity: Severity = Severity.LOW
    affected_row_indices: list[int] = field(default_factory=list)

    def has_issues(self) -> bool:
        return any(
            c.get("has_case_inconsistency") or c.get("has_structural_inconsistency")
            for c in self.per_column
        )


@dataclass
class DateResult:
    dataset_name: str
    # per_column: [{"column": name,
    #               "invalid_count": n, "invalid_pct": f,
    #               "format_clusters": [{"format": str, "count": n}],
    #               "dominant_format": str,
    #               "has_inconsistency": bool,
    #               "impossible_date_count": n,
    #               "severity": Severity}]
    per_column: list[dict] = field(default_factory=list)
    affected_row_indices: list[int] = field(default_factory=list)

    def has_issues(self) -> bool:
        return any(c.get("invalid_count", 0) > 0 or c.get("has_inconsistency") for c in self.per_column)


@dataclass
class RelationshipResult:
    parent_dataset: str
    child_dataset: str
    parent_key: str
    child_key: str
    total_child_records: int
    orphan_count: int
    orphan_pct: float
    severity: Severity = Severity.INFO
    description: str = ""
    sample_orphan_records: list[dict] = field(default_factory=list)
    origin: str = "configured"  # "configured" or "automatic"
    automatically_confirmed: bool = False
    affected_row_indices: list[int] = field(default_factory=list)

    @property
    def is_automatically_detected(self) -> bool:
        return self.origin == "automatic"

    @property
    def origin_display(self) -> str:
        return "Configured Rule" if self.origin == "configured" else "Automatically Detected"

    @property
    def status(self) -> str:
        return "PASSED" if self.orphan_count == 0 else "FAILED"

    def has_issues(self) -> bool:
        return self.orphan_count > 0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    name: str           # e.g. "Completeness"
    score: float        # 0–100
    weight: float       # 0–1
    weighted: float     # score * weight
    explanation: str    # human-readable rationale


@dataclass
class ScoreBreakdownItem:
    category: str
    dataset_name: str
    target: str          # column name, key set, or relationship pair
    severity: str
    weight: float
    affected_count: int
    total_records: int
    affected_ratio: float
    volume_scaler: float
    penalty: float


@dataclass
class ScoreBreakdown:
    items: list[ScoreBreakdownItem] = field(default_factory=list)
    total_penalty: float = 0.0
    raw_score: float = 100.0
    display_score: float = 100.0


@dataclass
class ReadinessScore:
    overall: float
    category: ReadinessCategory
    dimensions: list[DimensionScore]
    blocker_count: int   # Critical severity issues
    high_count: int
    medium_count: int
    low_count: int
    raw_score: float = 100.0
    breakdown: Optional[ScoreBreakdown] = None


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    title: str
    description: str
    severity: Severity
    affected_columns: list[str]
    issue_type: str       # e.g. "duplicates", "nulls", "date_format"
    dataset_name: str


from core.inference.models import InferredRulesResult


# ---------------------------------------------------------------------------
# Timestamp Formatting Helper
# ---------------------------------------------------------------------------

def format_display_timestamp(val: Any) -> str:
    """
    Format a timestamp (datetime object or ISO formatted string) into human-readable format:
    'DD MMM YYYY, hh:mm AM/PM' (e.g. '07 Sep 2026, 04:40 PM').
    Safely falls back to original string or '—' if empty/invalid.
    """
    if val is None:
        return "—"
    if isinstance(val, datetime):
        return val.strftime("%d %b %Y, %I:%M %p")

    s = str(val).strip()
    if not s or s in ("—", "None", "null"):
        return "—"

    try:
        clean = s.replace("Z", "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%b-%Y %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            pass

    return s


# ---------------------------------------------------------------------------
# Top-level Analysis Result
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """
    Top-level container produced by the Analysis Service.
    Consumed by GUI screens, report generators, and the optional AI layer.
    """
    run_id: str
    timestamp: str
    datasets: list[DatasetProfile]
    enabled_checks: list[str]

    duplicate_results: list[DuplicateResult] = field(default_factory=list)
    null_blank_results: list[NullBlankResult] = field(default_factory=list)
    mandatory_field_results: list[MandatoryFieldResult] = field(default_factory=list)
    whitespace_results: list[WhitespaceResult] = field(default_factory=list)
    special_char_results: list[SpecialCharResult] = field(default_factory=list)
    pattern_results: list[PatternResult] = field(default_factory=list)
    date_results: list[DateResult] = field(default_factory=list)
    relationship_results: list[RelationshipResult] = field(default_factory=list)

    # Inferred business rules recommendations (V2.5 Prototype)
    inferred_rules: list[InferredRulesResult] = field(default_factory=list)

    score: Optional[ReadinessScore] = None
    recommendations: list[Recommendation] = field(default_factory=list)
    ai_insights: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    affected_rows_count: Optional[int] = None

    def primary_dataset(self) -> Optional[DatasetProfile]:
        return self.datasets[0] if self.datasets else None

    @property
    def display_timestamp(self) -> str:
        """Human-readable timestamp for UI and reports (DD MMM YYYY, hh:mm AM/PM)."""
        return format_display_timestamp(self.timestamp)


# ---------------------------------------------------------------------------
# Branding Configuration Model
# ---------------------------------------------------------------------------

@dataclass
class LeftLogoConfig:
    """Configuration for an individual left-side branding logo."""
    enabled: bool = True
    file: str = ""


@dataclass
class BrandingConfig:
    """Typed branding configuration loaded from config/admin_config.yaml."""
    title: str = "Data Quality Scanner"
    description: str = "Pre-Migration Data Quality Assessment"
    logo_enabled: bool = True
    logo_file: str = "assets/branding/company_logo.png"
    logo_size: int = 56
    left_logos: list[LeftLogoConfig] = field(default_factory=list)

