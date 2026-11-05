# Data Quality Scanner — User Guide

## Overview

The **Data Quality Scanner** automates Pre-Migration Analysis (PMA) on source datasets (CSV & Excel), detects quality anomalies, automatically inspects datasets to identify parent-child relationships, validates referential integrity across related datasets, calculates an explainable **Migration Readiness Score**, persists scan results in SQLite, and exports executive-ready assessment reports in HTML, Excel, and JSON formats.

### Core Capabilities
- **Dual-Layer Configuration**: User-facing business rules (`config/config.yaml`) are decoupled from technical engine parameters (`config/admin_config.yaml`).
- **Simplified Dataset Definitions**: Users define dataset rules (`mandatory_fields` and `duplicate_keys`) using clean, intuitive YAML lists.
- **Quality Dimension Filtering**: Issues are categorized into 6 standalone dimensions (**Completeness**, **Uniqueness**, **Validity**, **Consistency**, **Integrity**, **Cleanliness**) with interactive dropdown filtering.
- **Autonomous Rule Inference & Confirmation**: The scanner profiles datasets and infers candidate rules, prompting for user confirmation before activating new mandatory fields in Desktop GUI mode.
- **Deterministic Issue-Driven Readiness Scoring**: Calculated directly from detected quality issues based on severity deductions scaled by affected volume.

---

## 1. Quick Start

### Installation & Environment Setup
Ensure Python 3.11+ is installed. Create and activate a virtual environment, then install runtime dependencies:

```powershell
# Create virtual environment
python -m venv .venv

# Activate on Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Activate on Linux/macOS
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Launch Desktop GUI
```powershell
python main.py
```

### Launch Headless Batch Mode
```powershell
# Single dataset analysis (runs autonomously and prompts for export format)
python batch_runner.py samples\customers_clean_100pct.csv

# Multi-dataset analysis with custom output directory
python batch_runner.py samples\customers_clean_100pct.csv samples\orders_related_to_customers.csv --output reports\

# Specific profile override and non-interactive export
python batch_runner.py samples\customers_faulty.csv --profile Customer_Master --json
```

### Run Full Test Suite
```powershell
pytest tests/ -v
```

---

## 2. Desktop GUI Walkthrough (Single-Page Executive Dashboard)

The application features a single-page, vertically scrollable layout where all information is accessible on a continuous dashboard:

1. **Header & Active Configuration**: Fixed top bar displaying application branding and active configuration SHA-256 hash (reflecting both `config.yaml` and `admin_config.yaml`).
2. **📂 Dataset Upload**: Drag & drop or browse for CSV/Excel datasets. Select sheets for multi-sheet workbooks.
3. **📋 Dataset Information**: Compact summary of loaded datasets, row counts, and column counts.
4. **🚀 Run Analysis**: One-click analysis execution with a live progress bar and non-blocking background worker.
5. **🎯 Overall Readiness Result**: Prominent circular score gauge (0–100) calculated deterministically from all detected quality issues, and issue count KPI metrics (Critical, High, Medium, Low).
6. **📊 Quality Dimension Scores**: Six clean progress-bar metric rows (Completeness, Uniqueness, Validity, Consistency, Integrity, Cleanliness) providing independent diagnostic health scores (0–100).
7. **⚠️ Quality Issues & Dimension Filtering**:
   - Filterable 6-column table: `#`, `Severity`, `Category`, `Dataset`, `Affected Field(s)`, **`Quality Dimension`**, `Issue Description`.
   - **Dimension Filter Dropdown**: Quickly isolate issues by Quality Dimension (`All Dimensions`, `Completeness`, `Uniqueness`, `Validity`, `Consistency`, `Integrity`, `Cleanliness`, `Unclassified`).
   - **Search Box**: Interactive text search matching across all issue fields.
8. **🔗 Relationship Integrity & Detection**:
   - **Relationship Detection**: Clear `Relationship Detected: YES` or `Relationship Detected: NO` status showing parent and child dataset linkages.
   - **Integrity Status**: `Integrity Status: PASSED` (green) or `Integrity Status: FAILED` (red).
   - **Metrics**: Total child records, invalid reference count, and invalid reference rate (percentage).
   - **Problematic Records**: Itemized list of exact child row numbers and invalid key values referencing missing parents.
9. **💡 Actionable Recommendations**: Prioritized remediation steps ordered by severity (Critical blockers surfaced first).
10. **📄 Export Reports**: Generate and save interactive HTML, 7-sheet Excel (`.xlsx`), and structured JSON reports named `<dataset_name>_data_quality_report.<ext>`.
11. **🕒 Scan History**: Browse, load, or review previous scans persisted in SQLite. Loading a historical scan restores all findings directly to the dashboard.
12. **⚙️ Active Configuration**: Read-only display of the active configuration file path and checksum.

---

## 3. Autonomous Business-Rule Inference & Configuration

### 3.1 Autonomous Operation (Config-Free Mode)
The scanner works completely out of the box without requiring manual configuration:
- Profiles every column's completeness, uniqueness, data type, and value structure.
- Automatically infers likely **mandatory fields** (using multi-signal heuristics) and likely **record identity / duplicate keys** (with strict false-positive protections).
- Prompts with a confirmation popup before activating newly inferred mandatory fields in the GUI.

### 3.2 Additive Rule Resolution & Configuration Precedence
When `config/config.yaml` is provided, explicit business rules take absolute precedence:
- **Mandatory Fields**: Configured mandatory fields are always preserved. Inferred High-confidence mandatory fields on other columns are added upon confirmation.
- **Duplicate Keys**: Configured duplicate key sets are always preserved. High-confidence inferred identity keys coexist as independent check rules.
- **Overlapping Rules**: If an inferred rule matches an explicit configured rule, it is evaluated once with no double penalties.

---

## 4. Headless Batch Mode & Automation

The application provides a fully headless execution mode (`batch_runner.py`) designed for CI/CD pipelines, scheduled jobs, batch scripts, and integration with external tools without any Qt windowing.

### 4.1 Interactive Export Selection Flow
When run without non-interactive export flags, the batch runner prompts the user upon scan completion:
```text
Select export format(s):

1. Excel
2. JSON
3. HTML
4. All formats

Enter the option(s) you would like for exporting: 
```

### 4.2 Command-Line Arguments
- `DATASET...` (Positional): One or more CSV or Excel (`.xlsx`/`.xls`) files to profile.
- `--config, -c`: Custom YAML configuration path (defaults to `config/config.yaml`).
- `--profile, -p`: Manual profile selection override (e.g. `--profile Customer_Master`).
- `--output, -o`: Output directory for generated reports (default: `reports`).
- `--db`: Custom SQLite database path (default: `data/scanner.db`).
- `--no-db`: Disable persisting scan findings to SQLite.
- `--html`, `--excel`, `--json`: Direct non-interactive flags to export specific formats.
- `--no-reports`: Skip report file export entirely.
- `--quiet, -q`: Suppress console progress, summary, and interactive prompts.

### 4.3 Process Exit Codes
- `0`: Scan completed successfully.
- `1`: Command-line syntax or argument error.
- `2`: File not found, unreadable file, unsupported format, or invalid configuration YAML.
- `3`: Unexpected application runtime exception.

---

## 5. Configuration Architecture Reference

### 5.1 User Business Configuration (`config/config.yaml`)
Contains dataset-level business definitions and validation expectations:
- `datasets:` Maps dataset names to `mandatory_fields` and `duplicate_keys`.
- `field_character_rules:` Maps columns to standard character validation presets (`alpha_numeric_only`, `email_format`, `numeric_only`, etc.).
- `date_rules:` Accepted date formats (`accepted_formats`) and date column detection hints (`column_hints`).
- `relationships:` Configured parent-child foreign-key relationships.

### 5.2 Administrator Technical Configuration (`config/admin_config.yaml`)
Contains system strictness and scoring calibration parameters:
- `checks.enabled:` Active quality checks (`duplicates`, `nulls`, `mandatory_fields`, `whitespace`, `special_chars`, `patterns`, `dates`, `relationships`).
- `scoring.severity_weights:` Penalty weights for Critical (15.0), High (8.0), Medium (3.0), and Low (1.0) issues.
- `scoring.readiness_thresholds:` Score thresholds for Ready (90), Minor Cleansing (75), and Needs Cleansing (50).
- `duplicate_rules.thresholds:` High (5.0%) and Medium (1.0%) duplicate rate thresholds.
- `null_rules:` High (20.0%) and Medium (5.0%) null percentage thresholds.
- `special_chars.anomaly_characters:` Global anomaly symbols (`$`, `@`, `#`, `%`, `&`, `*`).

---

*For detailed operational installation and environment setup, see `Deployment_Guide.md` and `Deployment_Guide.html`.*
