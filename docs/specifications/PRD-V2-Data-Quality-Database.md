# PRD 2 — V3 Data Quality Engine, Configuration & Database (Foundation Baseline)

**Project:** Data Quality Scanner (V3 Foundation)
**Document Type:** Data Quality Engine, Configuration & Database PRD
**Version:** 3.0 Foundation (Cleaned V2.5 + V3 Configuration Baseline)
**Status:** Completed & Verified Implementation
**Companion Documents:** `PRD-V2-Architecture.md`, `PRD-V2-UI-UX-Deployment.md`

---

## 1. Objective

Specify the autonomous business-rule inference engine, dual-layer user/admin configuration model, deterministic issue-driven scoring engine, 8 quality checks, quality dimension mappings, and SQLite persistence layer (`data/scanner.db`).

---

## 2. Scope

In scope: automated business-rule inference (5-phase calibrated pipeline, single & composite identity keys, small-sample safeguards), rule resolution and config precedence, config-free execution, dual-layer YAML schemas (`config.yaml` & `admin_config.yaml`), duplicate-key normalization, canonical check execution parameters, issue-driven scoring formulas, Quality Dimension mappings, and SQLite star schema.

Out of scope: GUI presentation (PRD 3), Docker packaging (PRD 3), top-level system architecture (PRD 1), implementation of future V3 automatic profile selector.

---

## 3. Configuration Architecture & Separation of Concerns

The configuration architecture establishes a strict separation between **User Business Rules** and **Administrator Technical Parameters**:

```text
USER CONFIG (config/config.yaml)       ADMIN CONFIG (config/admin_config.yaml)
  - What the data should look like        - How strict the engine should be
  - Dataset business expectations          - Check toggles (checks.enabled)
  - Mandatory fields & duplicate keys      - Technical severity thresholds
  - Field character rule mappings          - Scoring weights & readiness tiers
  - Date formats & hints                   - Anomaly characters & system limits
  - Configured relationships
                     │                                      │
                     └──────────────────┬───────────────────┘
                                        ▼
                           Configuration Loader
                         (rules/config_loader.py)
                                        │
                         Translates & normalizes into
                                        ▼
                                 AnalysisConfig
                                        │
                                        ▼
                                 AnalysisService
```

### 3.1 User Configuration (`config/config.yaml`)

Normal users define dataset-level business expectations without exposure to technical formulas or raw regular expressions:

```yaml
# =============================================================================
# Data Quality Scanner - User Configuration (V3)
# =============================================================================

# 1. Dataset Business Rules
datasets:
  Customer_Master:
    mandatory_fields:
      - Customer_ID
      - Customer_Name
      - Email
      - Phone
      - Country
    duplicate_keys:
      - Customer_ID
      - Email

  Orders:
    mandatory_fields:
      - Order_ID
      - Customer_ID
      - Order_Date
      - Product_ID
      - Quantity
      - Unit_Price
    duplicate_keys:
      - Order_ID

# 2. Field Character Format Rules (maps columns to built-in rule presets)
field_character_rules:
  Customer_ID: alpha_numeric_only
  Email: email_format

# 3. Accepted Date Formats & Column Detection Hints
date_rules:
  accepted_formats:
    - "%Y-%m-%d"
    - "%m/%d/%Y"
    - "%d-%m-%Y"
    - "%d/%m/%Y"
    - "%d %b %Y"
    - "%d-%b-%Y"
    - "%Y/%m/%d"
    - "%m-%d-%Y"
  column_hints:
    - date
    - _dt
    - _at
    - _on
    - created
    - updated
    - modified
    - birth
    - expiry
    - expire
    - timestamp

# 4. Configured Relationships (Referential Integrity)
relationships:
  - parent_dataset: customers_clean_100pct
    parent_key: Customer_ID
    child_dataset: orders_related_to_customers
    child_key: Customer_ID
    description: "Orders must reference a valid Customer"
```

#### Duplicate-Key Normalization
User-facing syntax:
```yaml
duplicate_keys:
  - Customer_ID
  - Email
```
is normalized by `rules/config_loader.py` into the internal representation expected by the duplicate checker:
```python
[["Customer_ID"], ["Email"]]
```
Composite keys defined as YAML lists (e.g. `- [Dept_ID, Org_ID]`) are preserved as composite lists internally: `[["Dept_ID", "Org_ID"]]`.

#### Built-in Character Format Presets
Users map fields to standardized preset names (`alpha_numeric_only`, `email_format`, `numeric_only`, `alpha_only`, `phone_format`, etc.). Built-in regular expression implementations remain canonical in code (`core/checks/special_chars.py`), eliminating raw regex definitions from user YAML files.

---

### 3.2 Administrator Configuration (`config/admin_config.yaml`)

Administrators configure technical engine parameters and calibration thresholds:

```yaml
# =============================================================================
# Data Quality Scanner - Administrator Configuration (V3)
# =============================================================================

# 1. Active Quality Checks Master Toggle
checks:
  enabled:
    - duplicates
    - nulls
    - mandatory_fields
    - whitespace
    - special_chars
    - patterns
    - dates
    - relationships

# 2. Migration Readiness Scoring & Issue Severity Weights
scoring:
  severity_weights:
    critical: 15.0   # Penalty points for Critical issue
    high: 8.0        # Penalty points for High severity issue
    medium: 3.0      # Penalty points for Medium severity issue
    low: 1.0         # Penalty points for Low severity issue
  readiness_thresholds:
    ready: 90            # Minimum score for Ready status
    minor_cleansing: 75  # Minimum score for Ready with Minor Cleansing status
    needs_cleansing: 50  # Minimum score for Needs Cleansing status

# 3. Duplicate Rate Severity Thresholds (% of dataset)
duplicate_rules:
  thresholds:
    high: 5.0
    medium: 1.0

# 4. Null / Blank Severity Thresholds (% of column)
null_rules:
  high_threshold: 20.0
  medium_threshold: 5.0

# 5. Pattern Consistency Clustering Rules
pattern_rules:
  min_cluster_size: 2
  max_cardinality_ratio: 0.95
  exclude_columns: []

# 6. Anomaly Character Scanning
special_chars:
  anomaly_characters:
    - "$"
    - "@"
    - "#"
    - "%"
    - "&"
    - "*"

# 7. System Warning Thresholds
row_count_warning_threshold: 500000
```

#### Check Enablement Semantics
- `enabled_checks is None`: Defaults to all 8 standard checks.
- `enabled_checks == []`: Explicitly runs 0 checks (`set()`).

#### Combined Configuration Hashing
`get_config_hash()` computes a deterministic SHA-256 hash incorporating both `config/config.yaml` and `config/admin_config.yaml`. Changing either file updates the effective configuration hash persisted in SQLite and displayed in reports.

---

## 4. Autonomous Business-Rule Inference (`core/inference/`)

The scanner automatically deduces business rules using profile-driven multi-signal heuristics.

### 4.1 Calibrated 5-Phase Mandatory-Field Inference

To prevent high completeness from misidentifying operational or status columns as mandatory, inference executes across 5 sequential phases:

```text
Column
  │
  ▼
Phase 1: Semantic / Business-Role Anchor (Requires entity-identifying tokens)
  │
  ▼
Phase 2: Data Behavior Verification (Zero nulls, high population, length stability)
  │
  ▼
Phase 3: Structural Format & Length Consistency (Fixed-width masking, structured syntax)
  │
  ▼
Phase 4: Anti-Pattern & False-Positive Guard (Strict rejection of categoricals, metrics, dates, comments)
  │
  ▼
Phase 5: Multi-Signal Confidence Calibration (Scores combined, 8-field activation cap applied)
```

#### Core Invariants
- **Completeness $\ne$ Mandatory-ness**: High completeness alone cannot make a field High-confidence mandatory without structural/semantic evidence.
- **Identity-likeness $\ne$ Mandatory-likeness**: Identity keys and mandatory fields are scored independently.
- **Wide Dataset Cap**: Wide datasets (e.g. 80+ columns) enforce an activation cap ($\le 8$ fields) to prevent confirmation fatigue while preserving genuine entity anchors.

#### Confidence Tiers & Activation
- **High ($\ge 0.70$)**: Eligible for automatic activation (with GUI confirmation popup).
- **Medium ($0.45 - 0.69$)**: Kept as internal diagnostic recommendation; not automatically enforced.
- **Low / Uncertain ($< 0.45$)**: Ignored for enforcement.

### 4.2 Record Identity & Duplicate-Key Inference

1. **Strict False-Positive Rejection Rules**:
   - Categoricals (`city`, `state`, `country`, `status`, `type`, `category`, `gender`, `role`, `dept`, `region`) without strong ID tokens are strictly rejected.
   - Person names (`first_name`, `last_name`, `customer_name`) are rejected as single identity keys.
   - Free-form text (`notes`, `description`, `comments`, `feedback`, `summary`) is strictly rejected.
   - Financial metrics (`amount`, `price`, `total`, `balance`, `cost`, `tax`, `quantity`) are excluded.
   - Columns with $> 2.0\%$ missing values are rejected immediately.
2. **Affinity Signals**:
   - High distinctness ($\ge 95\%$): $+0.45$.
   - Zero nulls: $+0.20$.
   - Strong identifier tokens: $+0.25$.
   - Fixed-width masking: $+0.10$.
3. **Bounded Composite Key Search**:
   - Evaluates combinations only among the top $K=5$ candidate columns ($\le 10$ pairs evaluated).
   - Requires individual uniqueness $< 98\%$ and joint uniqueness $\ge 95\%$.

### 4.3 Small-Dataset Safeguards ($N < 30$ Rows)
- **$N < 10$ rows**: Identity key score penalized by $-0.35$ and capped at $\le 0.40$; mandatory completeness bonus is halved.
- **$10 \le N < 30$ rows**: Identity key score penalized by $-0.15$.

---

## 5. Quality Checks Specification

All 8 quality checks operate as pure functions over DataFrames:

| Check Module | Canonical Function | Implemented Logic | Severity Classification |
|---|---|---|---|
| **Mandatory Fields** | `check_mandatory_fields()` | Validates presence and non-null status of resolved mandatory fields. | **Critical**: Any failing or missing mandatory column. |
| **Duplicates** | `check_full_row_duplicates()`, `check_key_based_duplicates()` | Evaluates resolved duplicate keys or full-row duplicates. | **High** ($\ge 5.0\%$), **Medium** ($1.0\% - 4.9\%$), **Low** ($< 1.0\%$). |
| **Nulls & Blanks** | `check_nulls_and_blanks()` | Flags null, blank, and whitespace-only cells across non-mandatory columns. | **Critical** (if mandatory), otherwise **High** ($\ge 20\%$), **Medium** ($5\% - 20\%$), **Low** ($< 5\%$). |
| **Relationships** | `check_relationships()`, `detect_and_validate_relationships()` | Validates referential integrity against parent datasets with exact invalid references. | **Critical** ($> 10\%$ orphans), **High** ($2\% - 10\%$), **Medium** ($< 2\%$). |
| **Special Characters** | `check_special_chars()` | Detects unprintable characters, configured anomaly symbols, and regex violations. | **High** ($\ge 10\%$), **Medium** ($2\% - 10\%$), **Low** ($< 2\%$). |
| **Dates** | `check_dates()` | Validates calendar validity (leap years, month bounds) and format consistency. | **High** (impossible dates), **Medium** (format inconsistencies), **Low** (minor variances). |
| **Whitespace** | `check_whitespace()` | Detects leading, trailing, and multi-internal whitespace anomalies. | **Low**: Standard formatting noise. |
| **Patterns** | `check_patterns()` | Masks string structures (A-Z $\to$ A, 0-9 $\to$ 9) to detect structural outliers. | **Low**: Standard formatting noise. |

---

## 6. Deterministic Issue-Driven Scoring Engine (`core/scoring/scorer.py`)

### 6.1 Mathematical Formula

The overall readiness score (0–100) is derived directly and deterministically from detected defects:

$$\text{Penalty}_i = \text{Severity Weight}_i \times (0.05 + 0.95 \times \text{Affected Ratio}_i)$$

$$\text{Overall Score} = \text{clamp}\left(100.0 - \sum_{i \in \text{issues}} \text{Penalty}_i, \; 0.0, \; 100.0\right)$$

### 6.2 Severity Penalty Points vs. Severity Classification

- **Severity Penalty Weights** (from `admin_config.yaml`):
  - `Critical`: **15.0** points
  - `High`: **8.0** points
  - `Medium`: **3.0** points
  - `Low`: **1.0** point

### 6.3 Scoring Precision & Deduplication Rules

1. **Mandatory & Null Deduplication**: Columns penalized under Mandatory Fields (Critical) are excluded from Null/Blank penalty calculations.
2. **Missing Value Grouping**: Nulls, blanks, and whitespace-only cells in a column are combined into a single logical missing-value count.
3. **Exact Denominators**: Affected ratio is calculated against exact dataset row counts. For relationships, the denominator is the child dataset's total record count ($N_{child}$).
4. **Full Float Precision & Reconciliation**: Calculations maintain full 64-bit float precision; `calculate_score()` attaches the complete `ScoreBreakdown` verifying $\left|\text{raw\_score} - (100 - \sum \text{penalties})\right| < 10^{-9}$.

### 6.4 Diagnostic Quality Dimensions & Category Mapping

Six standalone dimensions provide independent health percentages (0–100) and do not feed into the overall score formula. Detected issue categories map deterministically to quality dimensions:

| Check Category | Quality Dimension (`QualityDimension`) |
|---|---|
| `Mandatory Fields`, `Nulls & Blanks` | **Completeness** |
| `Duplicates (Full Row)`, `Duplicates (Key-Based)` | **Uniqueness** |
| `Special Characters`, `Dates` | **Validity** |
| `Patterns`, `Whitespace` | **Consistency** |
| `Relationships` | **Integrity** |
| *(Any unmapped new category)* | **Unclassified** *(Explicit handling, never silently defaulting to Validity)* |

---

## 7. SQLite Persistence Schema (`data/scanner.db`)

All scan history is persisted to `data/scanner.db` (`DEFAULT_DB_PATH`) using a 6-table star schema.

### 7.1 Schema Architecture
- **Automatic Initialization**: `get_connection()` guarantees schema verification and creation via `schema.sql` on first access (obsolete `init_db()` helper removed).
- **No Raw Record Storage**: Uploaded dataset rows are never written to SQLite.
- **Star Schema**:
  - `scans` (root): `id`, `run_id`, `started_at`, `completed_at`, `app_version`, `config_hash`, `overall_score`, `issue_count_critical`, `issue_count_high`, `issue_count_medium`, `issue_count_low`.
  - `scan_datasets`: `id`, `scan_id` (FK), `dataset_name`, `filename`, `row_count`, `column_count`.
  - `check_results`: `id`, `scan_id` (FK), `dataset_name`, `check_type`, `severity`, `affected_count`, `affected_pct`, `summary_json`.
  - `scoring_factors`: `id`, `scan_id` (FK), `dimension_name`, `dimension_score`, `weight`, `explanation`.
  - `relationship_results`: `id`, `scan_id` (FK), `parent_dataset`, `child_dataset`, `parent_key`, `child_key`, `orphan_count`, `orphan_pct`, `sample_orphans_json`.
  - `recommendations`: `id`, `scan_id` (FK), `title`, `description`, `severity`, `issue_type`, `dataset_name`.
- **Historical Reconstruction**: Previous scans can be fully restored to the GUI dashboard and re-exported as HTML/Excel/JSON reports without the original data files.

---

## 8. Removed Legacy Infrastructure

The following legacy components have been verified and permanently removed:
- Legacy config loaders: `load_rules()`, `load_mandatory_fields()`, `load_relationships()`, `build_analysis_config_from_rules()`.
- Legacy scoring fields: `scoring_weights`, `mandatory_field_multiplier`, `scoring_factor_explanations`.
- Duplicate scoring functions: `get_score_breakdown()`.
- Unused helper methods: `init_db()`, `DatasetProfile.get_column()`, `InferredIdentityKey.display_name`, `export_duplicate_records()`, `export_orphan_records()`.
- Legacy configuration toggles: `whitespace_rules.enabled`.

---

*End of PRD 2.*
