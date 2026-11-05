# Data Quality Scanner V2.5 — User Guide Documentation

This directory contains the official **User Guide** for Data Quality Scanner V2.5.

## Deliverables

1. **[Data_Quality_Scanner_V2.5_User_Guide.html](Data_Quality_Scanner_V2.5_User_Guide.html)** (Primary Guide)
   - Practical, user-oriented enterprise user manual.
   - Includes interactive sidebar navigation, clear step-by-step setup and GUI walkthrough, CLI command reference, comparison tables, and authentic application screenshots.
   - Optimized with `@media print` rules for printing and pagination.

2. **[Data_Quality_Scanner_V2.5_User_Guide.pdf](Data_Quality_Scanner_V2.5_User_Guide.pdf)** (Distribution PDF)
   - Professional PDF generated directly from the HTML guide via Microsoft Edge headless rendering engine (`--headless=new --print-to-pdf`).
   - Compact, high-readability layout targeting ~15–18 pages in standard print format.

3. **[images/](images/)**
   - High-resolution, authentic screenshots captured directly from the running Data Quality Scanner V2.5 application.

## Verification Summary

All instructions, GUI labels, CLI commands, configuration options, scoring principles, and report structures reflect the current V2.5 codebase:
- **GUI Walkthrough:** Complete setup sequence (Steps 1–5: navigate to project, create venv, activate venv, install requirements, launch) and operational walkthrough (Steps 6–13) using actual button labels (e.g., *➕ Add CSV File*, *➕ Add Excel Workbook*, *🚀 Run Data Quality Analysis*, *Proceed*, *📥 Generate & Save Reports*).
- **CLI Commands:** Verified against `batch_runner.py` argument parser, real flags (`--config`, `--profile`, `--output`, `--db`, `--no-db`, `--sheet`, `--html`, `--excel`, `--json`, `--no-reports`, `--quiet`, `--version`), and exit codes (`0`, `1`, `2`, `3`).
- **Readiness Scoring:** Verified against `core/scoring/scorer.py` (clean data = 100, severity weights, volume scaling, readiness categories).
- **8 Quality Checks:** Verified against `core/checks/`.
- **Excel Report Structure:** Verified against `reports/excel_reporter.py` (Sheet 4 Issue Details table columns & AutoFilter `A1:H{last_row}`).
