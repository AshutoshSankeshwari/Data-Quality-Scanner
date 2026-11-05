# Data Quality Scanner (V3 Foundation) — Technical Design Document

## 1. System Architecture

The application adopts a strictly layered architecture enforcing a **single source of truth** across presentation, persistence, and reporting.

```text
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│   PySide6 Desktop GUI (main.py) │   │ Headless Batch (batch_runner.py)│
│  (Scrollable Dashboard, Gauge)  │   │     (CLI Runner, No Qt)         │
└────────────────┬────────────────┘   └────────────────┬────────────────┘
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│            Application / Service Layer (core/service.py)               │
├────────────────────────────────────────────────────────────────────────┤
│                     Core Data Quality Engine                           │
│   ├── Ingestion (core/ingestion - CSV, Excel loading & validation)     │
│   ├── Profiling (core/profiling - dataset & column statistics)         │
│   ├── Rule Inference (core/inference - 5-phase calibrated pipeline)    │
│   ├── Rule Resolution (explicit config priority, additive supplement)  │
│   ├── Checks (core/checks - canonical check functions)                 │
│   ├── Relationship Discovery & Integrity (relationship_discovery)     │
│   ├── Issue-Driven Scoring Engine (core/scoring - exact deductions)    │
│   └── Recommendation Engine (core/recommendations - prioritized)       │
├────────────────────────────────────────────────────────────────────────┤
│                     Configuration Architecture                         │
│   ├── User Business Rules (config/config.yaml - datasets, fields, keys)│
│   └── Admin Parameters (config/admin_config.yaml - checks, thresholds) │
├────────────────────────────────────────────────────────────────────────┤
│           Shared Serializable Data Model (core/models.py)              │
│       (Includes QualityDimension enum & category-to-dimension map)     │
└────────────┬─────────────────────────────────────────────┬─────────────┘
             │                                             │
             ▼                                             ▼
┌─────────────────────────┐                   ┌─────────────────────────┐
│   SQLite Persistence    │                   │    Report Generators    │
│ (db/ - data/scanner.db) │                   │  (HTML, Excel, JSON)    │
└─────────────────────────┘                   └─────────────────────────┘
```

---

## 2. Key Architectural Guarantees

1. **Dual Execution Interfaces with Single Source of Truth**: The GUI (`main.py`) and headless batch runner (`batch_runner.py`) share the exact same `AnalysisService`, rules, checks, relationship engine, scoring logic, SQLite persistence, and reporting pipelines.
2. **Dual-Layer Configuration Architecture**: Decouples user business expectations (`config.yaml`) from technical strictness parameters (`admin_config.yaml`). Changing either file updates the combined deterministic SHA-256 configuration hash.
3. **Autonomous Rule Resolution & Config-Free Baseline**: Operates autonomously without requiring configuration files. When configuration is present, explicit rules take authoritative precedence and high-confidence inferred rules supplement them.
4. **Headless Execution & Zero GUI Coupling**: `batch_runner.py` executes without initializing `QApplication` or Qt widgets, allowing headless server, CI/CD, scheduled scripts, and container automation.
5. **Deterministic Scoring & Full Precision**: Reconciled scoring guarantees $\left|\text{raw\_score} - (100 - \sum \text{penalties})\right| < 10^{-9}$. Clean datasets score an exact 100.0.
6. **Data Isolation & Privacy**: Local-first processing with zero network transmission. **Raw dataset rows are NEVER stored in SQLite**; only metadata, check violations, diagnostic scores, relationship validations, and recommendations are persisted.
7. **Automatic Database Initialization**: Database connections auto-initialize schema on first access via `get_connection()` without requiring manual initialization scripts.
8. **100% Automated Test Coverage**: All core modules, inference phases, scoring algorithms, configuration loaders, database persistence flows, and GUI components are validated by 210 passing automated tests.

---

## 3. Autonomous Business-Rule Inference & Rule Resolution

The inference subsystem (`core/inference/rule_inferrer.py`) executes a 5-phase profile-driven heuristic pipeline:

### 3.1 5-Phase Mandatory-Field Inference Pipeline
1. **Phase 1: Semantic / Business-Role Anchor**: Evaluates column names against entity identifier tokens (`id`, `code`, `key`, `sku`, `po`, `order`, etc.). Columns lacking entity-identifying tokens cannot reach High confidence on completeness alone.
2. **Phase 2: Data Behavior Verification**: Checks empirical completeness (0.0% nulls), high population rates, and string length consistency.
3. **Phase 3: Structural Format & Length Consistency**: Verifies structured shape masking (fixed-width formats, hyphen/digit patterns) and penalizes wide length variations.
4. **Phase 4: Anti-Pattern & False-Positive Guard**: Enforces strict negative masks against operational categoricals, status flags, cost/price/tax metrics, comments, notes, dates, and names.
5. **Phase 5: Multi-Signal Confidence Calibration**: Calculates final confidence score and applies an activation cap ($\le 8$ fields on wide datasets) to prevent confirmation fatigue.

### 3.2 Record Identity & Duplicate-Key Inference
- **Strict Rejections**: Categoricals, person names, free-form text, financial metrics, and columns with $> 2.0\%$ nulls are rejected as single identity keys.
- **Affinity Signals**: Uniqueness ratio $\ge 95\%$, complete population, strong identifier tokens, fixed-width masking.
- **Bounded Composite Key Search**: Evaluates combinations only among the top $K=5$ candidate columns ($\le 10$ pairs evaluated). Requires individual uniqueness $< 98\%$ and joint uniqueness $\ge 95\%$.

### 3.3 Additive Rule Resolution
- Explicit user configuration is always retained and honored.
- High-confidence inferred rules on unconfigured columns supplement missing rules.
- Overlapping rules are merged into a single logical rule to prevent double execution and double penalties.
- In GUI mode, newly inferred mandatory fields prompt the user via `InferredMandatoryConfirmationDialog` before activation.

---

## 4. Deterministic Issue-Driven Scoring Engine

The overall readiness score (0–100) is derived directly from detected quality defects:

$$\text{Penalty}_i = \text{Severity Weight}_i \times (0.05 + 0.95 \times \text{Affected Ratio}_i)$$
$$\text{Overall Score} = \text{clamp}\left(100.0 - \sum_{i \in \text{issues}} \text{Penalty}_i, \; 0.0, \; 100.0\right)$$

### 4.1 Severity Penalty Weights vs. Severity Classifications
- **Critical (15.0 pts)**: Missing mandatory fields, high referential integrity orphan records ($>10\%$).
- **High (8.0 pts)**: High-rate duplicates ($\ge 5\%$), impossible calendar dates, high character format violations ($\ge 10\%$), high null rates ($\ge 20\%$).
- **Medium (3.0 pts)**: Moderate duplicates ($1–5\%$), moderate null values ($5–20\%$), date format inconsistencies.
- **Low (1.0 pt)**: Low duplicates ($<1\%$), whitespace noise (leading/trailing/internal), pattern inconsistencies.

### 4.2 Deduplication and Precision Rules
1. **Mandatory & Null Deduplication**: Columns penalized under Mandatory Fields (Critical) are excluded from Null/Blank penalty calculations.
2. **Missing Value Grouping**: Nulls, blanks, and whitespace-only cells in a column are combined into a single logical missing-value count.
3. **Exact Denominators**: Denominators are derived from exact dataset record counts. For referential integrity, the denominator is the child dataset's total record count ($N_{child}$).
4. **Float Precision & Reconciliation**: Calculations maintain full 64-bit IEEE float precision; `calculate_score()` attaches the complete `ScoreBreakdown`.

### 4.3 Quality Dimensions & Category Mapping
Six standalone quality dimensions are evaluated as unweighted diagnostic health metrics: Completeness, Uniqueness, Validity, Consistency, Integrity, and Cleanliness.

Detected issue categories map explicitly to `QualityDimension` enums (`core/models.py`):
- `Mandatory Fields`, `Nulls & Blanks` $\to$ **Completeness**
- `Duplicates (Full Row)`, `Duplicates (Key-Based)` $\to$ **Uniqueness**
- `Special Characters`, `Dates` $\to$ **Validity**
- `Patterns`, `Whitespace` $\to$ **Consistency**
- `Relationships` $\to$ **Integrity**
- Unmapped new categories $\to$ **Unclassified** *(Explicit handling, never silently defaulting to Validity)*

---

## 5. Automatic Relationship Detection & Referential Integrity

The relationship discovery engine (`core/checks/relationship_discovery.py`) automatically evaluates candidate column pairs across uploaded datasets:
- **Signals**: Column name similarity & identifier stems ($30\%$), parent primary-key uniqueness $\ge 85\%$ ($25\%$), child value coverage $\ge 30\%$ ($25\%$), child foreign-key repetition ($15\%$), non-null quality ($5\%$).
- **Integrity Validation**: Evaluates non-null child keys against parent keys, calculating child records, orphan count, orphan percentage, and exact problematic child row numbers and invalid key values.
- **Canonical API**: `core/checks/relationships.py` provides canonical `check_relationships()`.

---

## 6. SQLite Persistence Schema (`data/scanner.db`)

All scans are persisted to a canonical SQLite file at `data/scanner.db` (`DEFAULT_DB_PATH`) using a 6-table star schema rooted at `scans` with cascading foreign keys:
- `scans`: Primary run metadata, execution timestamp, app version, configuration hash, overall score, and issue severity counts.
- `scan_datasets`: Per-dataset profiling metadata, column statistics JSON, null percentages, duplicate counts.
- `check_results`: Aggregated findings per check type and dataset.
- `scoring_factors`: Dimension scores, weights, and explanations.
- `relationship_results`: Referential integrity findings, child/parent keys, orphan counts, percentages, and sample invalid records.
- `recommendations`: Prioritized remediation actions.

---

## 7. V3 Foundation & Future Roadmap

### 7.1 Implemented V3 Foundation
- Separation of User Business Rules (`config/config.yaml`) and Administrator Technical Parameters (`config/admin_config.yaml`).
- Clean duplicate-key normalization (`["Customer_ID", "Email"]` $\to$ `[["Customer_ID"], ["Email"]]`).
- Built-in field character presets eliminating raw regex in configuration files.
- Complete removal of dead modules (`gui/widgets/charts.py`), legacy loaders, and legacy scoring fields.
- 6-column Quality Issues table with Quality Dimension filtering.

### 7.2 Future V3 Capabilities (Planned)
- **Automatic Dataset / Profile Selector**: Multi-signal profile matching comparing uploaded datasets against configured dataset definitions (`datasets:`) with confidence scoring and ambiguity prompts.
- **Date Rule Consolidation**: Future evaluation of date rule syntax and automated format detection.
- **Logical Dataset-Type Relationship Mapping**: Migrating relationship configuration from filenames to logical dataset types.

---

*End of Technical Design Document.*
