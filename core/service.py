"""
core/service.py
Application / Service Layer.
Orchestrates a full analysis run: ingest → profile → checks → score → recommend.
Called identically by the GUI and the CLI — no logic is duplicated in either.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, Callable

import pandas as pd

from core.models import AnalysisResult
from core.profiling.profiler import profile_dataset
from core.inference import infer_rules_for_dataset, InferredRulesResult
from core.checks.duplicates import check_full_row_duplicates, check_key_based_duplicates
from core.checks.nulls import check_nulls_and_blanks
from core.checks.mandatory_fields import check_mandatory_fields
from core.checks.whitespace import check_whitespace
from core.checks.special_chars import check_special_chars
from core.checks.patterns import check_patterns
from core.checks.dates import check_dates
from core.checks.relationships import check_relationships
from core.checks.relationship_discovery import detect_and_validate_relationships
from core.scoring.scorer import calculate_score
from core.recommendations.recommender import generate_recommendations
from reports.summary_builder import count_affected_rows


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AnalysisCancelledError(Exception):
    """Raised when an analysis run is cancelled by the user during interactive confirmation."""
    pass


# ---------------------------------------------------------------------------
# Run configuration dataclass (avoids a long parameter list)
# ---------------------------------------------------------------------------

class AnalysisConfig:
    """
    All configuration needed for a single analysis run.
    Populated from config/config.yaml and config/admin_config.yaml,
    or from GUI inputs.
    """
    DEFAULT_CHECKS = [
        "duplicates", "nulls", "mandatory_fields", "whitespace",
        "special_chars", "patterns", "dates", "relationships",
    ]

    def __init__(
        self,
        # Check toggles
        enabled_checks: list[str] | None = None,
        # Mandatory fields
        mandatory_fields: list[str] | None = None,
        # Duplicate key sets e.g. [["Customer_ID"], ["Email"]]
        duplicate_key_sets: list[list[str]] | None = None,
        # Special char field rules: {column_name: preset_name}
        field_character_rules: dict[str, str] | None = None,
        character_rule_presets: dict[str, str] | None = None,
        anomaly_characters: list[str] | None = None,
        # Date check
        date_columns: list[str] | None = None,
        accepted_date_formats: list[str] | None = None,
        date_column_hints: list[str] | None = None,
        # Pattern check
        pattern_exclude_columns: list[str] | None = None,
        min_pattern_cluster_size: int = 2,
        max_cardinality_ratio: float = 0.95,
        # Relationships (list of dicts)
        relationships: list[dict] | None = None,
        # Scoring (Issue-driven)
        severity_weights: dict[str, float] | None = None,
        readiness_thresholds: dict[str, int] | None = None,
        # Duplicate thresholds
        duplicate_high_threshold: float = 5.0,
        duplicate_medium_threshold: float = 1.0,
        # Null thresholds
        null_high_threshold: float = 20.0,
        null_medium_threshold: float = 5.0,
        # Row count warning
        row_count_warning_threshold: int = 500_000,
    ):
        self.enabled_checks = set(
            enabled_checks
            if enabled_checks is not None
            else self.DEFAULT_CHECKS
        )
        self.mandatory_fields = mandatory_fields or []
        self.duplicate_key_sets = duplicate_key_sets or []
        self.field_character_rules = field_character_rules or {}
        self.character_rule_presets = character_rule_presets or {}
        self.anomaly_characters = anomaly_characters if anomaly_characters is not None else ["$", "@", "#", "%", "&", "*"]
        self.date_columns = date_columns
        self.accepted_date_formats = accepted_date_formats
        self.date_column_hints = date_column_hints
        self.pattern_exclude_columns = pattern_exclude_columns or []
        self.min_pattern_cluster_size = min_pattern_cluster_size
        self.max_cardinality_ratio = max_cardinality_ratio
        self.relationships = relationships or []
        self.severity_weights = severity_weights
        self.readiness_thresholds = readiness_thresholds
        self.duplicate_high_threshold = duplicate_high_threshold
        self.duplicate_medium_threshold = duplicate_medium_threshold
        self.null_high_threshold = null_high_threshold
        self.null_medium_threshold = null_medium_threshold
        self.row_count_warning_threshold = row_count_warning_threshold


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

def resolve_effective_rules(
    cfg: AnalysisConfig,
    inferred: Optional[InferredRulesResult],
    mandatory_confirmation_callback: Optional[Callable[[list[str]], bool]] = None,
) -> tuple[list[str], Optional[list[list[str]]]]:
    """
    Resolve effective mandatory fields and duplicate keys by combining
    explicit configuration with high-confidence inferred rules.

    Principles:
    1. Explicit config is always retained (never discarded or overridden).
    2. High-confidence inferred rules supplement unconfigured fields/keys.
    3. Medium / Low / Uncertain inferred candidates are not automatically activated.
    4. Duplicate logical rules are deduplicated (no duplicate rules or penalties).
    5. Configured and inferred identity keys coexist as independent key sets.
    6. If neither configured nor high-confidence inferred keys exist, duplicate keys is None (triggers full-row).
    7. User confirmation for new inferred mandatory fields can be requested via mandatory_confirmation_callback.
    """
    # 1. Mandatory Fields Resolution: Configured + High-Confidence Inferred
    effective_mandatory_fields: list[str] = list(cfg.mandatory_fields) if cfg.mandatory_fields else []
    seen_mandatory = set(effective_mandatory_fields)

    new_inferred_mandatory: list[str] = []
    if inferred and inferred.mandatory_fields:
        for f in inferred.mandatory_fields:
            # Only High-confidence AND is_activatable fields enter the popup / automatic activation.
            # is_activatable=False for Medium/Low/Uncertain and for High fields beyond the
            # MAX_AUTO_MANDATORY_FIELDS safety cap set during infer_rules_for_dataset().
            if f.confidence == "High" and f.is_mandatory and f.is_activatable:
                if f.column_name not in seen_mandatory and f.column_name not in new_inferred_mandatory:
                    new_inferred_mandatory.append(f.column_name)


    if new_inferred_mandatory:
        if mandatory_confirmation_callback is not None:
            proceed = bool(mandatory_confirmation_callback(list(new_inferred_mandatory)))
            if not proceed:
                raise AnalysisCancelledError("Analysis run cancelled by user during mandatory fields confirmation.")
            for col in new_inferred_mandatory:
                if col not in seen_mandatory:
                    effective_mandatory_fields.append(col)
                    seen_mandatory.add(col)
        else:
            # Batch mode / headless tests without callback: auto-apply high-confidence rules
            for col in new_inferred_mandatory:
                if col not in seen_mandatory:
                    effective_mandatory_fields.append(col)
                    seen_mandatory.add(col)

    # 2. Duplicate / Identity Keys Resolution: Configured + High-Confidence Inferred Key
    effective_duplicate_keys: list[list[str]] = [list(ks) for ks in cfg.duplicate_key_sets] if cfg.duplicate_key_sets else []

    def _key_sig(cols: list[str]) -> tuple[str, ...]:
        return tuple(sorted(cols))

    seen_keys = {_key_sig(ks) for ks in effective_duplicate_keys}

    if inferred and inferred.suggested_identity_key and inferred.suggested_identity_key.confidence == "High":
        sig = _key_sig(inferred.suggested_identity_key.columns)
        if sig not in seen_keys:
            effective_duplicate_keys.append(list(inferred.suggested_identity_key.columns))
            seen_keys.add(sig)

    resolved_keys = effective_duplicate_keys if len(effective_duplicate_keys) > 0 else None

    return effective_mandatory_fields, resolved_keys


class AnalysisService:
    """
    Stateless analysis service.
    Call run() to execute a full analysis and get back an AnalysisResult.
    """

    def run(
        self,
        datasets: list[tuple[str, pd.DataFrame]],
        config: Optional[AnalysisConfig] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        mandatory_confirmation_callback: Optional[Callable[[list[str]], bool]] = None,
    ) -> AnalysisResult:
        """
        Execute a full analysis run.

        Args:
            datasets: List of (dataset_name, DataFrame) pairs.
                      The first dataset is treated as the primary.
            config: Analysis configuration. Defaults to all checks on.
            progress_callback: Optional callable(step_name, 0-100) for UI progress.
            mandatory_confirmation_callback: Optional callable(new_fields: list[str]) -> bool
                                             confirming whether newly inferred mandatory fields
                                             should be applied.

        Returns:
            A fully populated AnalysisResult.
        """
        cfg = config or AnalysisConfig()
        run_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat(timespec="seconds")
        warnings: list[str] = []

        def _progress(step: str, pct: float):
            if progress_callback:
                try:
                    progress_callback(step, pct)
                except Exception:
                    pass

        # ----------------------------------------------------------------
        # Step 1: Profiling
        # ----------------------------------------------------------------
        _progress("Profiling datasets…", 5)
        dataset_profiles = []
        df_map: dict[str, pd.DataFrame] = {}

        for i, (name, df) in enumerate(datasets):
            if len(df) > cfg.row_count_warning_threshold:
                warnings.append(
                    f"Dataset '{name}' has {len(df):,} rows — large file, analysis may be slow."
                )
            file_type = getattr(df, "attrs", {}).get("file_type", "CSV" if ".csv" in name.lower() or not ".xls" in name.lower() else "Excel")
            file_path = getattr(df, "attrs", {}).get("file_path", name)
            profile = profile_dataset(
                df,
                name=name,
                file_path=str(file_path),
                file_type=str(file_type),
                is_primary=(i == 0),
            )
            dataset_profiles.append(profile)
            df_map[name] = df

        result = AnalysisResult(
            run_id=run_id,
            timestamp=timestamp,
            datasets=dataset_profiles,
            enabled_checks=list(cfg.enabled_checks),
            warnings=warnings,
        )

        # ----------------------------------------------------------------
        # Step 1b: Automatic Business-Rule Inference & Rule Resolution (V2.5)
        # ----------------------------------------------------------------
        _progress("Inferring business rules…", 10)
        for profile in dataset_profiles:
            ds_df = df_map.get(profile.name)
            inferred = infer_rules_for_dataset(profile, ds_df)
            result.inferred_rules.append(inferred)

        primary_name = datasets[0][0] if datasets else "dataset"
        primary_df = datasets[0][1] if datasets else pd.DataFrame()
        primary_inferred = result.inferred_rules[0] if result.inferred_rules else None

        # Rule Resolution (V2.5): Configured rules are retained and supplemented with High-confidence inference
        effective_mandatory_fields, effective_duplicate_keys = resolve_effective_rules(
            cfg, primary_inferred, mandatory_confirmation_callback=mandatory_confirmation_callback
        )

        # ----------------------------------------------------------------
        # Step 2: Quality checks on primary dataset
        # ----------------------------------------------------------------
        _progress("Checking duplicates…", 15)
        if "duplicates" in cfg.enabled_checks:
            if effective_duplicate_keys:
                dr = check_key_based_duplicates(
                    primary_df,
                    effective_duplicate_keys,
                    primary_name,
                    high_threshold=cfg.duplicate_high_threshold,
                    medium_threshold=cfg.duplicate_medium_threshold,
                )
            else:
                dr = check_full_row_duplicates(
                    primary_df,
                    primary_name,
                    high_threshold=cfg.duplicate_high_threshold,
                    medium_threshold=cfg.duplicate_medium_threshold,
                )
            result.duplicate_results.append(dr)

        _progress("Checking nulls & blanks…", 25)
        if "nulls" in cfg.enabled_checks:
            nb = check_nulls_and_blanks(
                primary_df, primary_name,
                mandatory_fields=effective_mandatory_fields,
                high_threshold=cfg.null_high_threshold,
                medium_threshold=cfg.null_medium_threshold,
            )
            result.null_blank_results.append(nb)

        _progress("Checking mandatory fields…", 35)
        if "mandatory_fields" in cfg.enabled_checks and effective_mandatory_fields:
            mf = check_mandatory_fields(primary_df, effective_mandatory_fields, primary_name)
            result.mandatory_field_results.append(mf)

        _progress("Checking whitespace…", 45)
        if "whitespace" in cfg.enabled_checks:
            ws = check_whitespace(primary_df, primary_name)
            result.whitespace_results.append(ws)

        _progress("Checking special characters…", 55)
        if "special_chars" in cfg.enabled_checks and (cfg.field_character_rules or cfg.anomaly_characters):
            sc = check_special_chars(
                primary_df,
                field_rules=cfg.field_character_rules,
                character_rule_presets=cfg.character_rule_presets,
                anomaly_characters=cfg.anomaly_characters,
                dataset_name=primary_name,
            )
            result.special_char_results.append(sc)

        _progress("Checking patterns…", 65)
        if "patterns" in cfg.enabled_checks:
            pr = check_patterns(
                primary_df,
                exclude_columns=cfg.pattern_exclude_columns,
                min_cluster_size=cfg.min_pattern_cluster_size,
                max_cardinality_ratio=cfg.max_cardinality_ratio,
                dataset_name=primary_name,
            )
            result.pattern_results.append(pr)

        _progress("Checking dates…", 73)
        if "dates" in cfg.enabled_checks:
            dr_date = check_dates(
                primary_df,
                date_columns=cfg.date_columns,
                accepted_formats=cfg.accepted_date_formats,
                date_column_hints=cfg.date_column_hints,
                dataset_name=primary_name,
            )
            result.date_results.append(dr_date)

        # ----------------------------------------------------------------
        # Step 3: Relationship Validation (Configured & Automatically Detected)
        # ----------------------------------------------------------------
        _progress("Validating relationships…", 80)
        checked_pairs: set[tuple[str, str, str, str]] = set()

        if len(datasets) >= 2:
            # 1. Configured relationships (if defined in config)
            if "relationships" in cfg.enabled_checks and cfg.relationships:
                for rel in cfg.relationships:
                    parent_name = rel.get("parent_dataset", "")
                    child_name = rel.get("child_dataset", "")
                    parent_key = rel.get("parent_key", "")
                    child_key = rel.get("child_key", "")
                    p_df = df_map.get(parent_name)
                    c_df = df_map.get(child_name)
                    if p_df is None or c_df is None:
                        warnings.append(
                            f"Relationship check skipped: dataset '{parent_name}' or "
                            f"'{child_name}' not loaded."
                        )
                        continue
                    rr = check_relationships(
                        p_df, c_df,
                        parent_key=parent_key,
                        child_key=child_key,
                        parent_dataset_name=parent_name,
                        child_dataset_name=child_name,
                        description=rel.get("description", ""),
                    )
                    rr.origin = "configured"
                    rr.automatically_confirmed = False
                    result.relationship_results.append(rr)

                    p_k_str = parent_key if isinstance(parent_key, str) else ", ".join(parent_key)
                    c_k_str = child_key if isinstance(child_key, str) else ", ".join(child_key)
                    checked_pairs.add((parent_name, p_k_str, child_name, c_k_str))

            # 2. Automatic Relationship Detection & Integrity Validation
            detected_rels = detect_and_validate_relationships(datasets)
            for det in detected_rels:
                det_p_k = det.parent_key if isinstance(det.parent_key, str) else ", ".join(det.parent_key)
                det_c_k = det.child_key if isinstance(det.child_key, str) else ", ".join(det.child_key)
                pair_key = (det.parent_dataset, det_p_k, det.child_dataset, det_c_k)

                if pair_key in checked_pairs:
                    # Configured relationship is authoritative; flag configured result as internally confirmed
                    for r in result.relationship_results:
                        p_r_k = r.parent_key if isinstance(r.parent_key, str) else ", ".join(r.parent_key)
                        c_r_k = r.child_key if isinstance(r.child_key, str) else ", ".join(r.child_key)
                        if (r.parent_dataset, p_r_k, r.child_dataset, c_r_k) == pair_key:
                            r.automatically_confirmed = True
                            # Keep r.origin = "configured"
                    continue

                # Automatically detected relationship not present in config
                det.origin = "automatic"
                det.automatically_confirmed = False
                result.relationship_results.append(det)
                checked_pairs.add(pair_key)

        # ----------------------------------------------------------------
        # Step 4: Scoring & Metrics
        # ----------------------------------------------------------------
        result.affected_rows_count = count_affected_rows(result)

        _progress("Calculating readiness score…", 88)
        result.score = calculate_score(
            result,
            severity_weights=cfg.severity_weights,
            thresholds=cfg.readiness_thresholds,
        )

        # ----------------------------------------------------------------
        # Step 5: Recommendations
        # ----------------------------------------------------------------
        _progress("Generating recommendations…", 95)
        result.recommendations = generate_recommendations(result)

        _progress("Done.", 100)
        return result
