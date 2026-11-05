<div align="center">

# 🔍 Data Quality Scanner

**Enterprise Pre-Migration Analysis (PMA), Relationship Integrity & Data Quality Assessment Engine**

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt-41CD52?style=flat-square&logo=qt&logoColor=white)](https://wiki.qt.io/Qt_for_Python)
[![Tests](https://img.shields.io/badge/Tests-271%20Passing-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![Database](https://img.shields.io/badge/Storage-SQLite%20WAL-003B57?style=flat-square&logo=sqlite&logoColor=white)](db/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](Dockerfile)
[![Reporting](https://img.shields.io/badge/Reports-HTML%20%7C%20Excel%20%7C%20JSON-orange?style=flat-square)](reports/)

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#key-features">Key Features</a> •
  <a href="#quality-dimensions">Quality Dimensions</a> •
  <a href="#system-architecture">Architecture</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#execution-modes">Execution Modes</a> •
  <a href="#headless-batch-cli-reference">CLI Reference</a> •
  <a href="#documentation--guides">Guides</a> •
  <a href="#project-structure">Project Structure</a>
</p>

</div>

---

## Overview

The **Data Quality Scanner** is an enterprise-ready analytical application designed specifically for **Pre-Migration Analysis (PMA)**. Before executing complex ETL pipelines, ERP migrations, PLM transformations, or database consolidations, the scanner profiles source datasets, detects quality anomalies across core validation dimensions, automatically discovers parent-child relationships, verifies referential integrity, and computes a deterministic, explainable **Migration Readiness Score**.

The platform is designed with a strict single-source-of-truth analytical engine that operates identically across both an **interactive PySide6 desktop dashboard** and a **headless batch command-line runner** with zero GUI dependencies.

---

## Key Features

### 📥 Ingestion & Profiling
- **Multi-Format Ingestion**: Native support for Delimited Text (`.csv`, `.tsv`, `.txt` with automatic delimiter detection and UTF-8/Latin-1/CP1252 fallback) and Excel (`.xlsx`, `.xls` with multi-sheet detection and worksheet selection).
- **Deep Statistical Profiling**: Automatically computes dataset-wide and column-level metrics including record count, distinct count, null count, blank/whitespace rate, inferred data type, and shape masks.

### 🔍 Core Quality Validation Checks
- **Uniqueness & Duplication**: Detects full-row duplicate records and business-key duplicates across configured or inferred composite primary keys.
- **Completeness & Nulls**: Disaggregates nulls, empty strings, and whitespace-only values to surface hidden blanks and validates mandatory business attributes.
- **Hygiene & Character Formatting**: Scans for leading, trailing, and excessive internal whitespace; validates character presets (`alpha_numeric_only`, `numeric_only`, `email_format`); and scans datasets for illegal anomaly characters (`$`, `@`, `#`, `%`, `&`, `*`).
- **Consistency & Patterns**: Performs date format validation and consistency checks against accepted patterns (`YYYY-MM-DD`, etc.) and evaluates string naming consistency using shape masks (`AAA-999`).

### 🔗 Autonomous Relationship & Referential Integrity
- **Automatic Relationship Detection**: Profiles related datasets and automatically infers parent-child foreign key linkages without requiring manual schema mapping.
- **Referential Integrity Validation**: Validates child key references against the parent dataset, isolates orphan records, calculates invalid reference percentages, and pinpoints exact child row numbers and missing key values.

### 🧠 Autonomous Rule Inference Engine
- **Calibrated 5-Phase Heuristics**: Evaluates semantic role anchors, population completeness, structural cardinality, and operational penalties to automatically infer candidate mandatory fields and identity keys.
- **Safe Activation**: Includes small-sample safeguards, false-positive categorical rejection, and an interactive confirmation popup in GUI mode before activating inferred mandatory fields.

### 🎯 Explainable Migration Readiness Scoring
- **Deterministic Deductions**: Computes an explainable Readiness Score (0–100) directly from detected quality issues using calibrated penalty weights (Critical: -15.0, High: -8.0, Medium: -3.0, Low: -1.0) scaled by affected record volume. Clean datasets score an exact 100.0.
- **Readiness Tiers**: Automatically categorizes datasets into **Ready** (Score ≥ 90), **Minor Cleansing Required** (Score 75–89), or **Needs Cleansing** (Score < 75).
- **Prioritized Recommendations**: Surfaces actionable remediation steps ordered by severity (Critical blockers surfaced first).

### 📄 Executive Multi-Format Reporting & Persistence
- **Self-Contained HTML**: Standalone, interactive HTML report with score gauge, dimension meters, KPI summary cards, and filterable issue tables.
- **Multi-Tab Excel (`.xlsx`)**: Comprehensive workbook featuring an Executive Summary tab and dedicated worksheets for Dataset Metrics, Column Profiles, Quality Issues with AutoFilter, Relationships, Recommendations, and Run Metadata.
- **Structured JSON**: Machine-readable scan summaries and itemized quality issue findings.
- **Embedded SQLite Persistence**: Local star-schema database with Write-Ahead Logging (WAL) that stores historical scans, metrics, and findings without retaining raw data rows.

---

## Quality Dimensions

The engine organizes all diagnostic findings into **6 Standalone Quality Dimensions**:

| Dimension | Core Focus Area | Quality Checks Applied |
|:---|:---|:---|
| **Completeness** | Absence of missing, blank, or omitted data in critical fields | Null checks, empty string separation, whitespace-only values, mandatory fields |
| **Uniqueness** | Absence of duplicate entity records or repeated primary keys | Full-row duplicates, business-key duplicates, composite key checks |
| **Validity** | Conformance of field values to business rules and character domains | Field-character presets, special character anomaly scanning (`$`, `@`, etc.) |
| **Consistency** | Structural uniformity, format compliance, and mask alignment | Date format consistency (`YYYY-MM-DD`), string shape masks (`AAA-999`) |
| **Integrity** | Soundness of cross-dataset foreign keys and entity references | Parent-child relationship discovery, foreign key validation, orphan isolation |
| **Cleanliness** | General hygiene of text values and elimination of formatting noise | Leading whitespace, trailing whitespace, consecutive internal spaces |

---

## System Architecture

```text
┌──────────────────────────────────────────────┐     ┌──────────────────────────────────────────────┐
│        PySide6 Desktop Application           │     │          Headless Batch CLI                  │
│             (python main.py)                 │     │        (python batch_runner.py)              │
│  • Single-Page Scrollable Executive Dashboard│     │  • Headless, automation-friendly execution   │
│  • Circular Readiness Gauge & Dimension Bars │     │  • Zero GUI / Qt windowing dependencies      │
│  • Inferred Mandatory Fields Confirmation    │     │  • Deterministic process exit codes (0/1/2/3)│
└───────────────────────┬──────────────────────┘     └──────────────────────┬───────────────────────┘
                        │                                                   │
                        └─────────────────────────┬─────────────────────────┘
                                                  ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Application Service Layer                                         │
│                                     (core/service.py)                                             │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                      Core Analysis Engine                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────────┐  │
│  │    Ingestion     │  │    Profiling     │  │  Rule Inference  │  │   Relationship Discovery  │  │
│  │ CSV / Excel Auto │  │ Column & Dataset │  │  5-Phase Anchor  │  │ Parent-Child & Foreign Key│  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └───────────────────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────────┐  │
│  │  Quality Checks  │  │  Issue Scoring   │  │ Recommendations  │  │     Data Model Mapper     │  │
│  │ 6 Core Dimensions│  │Severity Deducting│  │ Prioritized Fixes│  │  Serializable Dataclasses │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └───────────────────────────┘  │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                   Dual-Layer Configuration (YAML)                                 │
│  • Business Rules (config/config.yaml)         • Admin Parameters (config/admin_config.yaml)      │
└───────────────────────┬───────────────────────────────────────────────────┬───────────────────────┘
                        │                                                   │
                        ▼                                                   ▼
┌──────────────────────────────────────────────┐     ┌──────────────────────────────────────────────┐
│               SQLite Storage                 │     │               Report Generators              │
│             (data/scanner.db)                │     │              (reports/ directory)            │
│  • 6-Table Normalized Star Schema            │     │  • Interactive Self-Contained HTML Report    │
│  • WAL Mode & Foreign Key Constraints        │     │  • Multi-Tab Excel Workbook (.xlsx)          │
│  • Historical Scans & Aggregated Findings    │     │  • Machine-Readable Structured JSON Export   │
└──────────────────────────────────────────────┘     └──────────────────────────────────────────────┘
```

---

## Quickstart

> [!TIP]
> **Detailed Documentation**: For step-by-step setup guides, environment troubleshooting, and end-user walkthroughs, please consult the [Deployment Guide](Guide/Deployment_Guide.md) and [User Guide](Guide/User_Guide.md) in the [`Guide/`](Guide/) folder.

### 1. Environment Setup

```powershell
# Clone the repository
git clone https://github.com/AshutoshSankeshwari/Data-Quality-Scanner.git
cd Data-Quality-Scanner

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install runtime dependencies
pip install -r requirements.txt
```

### 2. Launch Desktop GUI Mode

```bash
python main.py
```

### 3. Launch Headless Batch CLI Mode

```bash
# Analyze a single dataset with interactive export prompt
python batch_runner.py samples/customers_clean_100pct.csv

# Multi-dataset analysis with referential integrity validation and automated export
python batch_runner.py samples/customers_clean_100pct.csv samples/orders_related_to_customers.csv --html --excel --json --output reports/
```

### 4. Run Automated Test Suite

```bash
# Execute the comprehensive test suite (271 tests)
pytest tests/ -v
```

---

## Execution Modes

### Mode 1: Interactive Desktop GUI (`main.py`)
Provides a modern, single-page scrollable dashboard designed with PySide6:
1. **Header & Active Configuration**: Fixed top bar showing active configuration checksum.
2. **Dataset Upload**: Drag-and-drop or file browser for CSV and multi-sheet Excel files.
3. **Dataset Information**: Summary cards with record counts, column counts, and file metadata.
4. **Readiness Score Gauge**: Prominent circular score meter with issue counts by severity.
5. **Quality Dimension Meters**: 6 standalone health progress bars (Completeness, Uniqueness, Validity, Consistency, Integrity, Cleanliness).
6. **Quality Issues Table**: Filterable 6-column issue grid with search and dimension dropdown filter.
7. **Relationship Integrity Card**: Visual status indicator (`PASSED`/`FAILED`), orphan record counts, and problematic row indices.
8. **Actionable Recommendations**: Prioritized remediation steps ordered by severity.
9. **Report Exporters**: One-click generation for HTML, Excel, and JSON reports.
10. **Scan History**: Review and reload historical scans persisted in SQLite.

### Mode 2: Headless Batch CLI (`batch_runner.py`)
Designed for scheduled tasks, batch scripts, and automation pipelines without requiring any Qt / windowing dependencies:
- Zero UI initialization overhead.
- Interactive export prompt when run manually.
- Direct non-interactive flags (`--html`, `--excel`, `--json`, `--quiet`) for automated workflows.
- Deterministic process exit codes for script orchestration.

---

## Headless Batch CLI Reference

```text
usage: batch_runner.py [-h] [--config CONFIG] [--profile PROFILE]
                       [--output OUTPUT] [--db DB] [--no-db] [--sheet SHEET]
                       [--html] [--excel] [--json] [--no-reports] [--quiet]
                       [--version]
                       DATASET [DATASET ...]
```

### Command-Line Arguments

| Flag | Argument | Description | Default |
|:---|:---|:---|:---|
| `DATASET` | Positional | One or more CSV or Excel (`.xlsx`/`.xls`) file paths | *(Required)* |
| `--config`, `-c` | `PATH` | Custom path to user business rules configuration YAML | `config/config.yaml` |
| `--profile`, `-p` | `NAME` | Profile name in configuration to use for primary dataset | Auto-detect |
| `--output`, `-o` | `DIR` | Output directory for generated quality reports | `reports/` |
| `--db` | `PATH` | Custom SQLite database path for persisting scan records | `data/scanner.db` |
| `--no-db` | Flag | Disable persisting scan findings to SQLite | `False` |
| `--sheet` | `NAME` | Target worksheet name when loading Excel workbooks | First sheet |
| `--html` | Flag | Non-interactive export of interactive HTML report | Prompt |
| `--excel` | Flag | Non-interactive export of multi-tab Excel workbook | Prompt |
| `--json` | Flag | Non-interactive export of structured JSON summary | Prompt |
| `--no-reports` | Flag | Suppress all file report generation | `False` |
| `--quiet`, `-q` | Flag | Suppress console progress and summary outputs | `False` |
| `--version`, `-v` | Flag | Display application name and exit | — |

### Process Exit Codes

| Exit Code | Meaning | Operational Action |
|:---:|:---|:---|
| `0` | Analysis Completed Successfully | Scan completed and reports generated (regardless of data defects found). |
| `1` | Command-Line Argument Error | Check argument syntax, flags, or provided file paths. |
| `2` | Data Loading or Config Error | Input file unreadable, missing sheet, or malformed YAML configuration. |
| `3` | Application Runtime Exception | Unexpected runtime error encountered during processing. |

---

## Configuration Architecture

The application enforces a decoupled, dual-layer configuration governance model:

```text
config/
├── config.yaml          # Layer 1: User Business Rules
└── admin_config.yaml    # Layer 2: Administrator Technical Parameters
```

### 1. User Business Rules (`config/config.yaml`)
Business analysts and operators specify validation criteria using intuitive YAML syntax:
- `datasets:` Maps dataset profiles to required `mandatory_fields` and unique `duplicate_keys`.
- `field_character_rules:` Applies character validation presets (`alpha_numeric_only`, `numeric_only`, `email_format`) to specific columns without writing raw regex.
- `date_rules:` Configures accepted date patterns (`YYYY-MM-DD`, etc.) and column detection hints.
- `relationships:` Declares parent-child dataset foreign key relationships.

### 2. Administrator Parameters (`config/admin_config.yaml`)
Technical administrators calibrate engine strictness and scoring mechanics:
- `checks.enabled:` Master toggles for individual check modules.
- `scoring.severity_weights:` Penalty deduction weights (Critical: 15.0, High: 8.0, Medium: 3.0, Low: 1.0).
- `scoring.readiness_thresholds:` Score boundaries for Ready (90), Minor Cleansing (75), and Needs Cleansing (50).
- `special_chars.anomaly_characters:` Global anomaly symbols (`$`, `@`, `#`, `%`, `&`, `*`).

---

## Documentation & Guides

Comprehensive deployment and end-user documentation are provided in the [`Guide/`](Guide/) directory:

- **[Deployment Guide (Markdown)](Guide/Deployment_Guide.md)** • **[HTML Version](Guide/Deployment_Guide.html)**: Complete technical manual covering host requirements, virtual environment isolation, database initialization, container deployment, and verification procedures.
- **[User Guide (Markdown)](Guide/User_Guide.md)** • **[HTML Version](Guide/User_Guide.html)**: Practical user manual detailing the desktop dashboard sections, rule inference mechanics, CLI workflows, and report interpretations.

---

## Project Structure

```text
Data-Quality-Scanner/
├── Guide/                   # Deployment and User Guides (HTML and Markdown)
│   ├── Deployment_Guide.html
│   ├── Deployment_Guide.md
│   ├── User_Guide.html
│   └── User_Guide.md
├── config/                  # External configuration files
│   ├── config.yaml          # User business validation rules
│   └── admin_config.yaml    # Administrator technical thresholds & scoring weights
├── core/                    # Shared analytical engine
│   ├── ingestion/           # CSV and Excel loaders with auto-detection
│   ├── profiling/           # Dataset and column profiling
│   ├── inference/           # 5-phase heuristic business rule inference engine
│   ├── checks/              # Canonical quality checks across all 6 dimensions
│   ├── scoring/             # Deterministic issue-driven scoring engine
│   ├── recommendations/     # Rule-based remediation recommendation generator
│   ├── models.py            # Serializable dataclasses & QualityDimension enum
│   └── service.py           # AnalysisService facade orchestrator
├── data/                    # SQLite storage directory (auto-initializes scanner.db)
│   └── .gitkeep
├── db/                      # Database persistence layer
│   ├── schema.sql           # 6-table normalized star schema
│   ├── connection.py        # Connection manager with WAL mode auto-init
│   ├── repository.py        # ScanRepository data access object
│   └── serializer.py        # Bidirectional AnalysisResult <-> SQLite mapper
├── gui/                     # PySide6 desktop executive application
│   ├── sections/            # Dashboard section widgets (upload, score, issues, etc.)
│   ├── mandatory_confirmation_dialog.py # Inferred mandatory confirmation dialog
│   ├── style.py             # Enterprise color palette and stylesheet
│   ├── workers.py           # QThread non-blocking worker
│   └── main_window.py       # Single-page scrollable application window
├── reports/                 # Multi-format report exporters
│   ├── templates/           # Jinja2 HTML report templates
│   ├── html_reporter.py     # Interactive self-contained HTML report generator
│   ├── excel_reporter.py    # Multi-tab openpyxl Excel report generator
│   ├── json_reporter.py     # Structured JSON summary exporter
│   └── summary_builder.py   # Normalized issue counter and metric extractor
├── samples/                 # Standardized evaluation datasets
│   ├── customers_clean_100pct.csv
│   ├── customers_faulty.csv
│   ├── orders_related_to_customers.csv
│   ├── products_normal.csv
│   └── generate_samples.py
├── tests/                   # Complete automated pytest suite (271 tests)
├── Dockerfile               # Production container definition
├── .dockerignore            # Docker context exclusions
├── .gitignore               # Repository exclusion rules
├── requirements.txt         # Production runtime dependencies
├── requirements-dev.txt     # Development and testing dependencies
├── README.md                # Project README
├── batch_runner.py          # Headless batch CLI entry point
└── main.py                  # Desktop GUI entry point
```

---

## Containerization

The scanner includes production-ready Docker container support for automated pipeline integration:

```bash
# Build the Docker image
docker build -t data-quality-scanner .

# Execute analysis with persistent volume mounts for reports and database
docker run --rm \
  -v ${PWD}/data:/app/data \
  -v ${PWD}/reports:/app/reports \
  data-quality-scanner \
  samples/customers_clean_100pct.csv --excel --html --json --output reports/
```

---

## License

This project is licensed under the [MIT License](LICENSE).
