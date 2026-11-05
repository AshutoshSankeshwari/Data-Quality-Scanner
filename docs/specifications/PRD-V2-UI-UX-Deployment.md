# PRD 3 — V3 Single-Page UI, Reporting & Deployment (Foundation Baseline)

**Project:** Data Quality Scanner (V3 Foundation)
**Document Type:** Single-Page UI, UX, Reporting & Deployment PRD
**Version:** 3.0 Foundation (Cleaned V2.5 + V3 Configuration Baseline)
**Status:** Completed & Verified Implementation
**Companion Documents:** `PRD-V2-Architecture.md`, `PRD-V2-Data-Quality-Database.md`

---

## 1. Objective

Define the single-page GUI structure, Quality Issues table with Quality Dimension filtering, mandatory confirmation popup dialog, batch runner export prompt flow, reporting outputs, scan-history presentation, and Docker container packaging.

---

## 2. Scope

In scope: single-page dashboard layout and sections, 6-column Quality Issues table with Quality Dimension filtering, mandatory confirmation dialog with scrolling and cancellation flow, interactive batch export prompts, report contents, scan-history restoration, and Dockerfile/containerization specifications.

Out of scope: internal check logic (PRD 2), scoring algorithms (PRD 2), backend layering (PRD 1), future automatic profile selector UI (future V3 milestone).

---

## 3. Single-Page Desktop UI Specification

The application features a single-page, vertically scrolling executive dashboard built with PySide6 (`gui/main_window.py`).

### 3.1 Single-Page Dashboard Sections

In display order:

1. **Header Bar**: Displays application title ("Data Quality Scanner") and active configuration SHA-256 hash (reflecting both `config.yaml` and `admin_config.yaml`).
2. **📂 Dataset Upload**: File picker supporting CSV and Excel (`.xlsx`, `.xls`) with sheet-selection dropdown for multi-sheet workbooks.
3. **📋 Dataset Information**: Compact table showing loaded dataset names, file paths, row counts, and column counts.
4. **🚀 Run & Clear Controls**: Primary "Run Analysis" button and "Clear" action. Background execution via `QThread` ensures the UI remains responsive during scans.
5. **🎯 Overall Readiness Score & KPIs**:
   - Circular gauge displaying overall score ($0.0 - 100.0$) with color transitions (Green $\ge 90$, Yellow $75-89$, Orange $50-74$, Red $< 50$).
   - Prominent KPI count cards for Critical, High, Medium, and Low severity issue counts.
6. **📊 Diagnostic Quality Dimension Cards**: Six standalone cards for Completeness, Uniqueness, Validity, Consistency, Integrity, and Cleanliness showing health progress bars ($0.0\% - 100.0\%$) and descriptive explanations.
7. **⚠️ Quality Issues Table & Dimension Filtering**:
   - Filterable 6-column table: `#`, `Severity`, `Category`, `Dataset`, `Affected Field(s)`, **`Quality Dimension`**, `Issue Description`.
   - **Quality Dimension Dropdown Filter**: Dropdown allowing instant filtering by specific quality dimension (`All Dimensions`, `Completeness`, `Uniqueness`, `Validity`, `Consistency`, `Integrity`, `Cleanliness`, `Unclassified`).
   - **Search Box**: Interactive text search matching across Severity, Category, Dataset, Affected Fields, Quality Dimension, and Issue Description.
8. **🔗 Relationship Integrity Results**: Dedicated section displaying relationship detection status (`Relationship Detected: YES/NO`), parent/child linkages, integrity status (`PASSED/FAILED`), child record count, orphan count & percentage, and exact problematic child row numbers and invalid key values.
9. **💡 Remediation Recommendations**: Actionable recommendations sorted Critical-first with clear descriptions and affected datasets.
10. **📄 Export Reports**: Export buttons for HTML, Excel (`.xlsx`), and JSON formats.
11. **🕒 Scan History**: Table of previous scans persisted in SQLite (`data/scanner.db`). Selecting a scan restores all findings, scores, and relationship details to the dashboard and allows re-exporting reports.
12. **⚙️ Active Configuration Viewer**: Read-only display of the active configuration file path, checksum, and summary.

---

### 3.2 Inferred Mandatory Fields Confirmation Dialog (`InferredMandatoryConfirmationDialog`)

When the inference engine discovers newly inferred High-confidence mandatory fields that are not in explicit user configuration:
1. **Interactive Prompt**: The dialog displays candidate mandatory fields before they are activated.
2. **Fixed Height & Scrolling**: Field list is housed inside an isolated `QScrollArea` capped at 220px, ensuring the title, explanations, and action buttons remain visible on screen regardless of column count.
3. **Strict Cancellation Semantics**: Clicking "Cancel", the window close button (`X`), `Esc`, or `Alt+F4` raises `AnalysisCancelledError`, aborting the scan without calculating scores, producing partial results, or replacing existing dashboard data.

---

## 4. Reporting Specification

Reports are generated using the standard naming convention: `<dataset_name>_data_quality_report.<ext>`.

### 4.1 HTML Report (`reports/html_reporter.py`)
- Self-contained single-file interactive report (Jinja2 template).
- Executive summary, Overall Score gauge, KPI summary cards, 6 diagnostic dimension bars, full quality issues table, relationship integrity analysis with orphan records table, and prioritized recommendations.

### 4.2 Excel Report (`reports/excel_reporter.py`)
- Multi-tab workbook (`openpyxl`):
  1. `Summary`: Executive scorecard, overall readiness score, dimension health scores, and consolidated issues summary.
  2. `Duplicates`: Key-based and full-row duplicate records.
  3. `Nulls & Blanks`: Column-by-column missing value breakdown.
  4. `Field Formatting`: Special character, pattern, and date anomalies.
  5. `Relationships`: Referential integrity checks and orphan records.
  6. `Column Profiles`: Statistical profiling metrics per column.
  7. `Recommendations`: Prioritized remediation actions.

### 4.3 JSON Report (`reports/json_reporter.py`)
- Complete machine-readable JSON structure containing all findings, profiling stats, score breakdown, and metadata.

---

## 5. Headless Batch Runner & Interactive Export Flow

`batch_runner.py` provides a standalone CLI entrypoint for automation and CI/CD.

### 5.1 Interactive Export Prompt Flow
When executed without specific export flags, the batch runner prompts the user upon scan completion:
```text
Select export format(s):

1. Excel
2. JSON
3. HTML
4. All formats

Enter the option(s) you would like for exporting: 
```

### 5.2 Command-Line Arguments & Profile Selection
- `--config, -c`: Path to custom configuration file.
- `--profile, -p`: Manual profile selection override (e.g. `--profile Customer_Master`).
- `--output, -o`: Output directory for generated reports.
- `--db`: Custom SQLite database path.
- `--no-db`: Disable SQLite persistence.
- `--html`, `--excel`, `--json`: Direct non-interactive export flags.
- `--no-reports`: Suppress report generation entirely.
- `--quiet, -q`: Suppress console output and prompts.
- Exit codes: `0` (success), `1` (CLI syntax error), `2` (input/config error), `3` (runtime exception).

---

## 6. Docker Container Deployment

### 6.1 Container Specifications
- **Base Image**: `python:3.11-slim`
- **Dependencies**: Installed via `pip install -r requirements.txt`.
- **Exclusions**: `.dockerignore` excludes `.venv/`, `__pycache__/`, `.pytest_cache/`, `reports/`, and local test databases.

### 6.2 Volume Mount Points
- `/app/data`: Persistent storage for SQLite database (`scanner.db`).
- `/app/config`: External configuration overrides (`config.yaml`, `admin_config.yaml`).
- `/app/reports`: Output directory for generated reports.

---

*End of PRD 3.*
