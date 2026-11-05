"""
core/checks/relationship_discovery.py
Deterministic automatic relationship detection and referential integrity validation engine.

Evaluates candidate column pairs across datasets using deterministic internal signals:
  1. Column-name similarity and identifier token matching
  2. Data-type compatibility
  3. Parent-key uniqueness ratio (primary key signal)
  4. Child-key repetition / cardinality behavior (foreign key signal)
  5. Value coverage / overlap percentage
  6. False-positive prevention against categorical/status columns

When a relationship is identified, referential integrity is automatically validated,
surfacing exact problematic child row numbers and invalid key values as a RelationshipResult.
"""
from __future__ import annotations
import re
import pandas as pd

from core.models import RelationshipResult, Severity

MAX_EXAMPLES = 20

# Common non-relational descriptive column names that frequently have spurious value overlap
NON_RELATIONAL_KEYWORDS = {
    "status", "country", "gender", "category", "type", "flag", "state", "city",
    "created_date", "updated_date", "order_date", "date", "description", "comment",
    "notes", "quantity", "unit_price", "price", "amount", "credit_limit", "balance",
    "is_active", "is_deleted", "enabled", "role", "priority", "rating",
}

# Standard identifier stems / abbreviations
STEM_SYNONYMS = {
    "cust": "customer",
    "customer": "customer",
    "prod": "product",
    "product": "product",
    "ord": "order",
    "order": "order",
    "supp": "supplier",
    "supplier": "supplier",
    "emp": "employee",
    "employee": "employee",
    "acc": "account",
    "account": "account",
    "dept": "department",
    "department": "department",
    "inv": "invoice",
    "invoice": "invoice",
}


def _normalize_name(name: str) -> str:
    """Lowercase and remove non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _name_similarity(col_a: str, col_b: str, ds_a: str, ds_b: str) -> float:
    """
    Calculate column name similarity between 0.0 and 1.0.
    Considers normalized names, identifier tokens, and stem synonyms.
    """
    norm_a = _normalize_name(col_a)
    norm_b = _normalize_name(col_b)

    if norm_a == norm_b:
        return 1.0

    # Tokenize by underscores/camelCase
    tokens_a = set(re.findall(r"[a-z0-9]+", re.sub(r"([A-Z])", r"_\1", col_a).lower()))
    tokens_b = set(re.findall(r"[a-z0-9]+", re.sub(r"([A-Z])", r"_\1", col_b).lower()))

    # Map stems
    mapped_a = {STEM_SYNONYMS.get(t, t) for t in tokens_a}
    mapped_b = {STEM_SYNONYMS.get(t, t) for t in tokens_b}

    if mapped_a and mapped_b and mapped_a == mapped_b:
        return 0.95

    # Check if both have "id" or "key" and share a root entity
    has_id_a = "id" in mapped_a or "key" in mapped_a or norm_a.endswith("id")
    has_id_b = "id" in mapped_b or "key" in mapped_b or norm_b.endswith("id")

    if has_id_a and has_id_b:
        entities_a = mapped_a - {"id", "key", "num", "no", "code"}
        entities_b = mapped_b - {"id", "key", "num", "no", "code"}
        if entities_a and entities_b and entities_a == entities_b:
            return 0.90
        # If one is just "id" and other is e.g. "customer_id", check if dataset name matches entity
        ds_a_norm = _normalize_name(ds_a)
        ds_b_norm = _normalize_name(ds_b)
        if ("id" in norm_a or norm_a == "id") and entities_b:
            ent = list(entities_b)[0]
            if ent in ds_a_norm:
                return 0.85
        if ("id" in norm_b or norm_b == "id") and entities_a:
            ent = list(entities_a)[0]
            if ent in ds_b_norm:
                return 0.85

    # Jaccard overlap on tokens
    if mapped_a and mapped_b:
        jaccard = len(mapped_a & mapped_b) / len(mapped_a | mapped_b)
        if jaccard > 0.5:
            return 0.70

    return 0.10


def _are_types_compatible(series_a: pd.Series, series_b: pd.Series) -> bool:
    """Check if two series have compatible data types for relationship joining."""
    is_num_a = pd.api.types.is_numeric_dtype(series_a)
    is_num_b = pd.api.types.is_numeric_dtype(series_b)
    
    if is_num_a and is_num_b:
        return True
    if not is_num_a and not is_num_b:
        return True
    return False


def detect_and_validate_relationships(
    datasets: list[tuple[str, pd.DataFrame]],
    internal_detection_threshold: float = 70.0,
) -> list[RelationshipResult]:
    """
    Automatically detect parent-child relationships across uploaded datasets and
    perform referential integrity validation on detected pairs.

    Args:
        datasets: List of (dataset_name, DataFrame) tuples.
        internal_detection_threshold: Internal heuristic threshold score (default: 70.0).

    Returns:
        List of RelationshipResult instances with is_automatically_detected=True.
    """
    if len(datasets) < 2:
        return []

    detected_results: list[RelationshipResult] = []

    # Evaluate each ordered pair of (Dataset_A, Dataset_B) as (Parent, Child)
    for idx_a, (name_a, df_a) in enumerate(datasets):
        if df_a.empty:
            continue
        for idx_b, (name_b, df_b) in enumerate(datasets):
            if idx_a == idx_b or df_b.empty:
                continue

            # Evaluate each column pair: col_a (candidate parent PK) vs col_b (candidate child FK)
            for col_a in df_a.columns:
                norm_col_a = _normalize_name(col_a)
                if norm_col_a in NON_RELATIONAL_KEYWORDS:
                    continue

                series_a = df_a[col_a].dropna()
                if len(series_a) == 0:
                    continue

                # 1. Parent Uniqueness Signal (Primary Key requires high uniqueness)
                parent_distinct_count = series_a.nunique()
                parent_total = len(df_a)
                parent_uniqueness = parent_distinct_count / parent_total

                if parent_uniqueness < 0.85:
                    continue

                parent_unique_score = 1.0 if parent_uniqueness >= 0.99 else 0.80
                parent_values_set = set(series_a.astype(str).str.strip())

                for col_b in df_b.columns:
                    norm_col_b = _normalize_name(col_b)
                    if norm_col_b in NON_RELATIONAL_KEYWORDS:
                        continue

                    series_b = df_b[col_b].dropna()
                    if len(series_b) == 0:
                        continue

                    # 2. Type Compatibility
                    if not _are_types_compatible(series_a, series_b):
                        continue

                    # 3. Name Similarity
                    name_sim = _name_similarity(col_a, col_b, name_a, name_b)

                    # 4. Child Values and Value Coverage
                    child_series_str = series_b.astype(str).str.strip()
                    child_distinct_values = set(child_series_str.unique())
                    child_distinct_count = len(child_distinct_values)

                    if child_distinct_count == 0:
                        continue

                    matched_values = child_distinct_values & parent_values_set
                    matched_count = len(matched_values)
                    coverage_score = matched_count / child_distinct_count

                    # If coverage is too low, reject
                    if coverage_score < 0.30:
                        continue

                    # 5. Child Repetition / Foreign-Key Behavior Signal
                    child_total = len(df_b)
                    child_repetition_ratio = max(0.0, 1.0 - (child_distinct_count / max(1, child_total)))
                    
                    if child_repetition_ratio > 0.10:
                        child_rep_score = 1.0
                    elif child_repetition_ratio > 0.0:
                        child_rep_score = 0.85
                    else:
                        child_rep_score = 0.70

                    # 6. Non-null Ratio Signal
                    non_null_a = len(series_a) / max(1, parent_total)
                    non_null_b = len(series_b) / max(1, child_total)
                    null_score = (non_null_a + non_null_b) / 2.0

                    # 7. False-Positive Prevention Gating
                    if name_sim < 0.40 and coverage_score < 0.85:
                        continue

                    # Calculate internal detection score (0.0 to 100.0)
                    internal_score = round(
                        100.0 * (
                            0.30 * name_sim +
                            0.25 * parent_unique_score +
                            0.25 * coverage_score +
                            0.15 * child_rep_score +
                            0.05 * null_score
                        ),
                        1,
                    )

                    if internal_score < internal_detection_threshold:
                        continue

                    # =========================================================
                    # RELATIONSHIP DETECTED -> Execute Referential Integrity Check
                    # =========================================================
                    orphan_values_set = child_distinct_values - parent_values_set
                    
                    # Count total records in child dataset that have orphan keys
                    child_full_series = df_b[col_b].astype(str).str.strip()
                    orphan_mask = child_full_series.isin(orphan_values_set)
                    orphan_record_count = int(orphan_mask.sum())
                    orphan_pct = round(100.0 * orphan_record_count / max(1, child_total), 2)

                    # Extract sample orphan records with exact child row numbers and invalid values
                    orphan_indices = df_b[orphan_mask].index[:MAX_EXAMPLES]
                    sample_orphan_records = [
                        {
                            "row_number": int(idx + 1),
                            "key_value": str(df_b.loc[idx, col_b]),
                            "child_dataset": name_b,
                            "child_key": col_b,
                            "parent_dataset": name_a,
                            "parent_key": col_a,
                        }
                        for idx in orphan_indices
                    ]

                    # Determine severity
                    if orphan_record_count == 0:
                        severity = Severity.INFO
                    elif orphan_pct > 10:
                        severity = Severity.CRITICAL
                    elif orphan_pct > 2:
                        severity = Severity.HIGH
                    else:
                        severity = Severity.MEDIUM

                    all_orphan_indices = [int(idx + 1) for idx in df_b[orphan_mask].index]

                    detected_results.append(RelationshipResult(
                        parent_dataset=name_a,
                        child_dataset=name_b,
                        parent_key=col_a,
                        child_key=col_b,
                        total_child_records=child_total,
                        orphan_count=orphan_record_count,
                        orphan_pct=orphan_pct,
                        severity=severity,
                        description=f"Automatically detected relationship: {name_b}.{col_b} -> {name_a}.{col_a}",
                        sample_orphan_records=sample_orphan_records,
                        origin="automatic",
                        affected_row_indices=all_orphan_indices,
                    ))

    return detected_results
