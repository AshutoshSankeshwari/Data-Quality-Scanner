# Data Quality Scanner — Deployment Guide

## 1. Purpose & Scope

This guide defines the standard operational setup, environment configuration, dependency installation, persistence management, verification, and execution procedures for deploying the **Data Quality Scanner** across supported workstation and server environments.

---

## 2. Prerequisites

### 2.1 Software Requirements
| Component | Minimum Version | Recommended Version | Verification Command |
|---|---|---|---|
| **Python** | 3.11.0 | 3.11.x or 3.12.x | `python --version` |
| **pip** | 23.0+ | Latest | `pip --version` |
| **Git** | 2.30+ | Latest | `git --version` |

### 2.2 Hardware Requirements
- **CPU**: Dual-core processor (Quad-core recommended for datasets > 100,000 rows).
- **RAM**: Minimum 4 GB (8 GB recommended).
- **Disk Space**: 500 MB free for dependencies, runtime SQLite database, and report exports.

### 2.3 Operating System Support
- **Windows**: Windows 10 / 11 / Server 2019+ (PowerShell 5.1+ or PowerShell 7+)
- **Linux**: Ubuntu 22.04+, RHEL 8+, Debian 11+
- **macOS**: macOS 12 (Monterey) or later

---

## 3. Deployment Package Directory Structure

```text
Data-Quality-Scanner/
├── Guide/                   # Deployment guide & user guide (HTML and Markdown)
│   ├── Deployment_Guide.html
│   ├── Deployment_Guide.md
│   ├── User_Guide.html
│   └── User_Guide.md
├── config/                  # Configuration files
│   ├── config.yaml          # User business validation rules
│   └── admin_config.yaml    # Admin thresholds and scoring weights
├── core/                    # Analysis engine (checks, profiling, scoring, service)
├── data/                    # Local SQLite persistence (auto-initialized scanner.db)
│   └── .gitkeep
├── db/                      # Schema definition and repository data access
├── gui/                     # PySide6 desktop executive dashboard
├── reports/                 # Exporters (HTML, Excel, JSON) & templates
│   └── templates/
├── samples/                 # Sample datasets for smoke testing
├── tests/                   # Automated pytest suite (271 tests)
├── Dockerfile               # Container definition
├── requirements.txt         # Production runtime dependencies
├── requirements-dev.txt     # Test and lint dependencies
├── batch_runner.py          # Headless batch CLI entry point
├── main.py                  # Desktop GUI entry point
└── README.md                # Project README
```

---

## 4. Step-by-Step Installation & Setup

### Step 1: Clone Repository
```bash
git clone https://github.com/AshutoshSankeshwari/Data-Quality-Scanner.git
cd Data-Quality-Scanner
```

### Step 2: Create & Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On Linux / macOS (Bash/Zsh):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Runtime Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

*For test execution and development tools, additionally run:*
```bash
pip install -r requirements-dev.txt
```

---

## 5. Persistence & Database Initialization

The Data Quality Scanner uses a local SQLite database (`data/scanner.db`) featuring a 6-table star schema with Write-Ahead Logging (WAL) and foreign key constraints enabled.

- **Auto-Initialization**: The database file is created automatically on the first execution of `main.py` or `batch_runner.py`.
- **Storage Policy**: Findings, metrics, and execution metadata are persisted without storing raw dataset rows.
- **Custom Location**: Specify an alternative database path using the `--db` flag in batch runner:
  ```bash
  python batch_runner.py samples/customers_clean_100pct.csv --db /path/to/custom_scanner.db
  ```
- **In-Memory / Ephemeral Runs**: Pass `--no-db` to prevent persisting scan records to disk.

---

## 6. Verification & Smoke Testing

Run the automated test suite to verify that all modules, checks, UI components, and reporting engines are operating correctly:

```bash
pytest tests/ -v
```

Expected result:
```text
======================= 271 passed in ~32s =======================
```

---

## 7. Operational Execution Modes

### Mode 1: Desktop GUI
Launch the interactive PySide6 dashboard:
```bash
python main.py
```

### Mode 2: Headless Batch CLI
Execute non-interactive or automated pipeline runs:
```bash
# Automated run with Excel, HTML, and JSON exports
python batch_runner.py samples/customers_clean_100pct.csv --excel --html --json --output reports/
```

### Mode 3: Docker Container
Build and run via Docker:
```bash
# Build Docker image
docker build -t data-quality-scanner:latest .

# Run batch container with volume mounts
docker run --rm \
  -v ${PWD}/data:/app/data \
  -v ${PWD}/reports:/app/reports \
  data-quality-scanner:latest \
  samples/customers_clean_100pct.csv --excel --json --output reports/
```

---

## 8. Rollback & Uninstallation

To remove or reset the deployment:
1. Deactivate the virtual environment:
   ```bash
   deactivate
   ```
2. Remove `.venv/` and runtime database `data/scanner.db`:
   ```powershell
   Remove-Item -Recurse -Force .venv, data/scanner.db
   ```
3. To reinstall cleanly, repeat Step 2 and Step 3 from Section 4.

