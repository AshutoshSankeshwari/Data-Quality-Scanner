# PRD 1 — V3 Architecture & Application Design (Foundation Baseline)

**Project:** Data Quality Scanner (V3 Foundation)
**Document Type:** Product & System Architecture PRD
**Version:** 3.0 Foundation (Cleaned V2.5 + V3 Configuration Baseline)
**Status:** Completed & Verified Implementation
**Predecessor Document:** `PRD-Migration-Data-Quality-Scanner.md` (V1, historical baseline, unchanged)

---

## 1. Objective

Define the overall system architecture for the Data Quality Scanner: a simplified, single-page, autonomous, and configuration-driven desktop application and headless batch engine with automated business-rule inference, dual-layer user/admin configuration, SQLite persistence, and Docker packaging.

This PRD covers structure, component responsibilities, configuration architecture, and end-to-end execution flow. Detailed check/config/database specifications are in `PRD-V2-Data-Quality-Database.md`; UI layout and deployment mechanics are in `PRD-V2-UI-UX-Deployment.md`.

---

## 2. Scope

In scope: overall layered architecture, GUI/core separation, service-layer orchestration, dual-layer configuration (User `config.yaml` & Admin `admin_config.yaml`), automated business-rule inference, rule resolution & configuration precedence, config-free operation, headless batch mode, persistence layer placement, report-generation placement, error handling, logging, startup sequence, end-to-end data flow, and architectural readiness for future V3 automatic dataset/profile selection.

Out of scope: exact SQLite schema (PRD 2), exact UI widget layout (PRD 3), implementation of the future automatic dataset/profile selector (future V3 milestone).

---

## 3. Architecture Objectives

- **ARCH-001**: Maintain a streamlined architectural surface area, free of dead modules, legacy loaders, and redundant scoring code.
- **ARCH-002**: Maintain the single scrolling page GUI without complex sidebars or multi-screen workflows.
- **ARCH-003**: Separate User Business Rules (`config/config.yaml`) from Administrator Technical Parameters (`config/admin_config.yaml`).
- **ARCH-004**: Preserve automated business-rule inference (`core/inference/`) to deduce candidate mandatory fields and identity keys without requiring manual YAML configuration for baseline analysis.
- **ARCH-005**: Maintain the Rule Resolution layer where explicit configuration takes authoritative precedence over inferred recommendations, with confirmation popups in Desktop GUI before new mandatory fields are activated.
- **ARCH-006**: Support config-free autonomous execution when `config.yaml` is absent.
- **ARCH-007**: Maintain the SQLite persistence layer (`data/scanner.db`) for scan history and results shared across GUI and batch modes without storing raw data rows.
- **ARCH-008**: Maintain the headless batch execution interface (`batch_runner.py`) with manual `--profile` selection support for CI/CD, scripting, and container automation.
- **ARCH-009**: Maintain Docker packaging for reproducible runtime.
- **ARCH-010**: Preserve the core Python + PySide6 stack with 100% automated test coverage.

---

## 4. Summary of Changes Across Generations

| Area | V1 | V2 Baseline | V2.5 Implemented | V3 Foundation (Current State) |
|---|---|---|---|---|
| Navigation | Sidebar + 11-screen `QStackedWidget` | Single scrolling page | Single scrolling page | Single scrolling page |
| Configuration | Multi-file legacy YAMLs | Single `config.yaml` | Single `config.yaml` | **Dual-Layer**: User `config.yaml` + Admin `admin_config.yaml` |
| Duplicate Keys Syntax | Complex lists of lists | Key sets in config | Key sets in config | **Simplified user list** normalized internally to list of lists |
| Field Character Rules | Raw regex strings | Raw regex presets | Raw regex presets | **Rule names** mapped to built-in presets in code |
| Check Enablement | Interactive screen | `config.yaml` toggle | `config.yaml` toggle | **Admin controlled** (`checks.enabled`); explicit `[]` runs 0 checks |
| Config Hashing | None | SHA-256 of `config.yaml` | SHA-256 of `config.yaml` | **Deterministic SHA-256 of combined User + Admin config** |
| Rule Inference | None | Prototype observation | Autonomous + confirmation popup | Recalibrated 5-phase inference + confirmation popup |
| Scoring Model | Weighted dimensions | Issue-driven deductions | Reconciled issue-driven deductions | Reconciled issue-driven deductions (legacy scoring fields removed) |
| Quality Issues View | Flat issue list | Flat issue list | Flat issue list | **6-column table with Quality Dimension & dropdown filter** |
| Batch Execution | None | Headless CLI | Headless CLI with format prompt | Headless CLI with format prompt & manual `--profile` override |
| Persistence | None | SQLite (`scanner.db`) | Unified SQLite (`scanner.db`) | Unified SQLite (`scanner.db`), auto-initialized via `get_connection()` |
| Dead Code Status | Stale screens/helpers | Deprecated screens | Active codebase | **All dead files (`charts.py`), legacy loaders, and dead locals removed** |

---

## 5. Retained & Active Core Engine Modules

- **ARCH-011**: `core/ingestion/` — CSV/Excel loading, encoding detection, validation.
- **ARCH-012**: `core/profiling/` — dataset- and column-level profiling.
- **ARCH-013**: `core/inference/` — 5-phase profile-driven heuristic inference for mandatory fields and identity keys with small-dataset safeguards ($N < 30$), strict categorical/name/metric rejections, bounded composite search ($K=5$), and 8-field activation cap on wide datasets.
- **ARCH-014**: `core/checks/*` — all 8 quality-check modules (duplicates, nulls, mandatory fields, whitespace, special characters, patterns, dates, relationships) plus automatic relationship discovery (`relationship_discovery.py`). Canonical check function: `check_relationships()`.
- **ARCH-015**: `core/scoring/scorer.py` — deterministic issue-driven scoring engine ($Score = 100 - \sum \text{penalties}$) with exact counts, child relationship denominators, full float precision, and transparent `ScoreBreakdown`.
- **ARCH-016**: `core/recommendations/recommender.py` — severity-prioritized recommendation generation.
- **ARCH-017**: `core/models.py` — serializable dataclass contract, `QualityDimension` enum, and category-to-dimension mapping.
- **ARCH-018**: `reports/` — HTML, Excel, and JSON exporters with issue summaries.
- **ARCH-019**: `core/service.py` (`AnalysisService.run()`) — orchestrates ingestion → profiling → inference → rule resolution → checks → scoring → recommendations.
- **ARCH-020**: `samples/` — standardized sample datasets (`customers_clean_100pct.csv`, `customers_faulty.csv`, `orders_related_to_customers.csv`, `products_normal.csv`).

---

## 6. Application Architecture

```text
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│   Desktop GUI (main.py)         │   │ Headless Batch (batch_runner.py)│
│   (single-page PySide6 widget)  │   │     (CLI runner, no Qt)         │
└────────────────┬────────────────┘   └────────────────┬────────────────┘
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Application/Service Layer (core.service)                 │
├────────────────────────────────────────────────────────────────────────┤
│                     Core Data Quality Engine                           │
│   ├── Ingestion (core.ingestion)                                       │
│   ├── Profiling (core.profiling)                                       │
│   ├── Rule Inference (core.inference - 5-phase calibrated pipeline)    │
│   ├── Rule Resolution (explicit config priority, additive supplement)  │
│   ├── Quality Checks (core.checks - 8 canonical check modules)         │
│   ├── Relationship Discovery & Integrity (relationship_discovery)     │
│   ├── Issue-Driven Scoring (core.scoring - deterministic deductions)   │
│   └── Recommendations (core.recommendations - prioritized actions)    │
├────────────────────────────────────────────────────────────────────────┤
│                     Configuration Architecture                         │
│   ├── User Business Rules (config/config.yaml - datasets, fields, keys)│
│   └── Admin Parameters (config/admin_config.yaml - checks, thresholds) │
├────────────────────────────────────────────────────────────────────────┤
│               Persistence Layer (db/ - data/scanner.db)                │
│                   (Scan history, findings, star schema)                │
├────────────────────────────────────────────────────────────────────────┤
│               Report Exporters (reports/ - HTML, Excel, JSON)          │
└────────────────────────────────────────────────────────────────────────┘
```

**ARCH-030**: The Core Engine and Service Layer remain GUI-agnostic; both the GUI layer (`main.py`) and headless batch runner (`batch_runner.py`) invoke `AnalysisService.run()` with typed `AnalysisConfig` and process the returned `AnalysisResult`.

**ARCH-031**: Headless batch mode runs with zero Qt/GUI initialization, deterministic exit codes (0/1/2/3), machine-readable JSON reports, interactive export format prompts, and non-blocking SQLite persistence.

---

## 7. Single-Page Application Structure

**ARCH-040**: The GUI is a single `QWidget`/`QScrollArea` composed of ordered sections (upload, dataset info, run controls, score gauge + borderless KPIs, 6 diagnostic dimension progress bars, filterable issues table with Quality Dimension column and dropdown filter, relationships, recommendations, report export, scan history, configuration info).

**ARCH-041**: Mandatory fields confirmation popup (`InferredMandatoryConfirmationDialog`) provides user control before activating newly inferred High-confidence mandatory fields, with fixed Proceed/Cancel buttons and a 220px scrollable field container.

**ARCH-042**: Long-running analysis executes off the main thread via a `QThread` worker (`gui/workers.py`), ensuring the GUI remains responsive.

---

## 8. Separation Between GUI and Core Processing

**ARCH-050**: The GUI layer contains no check logic, scoring logic, inference algorithms, or config-parsing logic. Its responsibilities are strictly presentation and invocation.

**ARCH-051**: Boundary enforcement: `core/`, `rules/`, `reports/`, `db/` never import from `gui/`.

---

## 9. Additive Rule Resolution & Configuration Precedence

**ARCH-060**: Explicit configuration is always retained and honored, with automatic inference supplementing it:
- **Mandatory Fields**: Configured mandatory fields are always preserved. The automatic analyzer inspects all other columns and adds any additional High-confidence inferred mandatory fields (subject to GUI user confirmation). Medium/Low/Uncertain fields are not automatically enforced.
- **Duplicate Keys**: Configured duplicate key sets are always preserved. High-confidence inferred identity keys on other columns are added as independent duplicate check rules (not merged into composite keys).
- **Rule Deduplication**: If an inferred rule matches an explicit configured rule (e.g. both identify `Email`), Rule Resolution merges them into a single logical rule, ensuring no double evaluation or penalty occurs.
- **Config-Free Fallback**: In the total absence of configuration, high-confidence inferred rules execute autonomously, with full-row duplicates serving as fallback if no high-confidence identity key is discovered.

---

## 10. Service / Application Layer Pipeline

**ARCH-070**: `core/service.py` executes the following sequence:
1. **Ingestion & Profiling**: Dataset and column-level statistical profiling.
2. **Rule Inference**: 5-phase multi-signal heuristic inference evaluates mandatory fields and identity keys.
3. **Rule Resolution**: Combines explicit config with high-confidence inferred rules (config takes priority). Prompts for confirmation when newly inferred mandatory fields are detected in GUI mode.
4. **Quality Checks**: Executes enabled checks using resolved active rules.
5. **Relationship Integrity**: Discovers relationships and validates foreign-key integrity.
6. **Issue-Driven Scoring**: Computes overall score and breakdown via deterministic severity deductions.
7. **Recommendations**: Generates prioritized remediation actions.

---

## 11. SQLite Persistence Layer

**ARCH-080**: All scan history is persisted to `data/scanner.db` (`DEFAULT_DB_PATH`) using a 6-table star schema.

**ARCH-081**: Raw dataset rows are never written to disk or database. Only metadata, check findings, diagnostic scores, relationship results, and recommendations are stored.

**ARCH-082**: Database connections auto-initialize schema on first access via `get_connection()`. Writes are non-blocking; persistence failures log a warning without disrupting analysis or report exports.

---

## 12. Report Generation

**ARCH-090**: HTML, Excel, and JSON report generators produce standardized assessment reports (`<dataset_name>_data_quality_report.<ext>`).

**ARCH-091**: Reports can be generated live from in-memory results or reconstructed from SQLite scan history without the original data files.

**ARCH-092**: Batch mode prompts the user interactively after analysis for their desired export formats (1: Excel, 2: JSON, 3: HTML, 4: All formats), or accepts non-interactive CLI flags (`--html`, `--excel`, `--json`, `--no-reports`).

---

## 13. Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| GUI | PySide6 |
| Data Processing | pandas |
| Excel I/O | openpyxl |
| Configuration | PyYAML |
| HTML Reports | Jinja2 |
| Visualizations | Matplotlib (QtAgg) |
| Encoding Detection | charset-normalizer |
| Database | `sqlite3` (built-in) |
| Testing | pytest, pytest-qt (210 tests passing) |
| Containerization | Docker (Dockerfile, .dockerignore) |

---

## 14. V3 Foundation & Cleanup State

The current V3 foundation includes:
- **Cleaned Configuration Architecture**: Separation of User Business Rules (`config/config.yaml`) and Administrator Parameters (`config/admin_config.yaml`).
- **Normalized Duplicate Keys**: Simplified user-facing syntax normalized to internal `list[list[str]]`.
- **Built-in Character Rules**: User configuration maps column names to built-in presets without raw regular expressions.
- **Removed Obsolete Modules & APIs**: Deleted `gui/widgets/charts.py`, `load_rules()`, `load_mandatory_fields()`, `load_relationships()`, `build_analysis_config_from_rules()`, `init_db()`, `get_score_breakdown()`, and legacy scoring fields.
- **Dual-File Config Hashing**: `get_config_hash()` deterministically computes a combined SHA-256 hash across both user and admin config files.
- **Full Regression Safety**: 210/210 tests passing with 100% success rate.

---

## 15. Future V3 Capabilities (Roadmap — Not Implemented in this Milestone)

The following capabilities are planned for upcoming V3 milestones:

### 15.1 Automatic Dataset / Profile Selection
The future selector will automatically match uploaded datasets against configured dataset definitions (`datasets:`) using column names, duplicate keys, profiling stats, and inference signals, requesting user confirmation only when ambiguous. In the current baseline, manual/explicit profile selection remains active.

### 15.2 Date Rule Simplification
Date rules currently reside in `config/config.yaml` (`accepted_formats`, `column_hints`) and will be evaluated for further simplification during future V3 feature tasks.

### 15.3 Logical Dataset-Type Relationship Mapping
Configured relationships currently link dataset filenames and will be migrated to link logical dataset types (e.g. `Customer_Master` $\to$ `Orders`) alongside automatic dataset selection.

---

## 16. Non-Goals

- Not a cloud/SaaS web application; local-first desktop and CLI execution only.
- Not introducing external database engines (PostgreSQL, MySQL, MongoDB).
- Not introducing third-party AI/LLM API calls or cloud-based neural networks.
- Not storing raw record values in SQLite.
- Not implementing interactive graphical rule editors.

---

*End of PRD 1.*
