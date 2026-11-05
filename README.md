# Data Quality Scanner

A lightweight, enterprise-ready Python desktop application and data-quality engine designed for **Pre-Migration Analysis (PMA)**. It profiles source datasets, detects quality anomalies across core check dimensions, automatically checks whether relationships exist between datasets, validates parent-child referential integrity, computes an explainable **Migration Readiness Score**, persists scan history to a local SQLite database, and exports executive-ready assessment reports.

---

## Key Features

- **Multi-Format Ingestion**: Ingest CSV (auto-delimiter & encoding detection) and Excel (`.xlsx` with sheet selection).
- **Core Quality Checks**:
  - Full-row and business key duplicate detection (with automatic normalization of simple key lists)
  - Null, empty string, and whitespace-only separation
  - Mandatory field validation
  - Whitespace anomaly detection (leading/trailing/multiple internal)
  - Special character format validation and dataset-wide anomaly character scanning (`$`, `@`, `#`, `%`, `&`, `*`)
  - Pattern and naming consistency analysis (shape masks `AAA-999`)
  - Date validity & format consistency checks
  - Cross-dataset referential integrity & orphan detection
- **Dual-Layer Configuration Architecture**:
  - **User Business Rules (`config/config.yaml`)**: Simple dataset definitions (`mandatory_fields`, `duplicate_keys`), field-character rules using built-in presets without raw regex, accepted date formats, and referential relationships.
  - **Administrator Parameters (`config/admin_config.yaml`)**: Master check toggles (`checks.enabled`), scoring severity weights, readiness thresholds, detection limits, and anomaly characters.
- **Quality Dimensions & Filtering**:
  - Standalone diagnostic health metrics for 6 dimensions: **Completeness**, **Uniqueness**, **Validity**, **Consistency**, **Integrity**, and **Cleanliness**.
  - 6-column Quality Issues table with dedicated **Quality Dimension** column and dropdown filter.
- **Automatic Relationship Detection & Integrity Validation**: Automatically determines if parent-child relationships exist between uploaded datasets and executes referential integrity checks, identifying exact invalid/missing references, child row numbers, and invalid key values.
- **Autonomous Rule Inference & Resolution**: Calibrated 5-phase heuristic engine infers candidate mandatory fields and record identity keys automatically with small-sample safeguards, false-positive categorical/name rejection, bounded composite search, and wide-dataset activation caps. Confirms newly inferred mandatory fields via an interactive popup.
- **Deterministic Issue-Driven Readiness Scoring**: Score (0–100) calculated directly from detected quality issues based on severity deductions scaled by affected volume. Clean datasets score an exact 100.0 with transparent reconciliation breakdowns.
- **Actionable Recommendations**: Prioritized remediation actions surfaced Critical-first.
- **Dual Execution Modes**:
  - **Desktop GUI Mode**: Interactive single-page executive dashboard (`python main.py`).
  - **Headless Batch Mode**: Automation-friendly command-line runner (`python batch_runner.py`) with zero UI dependencies, deterministic exit codes (0/1/2/3), manual `--profile` selection override, and machine-readable JSON.
- **SQLite Persistence**: Automatic local star-schema database storing scan history, metadata, and aggregated findings without storing raw data rows.
- **Actionable Reporting**: Self-contained interactive HTML, multi-tab Excel (`.xlsx`) with issues surfaced directly in the Summary worksheet, and structured JSON exports for live and historical scans using standardized naming `<dataset_name>_data_quality_report.<ext>`.
- **Docker Support**: Standardized containerization (`Dockerfile`, `.dockerignore`) with volume persistence for `/app/data`, `/app/config`, and `/app/reports`.

---

## Project Status

Codebase Cleanup and Configuration Architecture is complete and verified:
- User business rules and admin parameters are cleanly decoupled.
- Obsolete legacy configuration loaders, dead chart modules, duplicate scoring functions, and unused helper functions have been removed.
- Dual-file configuration hashing is active.
- The entire automated test suite (**271 tests**) passes with a 100% success rate.

---

## Quickstart

> **Application Setup**: To set up the application environment and install dependencies, please follow the step-by-step instructions in the [Deployment Guide](Guide/Deployment_Guide.md) (or [HTML version](Guide/Deployment_Guide.html)) and [User Guide](Guide/User_Guide.md) located in the [`Guide/`](Guide/) folder.

```bash
# Setup Environment & Install Dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Run the Desktop GUI
```bash
python main.py
```

### 2. Run Headless Batch Mode
```bash
# Single dataset analysis (runs autonomously and prompts for export format)
python batch_runner.py samples/customers_clean_100pct.csv

# Multiple related datasets with default reports
python batch_runner.py samples/customers_clean_100pct.csv samples/orders_related_to_customers.csv

# Specific dataset profile override and custom output directory
python batch_runner.py --profile Customer_Master --output reports/ samples/customers_faulty.csv
```

### 3. Run the Test Suite
```bash
pytest tests/ -v
```

---

## Project Structure

```
Data-Quality-Scanner/
├── config/                  # External configuration files
│   ├── config.yaml          # User business rules (datasets, mandatory fields, duplicate keys)
│   └── admin_config.yaml    # Administrator technical parameters & scoring weights
├── core/                    # Shared analysis engine
│   ├── ingestion/           # CSV and Excel loaders
│   ├── profiling/           # Dataset and column profiling
│   ├── inference/           # 5-phase calibrated business rule & identity key inference engine
│   ├── checks/              # Canonical quality checks (duplicates, nulls, dates, relationships, etc.)
│   ├── scoring/             # Deterministic issue-driven scoring engine
│   ├── recommendations/     # Rule-based remediation recommendations
│   ├── models.py            # Serializable dataclasses & QualityDimension enum
│   └── service.py           # Central AnalysisService orchestrator
├── db/                      # SQLite persistence layer (built-in sqlite3)
│   ├── schema.sql           # 6-table star schema
│   ├── connection.py        # Connection manager with WAL mode and schema auto-init
│   ├── repository.py        # ScanRepository data access object
│   └── serializer.py        # Bidirectional AnalysisResult <-> SQLite mapper
├── gui/                     # PySide6 desktop GUI
│   ├── sections/            # Single-page dashboard section widgets
│   ├── mandatory_confirmation_dialog.py  # Inferred mandatory fields confirmation popup
│   ├── workers.py           # QThread non-blocking worker
│   ├── style.py             # Enterprise color palette and stylesheet
│   └── main_window.py       # Single-page scrollable application window
├── reports/                 # Exporters (HTML, Excel, JSON) & templates
│   ├── templates/           # Jinja2 HTML report template
│   ├── html_reporter.py     # HTML report generator
│   ├── excel_reporter.py    # Multi-tab openpyxl Excel reporter
│   ├── json_reporter.py     # Structured JSON exporter
│   └── summary_builder.py   # Normalized issue extractor and summary counter
├── samples/                 # Standardized sample datasets
│   ├── customers_clean_100pct.csv
│   ├── customers_faulty.csv
│   ├── orders_related_to_customers.csv
│   ├── products_normal.csv
│   └── generate_samples.py
├── tests/                   # Complete pytest suite (210 tests passing)
├── Guide/                   # Deployment guide & user guide (HTML and Markdown)
├── Dockerfile               # Production container definition
├── .dockerignore            # Docker context exclusions
├── .gitignore               # Repository exclusion rules
├── requirements.txt         # Runtime dependencies
├── requirements-dev.txt     # Development and test dependencies
├── README.md                # Project documentation
├── batch_runner.py          # Headless batch CLI entry point
└── main.py                  # Desktop GUI application entry point
```

---

## Headless Batch CLI Reference

`batch_runner.py` provides a standard-library `argparse` CLI interface without initializing any Qt / GUI dependencies:

```text
usage: batch_runner.py [-h] [--config CONFIG] [--profile PROFILE]
                       [--output OUTPUT] [--db DB] [--no-db] [--sheet SHEET]
                       [--html] [--excel] [--json] [--no-reports] [--quiet]
                       [--version]
                       DATASET [DATASET ...]
```

### Exit Codes:
- `0`: Execution completed successfully.
- `1`: Invalid command-line arguments.
- `2`: Dataset loading or configuration parsing error.
- `3`: Unexpected application runtime error.
