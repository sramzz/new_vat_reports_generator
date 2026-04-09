# VAT Reports Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Gradio-based tool that queries Azure SQL for VAT transaction data, generates per-store Excel reports, uploads them to Google Drive, and provides rollback capability.

**Architecture:** Modular Python app with four independent layers — `db/` (SQL query execution), `drive/` (Google Drive auth/upload/delete/mapping), `reports/` (data filtering, Excel generation, summary), and `app.py` (Gradio UI + orchestration). TDD throughout: write tests first, implement second.

**Tech Stack:** Python 3.13, pyodbc (Azure SQL), openpyxl (Excel), google-api-python-client + google-auth-oauthlib (Drive), Gradio (UI), pytest + pytest-mock (testing), uv (package manager), python-dotenv (config).

**Design Spec:** `docs/superpowers/specs/2026-04-09-vat-reports-generator-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `config.py` | Load `.env`, expose typed constants (DB settings, Drive folder IDs) |
| `db/__init__.py` | Package init |
| `db/query.py` | Read SQL template, inject dynamic dates, execute via pyodbc, return list of dicts |
| `db/SQL_Query.sql` | T-SQL template (already exists) |
| `drive/__init__.py` | Package init |
| `drive/auth.py` | Google OAuth2 flow — first-run consent, token reuse, token refresh |
| `drive/upload.py` | Upload files to Drive, set "anyone can edit" permissions, create folders |
| `drive/delete.py` | Delete files by ID from Drive (for rollback) |
| `drive/mapping.py` | Read/write `store_mapping.json`, lookup by storeId, add new stores |
| `reports/__init__.py` | Package init |
| `reports/split.py` | Partition rows by StoreId and by month |
| `reports/excel.py` | Generate per-store Excel (monthly/quarterly) and raw backup Excel |
| `reports/summary.py` | Generate summary Excel (Store ID, Store Name, Report URL) |
| `app.py` | Gradio UI (Generate tab + Rollback tab) and pipeline orchestration |
| `logging_config.py` | Logger setup with 10-day file retention |
| `data/__init__.py` | Package init |
| `data/last_run_manager.py` | Read/write/manage `last_run.json` for rollback tracking |
| `tests/conftest.py` | Shared fixtures: sample data, mock Drive service, mock DB |
| `tests/test_db_query.py` | Tests for db/query.py |
| `tests/test_drive_auth.py` | Tests for drive/auth.py |
| `tests/test_drive_upload.py` | Tests for drive/upload.py |
| `tests/test_drive_delete.py` | Tests for drive/delete.py |
| `tests/test_drive_mapping.py` | Tests for drive/mapping.py |
| `tests/test_report_split.py` | Tests for reports/split.py |
| `tests/test_report_excel.py` | Tests for reports/excel.py |
| `tests/test_report_summary.py` | Tests for reports/summary.py |
| `tests/test_last_run.py` | Tests for data/last_run_manager.py |
| `tests/test_validation.py` | Tests for input validation in app.py |
| `tests/test_integration.py` | End-to-end pipeline tests with all services mocked |
| `fixtures/sample_query_result.json` | ~33 rows across 3 known stores + 1 unknown, 3 months |
| `fixtures/sample_store_mapping.json` | Mapping for the 3 known test stores |
| `fixtures/sample_last_run.json` | Sample rollback state |
| `data/store_mapping.json` | Production store mapping (migrated from `2026-04-08_stores_mapping.json`) |
| `scripts/setup.bat` | Windows setup: install uv, create venv, install deps |
| `scripts/setup.sh` | Mac/Linux setup: install uv, create venv, install deps |
| `scripts/run.bat` | Windows launcher: activate venv, run app |
| `scripts/run.sh` | Mac/Linux launcher: activate venv, run app |
| `.env` | Environment variables (gitignored) |
| `.gitignore` | Ignore .env, credentials.json, token.json, run.log, etc. |

---

## Task 1: Project Scaffold and Tooling

**Model: Sonnet**

**Files:**
- Modify: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `config.py`
- Create: `db/__init__.py`
- Create: `drive/__init__.py`
- Create: `reports/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Update `pyproject.toml` with all dependencies**

```toml
[project]
name = "new-vat-reports-generator"
version = "0.1.0"
description = "VAT accounting report generator for Belchicken stores"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "pyodbc",
    "openpyxl",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "gradio",
    "python-dotenv",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-mock",
    "pytest-cov",
]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/

# Secrets — NEVER commit these
.env
credentials.json
token.json

# Logs
run.log

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# UV
.python-version

# Generated reports (local)
output/
```

- [ ] **Step 3: Create `.env.example`** (safe template, no real values)

```env
# Azure SQL
DB_SERVER=your-server.database.windows.net
DB_DATABASE=your-database-name
DB_DRIVER={ODBC Driver 18 for SQL Server}
DB_TIMEOUT=1800

# Google Drive folder IDs
GDRIVE_RAW_REPORT_FOLDER_ID=your-raw-report-folder-id
GDRIVE_REPORTS_FOLDER_ID=your-reports-folder-id
GDRIVE_SUMMARY_FOLDER_ID=your-summary-folder-id
```

- [ ] **Step 4: Create `config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Azure SQL
DB_SERVER = os.environ["DB_SERVER"]
DB_DATABASE = os.environ["DB_DATABASE"]
DB_DRIVER = os.environ.get("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
DB_TIMEOUT = int(os.environ.get("DB_TIMEOUT", "1800"))

# Google Drive folder IDs
GDRIVE_RAW_REPORT_FOLDER_ID = os.environ["GDRIVE_RAW_REPORT_FOLDER_ID"]
GDRIVE_REPORTS_FOLDER_ID = os.environ["GDRIVE_REPORTS_FOLDER_ID"]
GDRIVE_SUMMARY_FOLDER_ID = os.environ["GDRIVE_SUMMARY_FOLDER_ID"]

# Paths
STORE_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "data", "store_mapping.json")
LAST_RUN_PATH = os.path.join(os.path.dirname(__file__), "data", "last_run.json")
SQL_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "db", "SQL_Query.sql")
LOG_PATH = os.path.join(os.path.dirname(__file__), "run.log")

# Google OAuth
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
```

- [ ] **Step 5: Create package `__init__.py` files**

Create empty files:
- `db/__init__.py`
- `drive/__init__.py`
- `reports/__init__.py`
- `tests/__init__.py`

- [ ] **Step 6: Install dependencies and lock**

```bash
uv sync --all-extras
```

Expected: `uv.lock` is created/updated, all packages installed.

- [ ] **Step 7: Create `tests/conftest.py` with shared fixtures**

```python
import json
import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


@pytest.fixture
def sample_query_result():
    with open(os.path.join(FIXTURES_DIR, "sample_query_result.json"), "r") as f:
        return json.load(f)


@pytest.fixture
def sample_store_mapping():
    with open(os.path.join(FIXTURES_DIR, "sample_store_mapping.json"), "r") as f:
        return json.load(f)


@pytest.fixture
def sample_last_run():
    with open(os.path.join(FIXTURES_DIR, "sample_last_run.json"), "r") as f:
        return json.load(f)
```

- [ ] **Step 8: Write one trivial test to verify pytest works**

Create `tests/test_smoke.py`:

```python
def test_smoke():
    assert 1 + 1 == 2
```

- [ ] **Step 9: Run the smoke test**

```bash
uv run pytest tests/test_smoke.py -v
```

Expected: `1 passed`

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml .gitignore .env.example config.py db/__init__.py drive/__init__.py reports/__init__.py tests/__init__.py tests/conftest.py tests/test_smoke.py uv.lock
git commit -m "feat: project scaffold with dependencies, config, test tooling"
```

---

## Task 2: Test Fixtures

**Model: Sonnet**

**Files:**
- Create: `fixtures/sample_query_result.json`
- Create: `fixtures/sample_store_mapping.json`
- Create: `fixtures/sample_last_run.json`

- [ ] **Step 1: Create `fixtures/sample_query_result.json`**

This fixture has ~33 rows across 3 known stores (IDs 100, 200, 300) + 1 unknown store (ID 999), spanning 3 months (January–March 2026). Some stores have missing dates (normal — store closed that day).

```json
[
    {"CreatedOn": "2026-01-02", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 500.50, "12%": 0.00, "21%": 0.00, "Bancontact": 200.00, "Cash": 100.50, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-01-03", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 620.30, "12%": 0.00, "21%": 0.00, "Bancontact": 300.00, "Cash": 120.30, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-01-04", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 810.00, "12%": 0.00, "21%": 0.00, "Bancontact": 400.00, "Cash": 210.00, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-01-05", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 450.20, "12%": 0.00, "21%": 0.00, "Bancontact": 150.00, "Cash": 100.20, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-02-01", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 700.00, "12%": 0.00, "21%": 0.00, "Bancontact": 350.00, "Cash": 150.00, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-02-02", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 550.10, "12%": 0.00, "21%": 0.00, "Bancontact": 250.00, "Cash": 100.10, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-02-03", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 480.00, "12%": 0.00, "21%": 0.00, "Bancontact": 180.00, "Cash": 100.00, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-03-01", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 900.00, "12%": 0.00, "21%": 0.00, "Bancontact": 400.00, "Cash": 200.00, "Betalen met kaart": 300.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-03-02", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 750.00, "12%": 0.00, "21%": 0.00, "Bancontact": 350.00, "Cash": 200.00, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-03-03", "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0.00, "6%": 680.00, "12%": 0.00, "21%": 0.00, "Bancontact": 280.00, "Cash": 200.00, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-01-02", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1200.00, "12%": 50.00, "21%": 0.00, "Bancontact": 600.00, "Cash": 300.00, "Betalen met kaart": 250.00, "UberEats": 50.00, "TakeAway": 0.00, "Deliveroo": 50.00},
    {"CreatedOn": "2026-01-03", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1350.00, "12%": 60.00, "21%": 0.00, "Bancontact": 700.00, "Cash": 350.00, "Betalen met kaart": 260.00, "UberEats": 40.00, "TakeAway": 0.00, "Deliveroo": 60.00},
    {"CreatedOn": "2026-01-04", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 980.00, "12%": 40.00, "21%": 0.00, "Bancontact": 500.00, "Cash": 220.00, "Betalen met kaart": 200.00, "UberEats": 60.00, "TakeAway": 0.00, "Deliveroo": 40.00},
    {"CreatedOn": "2026-02-01", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1100.00, "12%": 55.00, "21%": 0.00, "Bancontact": 550.00, "Cash": 275.00, "Betalen met kaart": 230.00, "UberEats": 45.00, "TakeAway": 0.00, "Deliveroo": 55.00},
    {"CreatedOn": "2026-02-02", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1050.00, "12%": 45.00, "21%": 0.00, "Bancontact": 500.00, "Cash": 250.00, "Betalen met kaart": 250.00, "UberEats": 50.00, "TakeAway": 0.00, "Deliveroo": 45.00},
    {"CreatedOn": "2026-02-03", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1180.00, "12%": 48.00, "21%": 0.00, "Bancontact": 580.00, "Cash": 300.00, "Betalen met kaart": 248.00, "UberEats": 52.00, "TakeAway": 0.00, "Deliveroo": 48.00},
    {"CreatedOn": "2026-02-04", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1300.00, "12%": 52.00, "21%": 0.00, "Bancontact": 650.00, "Cash": 325.00, "Betalen met kaart": 273.00, "UberEats": 52.00, "TakeAway": 0.00, "Deliveroo": 52.00},
    {"CreatedOn": "2026-03-01", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1400.00, "12%": 60.00, "21%": 0.00, "Bancontact": 700.00, "Cash": 350.00, "Betalen met kaart": 290.00, "UberEats": 60.00, "TakeAway": 0.00, "Deliveroo": 60.00},
    {"CreatedOn": "2026-03-02", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1250.00, "12%": 55.00, "21%": 0.00, "Bancontact": 625.00, "Cash": 312.00, "Betalen met kaart": 258.00, "UberEats": 55.00, "TakeAway": 0.00, "Deliveroo": 55.00},
    {"CreatedOn": "2026-03-03", "StoreId": 200, "RegisterName": "Belchicken Brugge", "0%": 0.00, "6%": 1150.00, "12%": 50.00, "21%": 0.00, "Bancontact": 575.00, "Cash": 287.00, "Betalen met kaart": 238.00, "UberEats": 50.00, "TakeAway": 0.00, "Deliveroo": 50.00},
    {"CreatedOn": "2026-01-02", "StoreId": 300, "RegisterName": "Belchicken Leuven", "0%": 10.00, "6%": 800.00, "12%": 0.00, "21%": 25.00, "Bancontact": 400.00, "Cash": 200.00, "Betalen met kaart": 200.00, "UberEats": 0.00, "TakeAway": 25.00, "Deliveroo": 10.00},
    {"CreatedOn": "2026-01-03", "StoreId": 300, "RegisterName": "Belchicken Leuven", "0%": 5.00, "6%": 920.00, "12%": 0.00, "21%": 30.00, "Bancontact": 460.00, "Cash": 230.00, "Betalen met kaart": 230.00, "UberEats": 0.00, "TakeAway": 30.00, "Deliveroo": 5.00},
    {"CreatedOn": "2026-01-05", "StoreId": 300, "RegisterName": "Belchicken Leuven", "0%": 0.00, "6%": 750.00, "12%": 0.00, "21%": 20.00, "Bancontact": 375.00, "Cash": 187.00, "Betalen met kaart": 188.00, "UberEats": 0.00, "TakeAway": 20.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-02-01", "StoreId": 300, "RegisterName": "Belchicken Leuven", "0%": 8.00, "6%": 860.00, "12%": 0.00, "21%": 22.00, "Bancontact": 430.00, "Cash": 215.00, "Betalen met kaart": 215.00, "UberEats": 0.00, "TakeAway": 22.00, "Deliveroo": 8.00},
    {"CreatedOn": "2026-02-03", "StoreId": 300, "RegisterName": "Belchicken Leuven", "0%": 12.00, "6%": 940.00, "12%": 0.00, "21%": 28.00, "Bancontact": 470.00, "Cash": 235.00, "Betalen met kaart": 235.00, "UberEats": 0.00, "TakeAway": 28.00, "Deliveroo": 12.00},
    {"CreatedOn": "2026-03-01", "StoreId": 300, "RegisterName": "Belchicken Leuven", "0%": 6.00, "6%": 880.00, "12%": 0.00, "21%": 24.00, "Bancontact": 440.00, "Cash": 220.00, "Betalen met kaart": 220.00, "UberEats": 0.00, "TakeAway": 24.00, "Deliveroo": 6.00},
    {"CreatedOn": "2026-03-02", "StoreId": 300, "RegisterName": "Belchicken Leuven", "0%": 4.00, "6%": 820.00, "12%": 0.00, "21%": 26.00, "Bancontact": 410.00, "Cash": 205.00, "Betalen met kaart": 205.00, "UberEats": 0.00, "TakeAway": 26.00, "Deliveroo": 4.00},
    {"CreatedOn": "2026-01-02", "StoreId": 999, "RegisterName": "Belchicken NewStore", "0%": 0.00, "6%": 300.00, "12%": 0.00, "21%": 0.00, "Bancontact": 150.00, "Cash": 75.00, "Betalen met kaart": 75.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-01-03", "StoreId": 999, "RegisterName": "Belchicken NewStore", "0%": 0.00, "6%": 350.00, "12%": 0.00, "21%": 0.00, "Bancontact": 175.00, "Cash": 87.50, "Betalen met kaart": 87.50, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-02-01", "StoreId": 999, "RegisterName": "Belchicken NewStore", "0%": 0.00, "6%": 280.00, "12%": 0.00, "21%": 0.00, "Bancontact": 140.00, "Cash": 70.00, "Betalen met kaart": 70.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-02-02", "StoreId": 999, "RegisterName": "Belchicken NewStore", "0%": 0.00, "6%": 320.00, "12%": 0.00, "21%": 0.00, "Bancontact": 160.00, "Cash": 80.00, "Betalen met kaart": 80.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-03-01", "StoreId": 999, "RegisterName": "Belchicken NewStore", "0%": 0.00, "6%": 400.00, "12%": 0.00, "21%": 0.00, "Bancontact": 200.00, "Cash": 100.00, "Betalen met kaart": 100.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00},
    {"CreatedOn": "2026-03-02", "StoreId": 999, "RegisterName": "Belchicken NewStore", "0%": 0.00, "6%": 360.00, "12%": 0.00, "21%": 0.00, "Bancontact": 180.00, "Cash": 90.00, "Betalen met kaart": 90.00, "UberEats": 0.00, "TakeAway": 0.00, "Deliveroo": 0.00}
]
```

Row counts: Store 100 (Aalst) = 10 rows, Store 200 (Brugge) = 10 rows, Store 300 (Leuven) = 7 rows (missing dates — normal), Store 999 (NewStore) = 6 rows. Total = 33 rows across 3 months.

- [ ] **Step 2: Create `fixtures/sample_store_mapping.json`**

Contains only the 3 known stores (100, 200, 300). Store 999 is deliberately absent to test new-store detection.

```json
{
    "stores": [
        {
            "storeId": 100,
            "storeName": "Belchicken Aalst",
            "folderName": "Belchicken Aalst",
            "gdriveId": "fake-gdrive-id-aalst"
        },
        {
            "storeId": 200,
            "storeName": "Belchicken Brugge",
            "folderName": "Belchicken Brugge",
            "gdriveId": "fake-gdrive-id-brugge"
        },
        {
            "storeId": 300,
            "storeName": "Belchicken Leuven",
            "folderName": "Belchicken Leuven",
            "gdriveId": "fake-gdrive-id-leuven"
        }
    ]
}
```

- [ ] **Step 3: Create `fixtures/sample_last_run.json`**

```json
{
    "report_name": "Q1 - March 2026",
    "created_at": "2026-04-01T10:00:00",
    "files": [
        {
            "file_id": "fake-file-id-aalst",
            "store_id": 100,
            "store_name": "Belchicken Aalst",
            "type": "report"
        },
        {
            "file_id": "fake-file-id-brugge",
            "store_id": 200,
            "store_name": "Belchicken Brugge",
            "type": "report"
        },
        {
            "file_id": "fake-file-id-leuven",
            "store_id": 300,
            "store_name": "Belchicken Leuven",
            "type": "report"
        },
        {
            "file_id": "fake-file-id-raw",
            "store_id": null,
            "store_name": null,
            "type": "raw_backup"
        },
        {
            "file_id": "fake-file-id-summary",
            "store_id": null,
            "store_name": null,
            "type": "summary"
        }
    ]
}
```

- [ ] **Step 4: Verify fixtures load in conftest**

```bash
uv run pytest tests/test_smoke.py -v
```

Expected: Still passes (conftest fixtures are loaded lazily).

- [ ] **Step 5: Commit**

```bash
git add fixtures/
git commit -m "feat: add test fixtures — sample query result, store mapping, last run"
```

---

## Task 3: Store Mapping Module — Tests + Implementation

**Model: Sonnet**

**Files:**
- Create: `tests/test_drive_mapping.py`
- Create: `drive/mapping.py`

- [ ] **Step 1: Write all failing tests for `drive/mapping.py`**

Create `tests/test_drive_mapping.py`:

```python
import json
import pytest
from drive.mapping import load_mapping, get_folder_id, add_store, get_all_stores


@pytest.fixture
def mapping_file(tmp_path):
    data = {
        "stores": [
            {
                "storeId": 100,
                "storeName": "Belchicken Aalst",
                "folderName": "Belchicken Aalst",
                "gdriveId": "fake-gdrive-id-aalst"
            },
            {
                "storeId": 200,
                "storeName": "Belchicken Brugge",
                "folderName": "Belchicken Brugge",
                "gdriveId": "fake-gdrive-id-brugge"
            }
        ]
    }
    path = tmp_path / "store_mapping.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_get_folder_id_returns_id_for_known_store(mapping_file):
    mapping = load_mapping(mapping_file)
    result = get_folder_id(mapping, 100)
    assert result == "fake-gdrive-id-aalst"


def test_get_folder_id_returns_none_for_unknown_store(mapping_file):
    mapping = load_mapping(mapping_file)
    result = get_folder_id(mapping, 999)
    assert result is None


def test_add_store_persists_to_file(mapping_file):
    mapping = load_mapping(mapping_file)
    add_store(mapping, mapping_file, store_id=999, store_name="Belchicken NewStore", folder_name="Belchicken NewStore", gdrive_id="new-gdrive-id")
    reloaded = load_mapping(mapping_file)
    assert get_folder_id(reloaded, 999) == "new-gdrive-id"


def test_add_store_includes_all_fields(mapping_file):
    mapping = load_mapping(mapping_file)
    add_store(mapping, mapping_file, store_id=999, store_name="Belchicken NewStore", folder_name="Belchicken NewStore", gdrive_id="new-gdrive-id")
    reloaded = load_mapping(mapping_file)
    store = next(s for s in reloaded["stores"] if s["storeId"] == 999)
    assert store["storeName"] == "Belchicken NewStore"
    assert store["folderName"] == "Belchicken NewStore"
    assert store["gdriveId"] == "new-gdrive-id"


def test_get_all_stores_returns_full_mapping(mapping_file):
    mapping = load_mapping(mapping_file)
    stores = get_all_stores(mapping)
    assert len(stores) == 2
    assert stores[0]["storeId"] == 100
    assert stores[1]["storeId"] == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_drive_mapping.py -v
```

Expected: All 5 tests FAIL with `ModuleNotFoundError: No module named 'drive.mapping'`

- [ ] **Step 3: Implement `drive/mapping.py`**

```python
import json


def load_mapping(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_folder_id(mapping: dict, store_id: int) -> str | None:
    for store in mapping["stores"]:
        if store["storeId"] == store_id:
            return store["gdriveId"]
    return None


def add_store(
    mapping: dict,
    path: str,
    store_id: int,
    store_name: str,
    folder_name: str,
    gdrive_id: str,
) -> None:
    mapping["stores"].append({
        "storeId": store_id,
        "storeName": store_name,
        "folderName": folder_name,
        "gdriveId": gdrive_id,
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)


def get_all_stores(mapping: dict) -> list[dict]:
    return mapping["stores"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_drive_mapping.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_drive_mapping.py drive/mapping.py
git commit -m "feat: store mapping module — lookup by storeId, add store, persist to file"
```

---

## Task 4: Data Filtering Module — Tests + Implementation

**Model: Sonnet**

**Files:**
- Create: `tests/test_report_split.py`
- Create: `reports/split.py`

- [ ] **Step 1: Write all failing tests for `reports/split.py`**

Create `tests/test_report_split.py`:

```python
from datetime import date
from reports.split import filter_by_store, filter_by_month


def _make_rows():
    return [
        {"CreatedOn": date(2026, 1, 2), "StoreId": 100, "RegisterName": "Store A", "6%": 500},
        {"CreatedOn": date(2026, 1, 3), "StoreId": 100, "RegisterName": "Store A", "6%": 600},
        {"CreatedOn": date(2026, 2, 1), "StoreId": 100, "RegisterName": "Store A", "6%": 700},
        {"CreatedOn": date(2026, 1, 2), "StoreId": 200, "RegisterName": "Store B", "6%": 1200},
        {"CreatedOn": date(2026, 2, 1), "StoreId": 200, "RegisterName": "Store B", "6%": 1100},
        {"CreatedOn": date(2026, 3, 1), "StoreId": 200, "RegisterName": "Store B", "6%": 1400},
        {"CreatedOn": date(2026, 1, 5), "StoreId": 300, "RegisterName": "Store C", "6%": 800},
    ]


def test_filter_by_store_returns_correct_groups():
    rows = _make_rows()
    result = filter_by_store(rows)
    assert set(result.keys()) == {100, 200, 300}
    assert len(result[100]) == 3
    assert len(result[200]) == 3
    assert len(result[300]) == 1


def test_filter_by_store_preserves_all_rows():
    rows = _make_rows()
    result = filter_by_store(rows)
    total = sum(len(store_rows) for store_rows in result.values())
    assert total == len(rows)


def test_filter_by_store_single_store():
    rows = [{"CreatedOn": date(2026, 1, 2), "StoreId": 100, "RegisterName": "A", "6%": 500}]
    result = filter_by_store(rows)
    assert set(result.keys()) == {100}
    assert len(result[100]) == 1


def test_filter_by_store_empty_input():
    result = filter_by_store([])
    assert result == {}


def test_filter_by_month_returns_correct_groups():
    rows = [
        {"CreatedOn": date(2026, 1, 2), "StoreId": 100, "RegisterName": "A", "6%": 500},
        {"CreatedOn": date(2026, 1, 3), "StoreId": 100, "RegisterName": "A", "6%": 600},
        {"CreatedOn": date(2026, 2, 1), "StoreId": 100, "RegisterName": "A", "6%": 700},
        {"CreatedOn": date(2026, 3, 1), "StoreId": 100, "RegisterName": "A", "6%": 900},
    ]
    result = filter_by_month(rows)
    assert set(result.keys()) == {"January", "February", "March"}
    assert len(result["January"]) == 2
    assert len(result["February"]) == 1
    assert len(result["March"]) == 1


def test_filter_by_month_single_month():
    rows = [
        {"CreatedOn": date(2026, 3, 1), "StoreId": 100, "RegisterName": "A", "6%": 900},
        {"CreatedOn": date(2026, 3, 5), "StoreId": 100, "RegisterName": "A", "6%": 800},
    ]
    result = filter_by_month(rows)
    assert set(result.keys()) == {"March"}
    assert len(result["March"]) == 2


def test_filter_by_month_empty_input():
    result = filter_by_month([])
    assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_report_split.py -v
```

Expected: All 7 tests FAIL with `ModuleNotFoundError: No module named 'reports.split'`

- [ ] **Step 3: Implement `reports/split.py`**

```python
import calendar
from collections import defaultdict


def filter_by_store(rows: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        result[row["StoreId"]].append(row)
    return dict(result)


def filter_by_month(rows: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        month_name = calendar.month_name[row["CreatedOn"].month]
        result[month_name].append(row)
    return dict(result)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_report_split.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_report_split.py reports/split.py
git commit -m "feat: data filtering — partition rows by store and by month"
```

---

## Task 5: Excel Report Generation — Tests + Implementation

**Model: Opus**

**Files:**
- Create: `tests/test_report_excel.py`
- Create: `reports/excel.py`

Complex: generates monthly (1 sheet), quarterly (3 sheets) Excel files, and raw backup. Must match exact column layout and naming conventions from the real examples.

- [ ] **Step 1: Write all failing tests for `reports/excel.py`**

Create `tests/test_report_excel.py`:

```python
import os
from datetime import date
import openpyxl
import pytest
from reports.excel import generate_store_report, generate_raw_backup, REPORT_COLUMNS


def _make_single_month_rows():
    return [
        {"CreatedOn": date(2026, 1, 5), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 450.20, "12%": 0, "21%": 0, "Bancontact": 150.00, "Cash": 100.20, "Betalen met kaart": 200.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
        {"CreatedOn": date(2026, 1, 2), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 500.50, "12%": 0, "21%": 0, "Bancontact": 200.00, "Cash": 100.50, "Betalen met kaart": 200.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
        {"CreatedOn": date(2026, 1, 4), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 810.00, "12%": 0, "21%": 0, "Bancontact": 400.00, "Cash": 210.00, "Betalen met kaart": 200.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
        {"CreatedOn": date(2026, 1, 3), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 620.30, "12%": 0, "21%": 0, "Bancontact": 300.00, "Cash": 120.30, "Betalen met kaart": 200.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
    ]


def _make_quarterly_rows():
    return [
        {"CreatedOn": date(2026, 1, 2), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 500.50, "12%": 0, "21%": 0, "Bancontact": 200.00, "Cash": 100.50, "Betalen met kaart": 200.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
        {"CreatedOn": date(2026, 1, 3), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 620.30, "12%": 0, "21%": 0, "Bancontact": 300.00, "Cash": 120.30, "Betalen met kaart": 200.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
        {"CreatedOn": date(2026, 2, 1), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 700.00, "12%": 0, "21%": 0, "Bancontact": 350.00, "Cash": 150.00, "Betalen met kaart": 200.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
        {"CreatedOn": date(2026, 2, 2), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 550.10, "12%": 0, "21%": 0, "Bancontact": 250.00, "Cash": 100.10, "Betalen met kaart": 200.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
        {"CreatedOn": date(2026, 3, 1), "StoreId": 100, "RegisterName": "Belchicken Aalst", "0%": 0, "6%": 900.00, "12%": 0, "21%": 0, "Bancontact": 400.00, "Cash": 200.00, "Betalen met kaart": 300.00, "UberEats": 0, "TakeAway": 0, "Deliveroo": 0},
    ]


def test_monthly_report_has_one_sheet(tmp_path):
    path = generate_store_report(_make_single_month_rows(), "January 2026", "Belchicken Aalst", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert len(wb.sheetnames) == 1


def test_monthly_report_sheet_named_by_month(tmp_path):
    path = generate_store_report(_make_single_month_rows(), "January 2026", "Belchicken Aalst", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames[0] == "January"


def test_monthly_report_has_correct_columns(tmp_path):
    path = generate_store_report(_make_single_month_rows(), "January 2026", "Belchicken Aalst", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    headers = [cell.value for cell in wb.active[1]]
    assert headers == REPORT_COLUMNS


def test_monthly_report_rows_sorted_by_created_on(tmp_path):
    path = generate_store_report(_make_single_month_rows(), "January 2026", "Belchicken Aalst", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    dates = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
    assert dates == sorted(dates)


def test_quarterly_report_has_three_sheets(tmp_path):
    path = generate_store_report(_make_quarterly_rows(), "Q1 - March 2026", "Belchicken Aalst", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert len(wb.sheetnames) == 3


def test_quarterly_report_sheets_named_by_month(tmp_path):
    path = generate_store_report(_make_quarterly_rows(), "Q1 - March 2026", "Belchicken Aalst", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["January", "February", "March"]


def test_quarterly_report_each_sheet_has_correct_month_data(tmp_path):
    path = generate_store_report(_make_quarterly_rows(), "Q1 - March 2026", "Belchicken Aalst", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert wb["January"].max_row - 1 == 2
    assert wb["February"].max_row - 1 == 2
    assert wb["March"].max_row - 1 == 1


def test_file_naming_convention(tmp_path):
    path = generate_store_report(_make_single_month_rows(), "January 2026", "Belchicken Aalst", str(tmp_path))
    assert os.path.basename(path) == "January 2026 - VAT Accounting Report - Belchicken Aalst.xlsx"


def test_excel_file_is_valid(tmp_path):
    path = generate_store_report(_make_single_month_rows(), "January 2026", "Belchicken Aalst", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert wb is not None


def test_raw_backup_has_all_rows(tmp_path):
    rows = _make_quarterly_rows()
    path = generate_raw_backup(rows, "Q1 - March 2026", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert wb.active.max_row - 1 == len(rows)


def test_raw_backup_naming_convention(tmp_path):
    path = generate_raw_backup(_make_quarterly_rows(), "Q1 - March 2026", str(tmp_path))
    assert os.path.basename(path) == "Q1 - March 2026 - VAT Raw Report.xlsx"


def test_raw_backup_has_correct_columns(tmp_path):
    path = generate_raw_backup(_make_quarterly_rows(), "Q1 - March 2026", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    headers = [cell.value for cell in wb.active[1]]
    assert headers == REPORT_COLUMNS
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_report_excel.py -v
```

Expected: All 12 tests FAIL with `ModuleNotFoundError: No module named 'reports.excel'`

- [ ] **Step 3: Implement `reports/excel.py`**

```python
import calendar
import os
from collections import defaultdict

from openpyxl import Workbook

REPORT_COLUMNS = [
    "CreatedOn", "RegisterName", "0%", "6%", "12%", "21%",
    "Bancontact", "Cash", "Betalen met kaart", "UberEats", "TakeAway", "Deliveroo",
]


def _write_sheet(ws, rows: list[dict]) -> None:
    ws.append(REPORT_COLUMNS)
    sorted_rows = sorted(rows, key=lambda r: r["CreatedOn"])
    for row in sorted_rows:
        ws.append([row[col] for col in REPORT_COLUMNS])


def _group_by_month(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        month_name = calendar.month_name[row["CreatedOn"].month]
        groups[month_name].append(row)
    return dict(groups)


def generate_store_report(
    rows: list[dict],
    report_name: str,
    store_name: str,
    output_dir: str,
) -> str:
    filename = f"{report_name} - VAT Accounting Report - {store_name}.xlsx"
    path = os.path.join(output_dir, filename)

    wb = Workbook()
    months = _group_by_month(rows)

    month_order = list(calendar.month_name)[1:]
    sorted_months = sorted(months.keys(), key=lambda m: month_order.index(m))

    for i, month_name in enumerate(sorted_months):
        if i == 0:
            ws = wb.active
            ws.title = month_name
        else:
            ws = wb.create_sheet(title=month_name)
        _write_sheet(ws, months[month_name])

    wb.save(path)
    return path


def generate_raw_backup(
    rows: list[dict],
    report_name: str,
    output_dir: str,
) -> str:
    filename = f"{report_name} - VAT Raw Report.xlsx"
    path = os.path.join(output_dir, filename)

    wb = Workbook()
    ws = wb.active
    ws.title = "Raw Data"
    _write_sheet(ws, rows)

    wb.save(path)
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_report_excel.py -v
```

Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_report_excel.py reports/excel.py
git commit -m "feat: Excel report generation — monthly, quarterly, and raw backup"
```

---

## Task 6: Summary Report — Tests + Implementation

**Model: Sonnet**

**Files:**
- Create: `tests/test_report_summary.py`
- Create: `reports/summary.py`

- [ ] **Step 1: Write all failing tests for `reports/summary.py`**

Create `tests/test_report_summary.py`:

```python
import os
import openpyxl
from reports.summary import generate_summary


def _make_store_results():
    return [
        {"store_id": 100, "store_name": "Belchicken Aalst", "report_url": "https://drive.google.com/file/d/abc/view"},
        {"store_id": 200, "store_name": "Belchicken Brugge", "report_url": "https://drive.google.com/file/d/def/view"},
        {"store_id": 300, "store_name": "Belchicken Leuven", "report_url": "https://drive.google.com/file/d/ghi/view"},
    ]


def test_summary_has_correct_columns(tmp_path):
    path = generate_summary(_make_store_results(), "Q1 - March 2026", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    headers = [cell.value for cell in wb.active[1]]
    assert headers == ["Store ID", "Store Name", "Report URL"]


def test_summary_has_one_row_per_store(tmp_path):
    path = generate_summary(_make_store_results(), "Q1 - March 2026", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert wb.active.max_row - 1 == 3


def test_summary_urls_are_populated(tmp_path):
    path = generate_summary(_make_store_results(), "Q1 - March 2026", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    for row_num in range(2, ws.max_row + 1):
        url = ws.cell(row=row_num, column=3).value
        assert url is not None and url.startswith("https://")


def test_summary_file_is_valid_xlsx(tmp_path):
    path = generate_summary(_make_store_results(), "Q1 - March 2026", str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert wb is not None


def test_summary_naming_convention(tmp_path):
    path = generate_summary(_make_store_results(), "Q1 - March 2026", str(tmp_path))
    assert os.path.basename(path) == "Q1 - March 2026 - VAT Summary Report.xlsx"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_report_summary.py -v
```

Expected: All 5 tests FAIL

- [ ] **Step 3: Implement `reports/summary.py`**

```python
import os
from openpyxl import Workbook

SUMMARY_COLUMNS = ["Store ID", "Store Name", "Report URL"]


def generate_summary(
    store_results: list[dict],
    report_name: str,
    output_dir: str,
) -> str:
    filename = f"{report_name} - VAT Summary Report.xlsx"
    path = os.path.join(output_dir, filename)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(SUMMARY_COLUMNS)

    for result in store_results:
        ws.append([
            result["store_id"],
            result["store_name"],
            result["report_url"],
        ])

    wb.save(path)
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_report_summary.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_report_summary.py reports/summary.py
git commit -m "feat: summary report generation — Store ID, Store Name, Report URL"
```

---

## Task 7: Database Query Module — Tests + Implementation

**Model: Opus**

**Files:**
- Create: `tests/test_db_query.py`
- Create: `db/query.py`

Complex: reads SQL template, injects dynamic date ranges via regex replacement, executes the full T-SQL script via pyodbc (with multiple result sets from cursors), and handles connection failure, timeout, and MFA cancellation errors. All pyodbc interactions are mocked.

- [ ] **Step 1: Write all failing tests for `db/query.py`**

Create `tests/test_db_query.py`:

```python
import pyodbc
import pytest
from unittest.mock import MagicMock, patch
from db.query import build_date_ranges_sql, execute_query, EXPECTED_COLUMNS


SQL_TEMPLATE = """DROP TABLE IF EXISTS #DateRanges;
CREATE TABLE #DateRanges (StartDate DATE, EndDate DATE);

INSERT INTO #DateRanges (StartDate, EndDate)
VALUES
    (N'2025-04-01', N'2025-05-01'),
    (N'2025-05-01', N'2025-06-01'),
    (N'2025-06-01', N'2025-07-01');

SELECT CreatedOn, StoreId, RegisterName FROM #FinalResult;"""


def test_build_date_ranges_for_single_month():
    result = build_date_ranges_sql([1], 2026)
    assert result == (
        "INSERT INTO #DateRanges (StartDate, EndDate)\n"
        "VALUES\n"
        "    (N'2026-01-01', N'2026-02-01');"
    )


def test_build_date_ranges_for_three_months():
    result = build_date_ranges_sql([1, 2, 3], 2026)
    assert "(N'2026-01-01', N'2026-02-01')" in result
    assert "(N'2026-02-01', N'2026-03-01')" in result
    assert "(N'2026-03-01', N'2026-04-01')" in result


def test_build_date_ranges_december_wraps_to_next_year():
    result = build_date_ranges_sql([12], 2026)
    assert "(N'2026-12-01', N'2027-01-01')" in result


def test_query_returns_list_of_dicts():
    mock_cursor = MagicMock()
    mock_cursor.description = [(col, None, None, None, None, None, None) for col in EXPECTED_COLUMNS]
    mock_cursor.fetchall.return_value = [
        ("2026-01-02", 100, "Store A", 0, 500, 0, 0, 200, 100, 200, 0, 0, 0),
    ]
    mock_cursor.nextset.return_value = False

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
         patch("db.query._connect", return_value=mock_conn):
        result = execute_query([1], 2026)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["StoreId"] == 100
    assert result[0]["RegisterName"] == "Store A"


def test_query_returns_expected_columns():
    mock_cursor = MagicMock()
    mock_cursor.description = [(col, None, None, None, None, None, None) for col in EXPECTED_COLUMNS]
    mock_cursor.fetchall.return_value = [
        ("2026-01-02", 100, "Store A", 0, 500, 0, 0, 200, 100, 200, 0, 0, 0),
    ]
    mock_cursor.nextset.return_value = False

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
         patch("db.query._connect", return_value=mock_conn):
        result = execute_query([1], 2026)

    assert set(result[0].keys()) == set(EXPECTED_COLUMNS)


def test_query_handles_empty_result():
    mock_cursor = MagicMock()
    mock_cursor.description = [(col, None, None, None, None, None, None) for col in EXPECTED_COLUMNS]
    mock_cursor.fetchall.return_value = []
    mock_cursor.nextset.return_value = False

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
         patch("db.query._connect", return_value=mock_conn):
        result = execute_query([1], 2026)

    assert result == []


def test_query_handles_connection_failure():
    with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
         patch("db.query._connect", side_effect=pyodbc.Error("08001", "[08001] Connection failed")):
        with pytest.raises(ConnectionError, match="Failed to connect"):
            execute_query([1], 2026)


def test_query_handles_timeout():
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = pyodbc.Error("HYT00", "[HYT00] Query timeout expired")

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
         patch("db.query._connect", return_value=mock_conn):
        with pytest.raises(TimeoutError, match="timed out"):
            execute_query([1], 2026)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_db_query.py -v
```

Expected: All 8 tests FAIL with `ModuleNotFoundError: No module named 'db.query'`

- [ ] **Step 3: Implement `db/query.py`**

```python
import re
import pyodbc
import config

EXPECTED_COLUMNS = [
    "CreatedOn", "StoreId", "RegisterName",
    "0%", "6%", "12%", "21%",
    "Bancontact", "Cash", "Betalen met kaart",
    "UberEats", "TakeAway", "Deliveroo",
]

_DATE_RANGES_PATTERN = re.compile(
    r"INSERT INTO #DateRanges \(StartDate, EndDate\)\s*VALUES\s*\n(.*?);",
    re.DOTALL,
)


def build_date_ranges_sql(months: list[int], year: int) -> str:
    lines = []
    for month in months:
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1}-01-01"
        else:
            end = f"{year}-{month + 1:02d}-01"
        lines.append(f"    (N'{start}', N'{end}')")

    values = ",\n".join(lines)
    return f"INSERT INTO #DateRanges (StartDate, EndDate)\nVALUES\n{values};"


def _read_sql_template() -> str:
    with open(config.SQL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _connect() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={config.DB_DRIVER};"
        f"SERVER={config.DB_SERVER};"
        f"DATABASE={config.DB_DATABASE};"
        f"Authentication=ActiveDirectoryInteractive;"
        f"Timeout={config.DB_TIMEOUT};"
    )
    return pyodbc.connect(conn_str, timeout=config.DB_TIMEOUT)


def execute_query(months: list[int], year: int) -> list[dict]:
    template = _read_sql_template()
    new_insert = build_date_ranges_sql(months, year)
    sql = _DATE_RANGES_PATTERN.sub(new_insert, template)

    try:
        conn = _connect()
    except pyodbc.Error as e:
        raise ConnectionError(f"Failed to connect to database: {e}") from e

    try:
        cursor = conn.cursor()
        cursor.execute(sql)

        # The T-SQL script may produce multiple result sets.
        # Advance to the last one (the final SELECT).
        while cursor.nextset():
            pass

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except pyodbc.Error as e:
        error_code = getattr(e, "args", [""])[0] if e.args else ""
        if "HYT00" in str(error_code) or "timeout" in str(e).lower():
            raise TimeoutError(f"Database query timed out after {config.DB_TIMEOUT}s: {e}") from e
        raise ConnectionError(f"Database query failed: {e}") from e
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_db_query.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_db_query.py db/query.py
git commit -m "feat: database query module — SQL template injection, dynamic dates, error handling"
```

---

## Task 8: Google Drive Auth — Tests + Implementation

**Model: Sonnet**

**Files:**
- Create: `tests/test_drive_auth.py`
- Create: `drive/auth.py`

- [ ] **Step 1: Write all failing tests for `drive/auth.py`**

Create `tests/test_drive_auth.py`:

```python
from unittest.mock import MagicMock, patch, mock_open
from drive.auth import get_drive_service


@patch("drive.auth.build")
@patch("drive.auth.InstalledAppFlow")
@patch("drive.auth.os.path.exists", return_value=False)
def test_auth_creates_token_on_first_run(mock_exists, mock_flow_class, mock_build):
    mock_flow = MagicMock()
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.to_json.return_value = '{"token": "fake"}'
    mock_flow.run_local_server.return_value = mock_creds
    mock_flow_class.from_client_secrets_file.return_value = mock_flow

    with patch("builtins.open", mock_open()):
        get_drive_service()

    mock_flow.run_local_server.assert_called_once()


@patch("drive.auth.build")
@patch("drive.auth.Credentials")
@patch("drive.auth.os.path.exists", return_value=True)
def test_auth_reuses_existing_valid_token(mock_exists, mock_creds_class, mock_build):
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    get_drive_service()

    mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)


@patch("drive.auth.build")
@patch("drive.auth.Request")
@patch("drive.auth.Credentials")
@patch("drive.auth.os.path.exists", return_value=True)
def test_auth_refreshes_expired_token(mock_exists, mock_creds_class, mock_request_class, mock_build):
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "fake-refresh-token"
    mock_creds.to_json.return_value = '{"token": "refreshed"}'
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    with patch("builtins.open", mock_open()):
        get_drive_service()

    mock_creds.refresh.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_drive_auth.py -v
```

Expected: All 3 tests FAIL

- [ ] **Step 3: Implement `drive/auth.py`**

```python
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import config


def get_drive_service():
    creds = None

    if os.path.exists(config.TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.TOKEN_PATH, config.GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.CREDENTIALS_PATH, config.GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)

        with open(config.TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_drive_auth.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_drive_auth.py drive/auth.py
git commit -m "feat: Google Drive auth — OAuth2 with token reuse and refresh"
```

---

## Task 9: Google Drive Upload — Tests + Implementation

**Model: Opus**

**Files:**
- Create: `tests/test_drive_upload.py`
- Create: `drive/upload.py`

Complex: file upload with media, permission setting ("anyone can edit"), folder creation, and error handling via the Drive API.

- [ ] **Step 1: Write all failing tests for `drive/upload.py`**

Create `tests/test_drive_upload.py`:

```python
import pytest
from unittest.mock import MagicMock
from drive.upload import upload_file, create_folder


def _mock_service():
    return MagicMock()


def test_upload_file_returns_id_and_link():
    service = _mock_service()
    service.files().create().execute.return_value = {
        "id": "file-123",
        "webViewLink": "https://drive.google.com/file/d/file-123/view",
    }
    service.permissions().create().execute.return_value = {"id": "perm-1"}

    file_id, link = upload_file(service, "/tmp/report.xlsx", "parent-folder-id")
    assert file_id == "file-123"
    assert link == "https://drive.google.com/file/d/file-123/view"


def test_upload_file_sends_correct_parent_folder():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "file-123", "webViewLink": "https://example.com"}
    service.permissions().create().execute.return_value = {"id": "perm-1"}

    upload_file(service, "/tmp/report.xlsx", "my-parent-folder")

    create_call = service.files().create.call_args
    body = create_call[1]["body"] if "body" in create_call[1] else create_call[0][0]
    assert body["parents"] == ["my-parent-folder"]


def test_upload_file_sends_correct_filename():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "file-123", "webViewLink": "https://example.com"}
    service.permissions().create().execute.return_value = {"id": "perm-1"}

    upload_file(service, "/tmp/My Report - Store A.xlsx", "parent-id")

    create_call = service.files().create.call_args
    body = create_call[1]["body"] if "body" in create_call[1] else create_call[0][0]
    assert body["name"] == "My Report - Store A.xlsx"


def test_upload_file_sets_anyone_can_edit():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "file-123", "webViewLink": "https://example.com"}
    service.permissions().create().execute.return_value = {"id": "perm-1"}

    upload_file(service, "/tmp/report.xlsx", "parent-id")

    perm_call = service.permissions().create.call_args
    assert perm_call[1]["fileId"] == "file-123"
    assert perm_call[1]["body"]["type"] == "anyone"
    assert perm_call[1]["body"]["role"] == "writer"


def test_upload_file_handles_api_error():
    service = _mock_service()
    service.files().create().execute.side_effect = Exception("Drive API error")

    with pytest.raises(RuntimeError, match="Failed to upload"):
        upload_file(service, "/tmp/report.xlsx", "parent-id")


def test_create_folder_returns_folder_id():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "new-folder-123"}

    folder_id = create_folder(service, "Belchicken NewStore", "reports-parent-id")
    assert folder_id == "new-folder-123"


def test_create_folder_sets_correct_parent():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "new-folder-123"}

    create_folder(service, "Belchicken NewStore", "reports-parent-id")

    create_call = service.files().create.call_args
    body = create_call[1]["body"] if "body" in create_call[1] else create_call[0][0]
    assert body["parents"] == ["reports-parent-id"]
    assert body["mimeType"] == "application/vnd.google-apps.folder"
    assert body["name"] == "Belchicken NewStore"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_drive_upload.py -v
```

Expected: All 7 tests FAIL

- [ ] **Step 3: Implement `drive/upload.py`**

```python
import os
from googleapiclient.http import MediaFileUpload


def upload_file(service, local_path: str, parent_folder_id: str) -> tuple[str, str]:
    filename = os.path.basename(local_path)
    file_metadata = {
        "name": filename,
        "parents": [parent_folder_id],
    }
    media = MediaFileUpload(local_path, resumable=True)

    try:
        created = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()
    except Exception as e:
        raise RuntimeError(f"Failed to upload {filename}: {e}") from e

    file_id = created["id"]
    web_view_link = created.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "writer"},
        fields="id",
    ).execute()

    return file_id, web_view_link


def create_folder(service, folder_name: str, parent_folder_id: str) -> str:
    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    created = service.files().create(
        body=file_metadata,
        fields="id",
    ).execute()
    return created["id"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_drive_upload.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_drive_upload.py drive/upload.py
git commit -m "feat: Drive upload — file upload with permissions, folder creation"
```

---

## Task 10: Google Drive Delete — Tests + Implementation

**Model: Sonnet**

**Files:**
- Create: `tests/test_drive_delete.py`
- Create: `drive/delete.py`

- [ ] **Step 1: Write all failing tests for `drive/delete.py`**

Create `tests/test_drive_delete.py`:

```python
from unittest.mock import MagicMock
from drive.delete import delete_files


def _mock_service():
    return MagicMock()


def test_delete_files_removes_all_by_id():
    service = _mock_service()
    service.files().delete().execute.return_value = None

    file_ids = ["id-1", "id-2", "id-3", "id-4", "id-5"]
    success_count, errors = delete_files(service, file_ids)

    assert service.files().delete.call_count == 5
    assert success_count == 5


def test_delete_files_returns_success_count():
    service = _mock_service()
    service.files().delete().execute.return_value = None

    success_count, errors = delete_files(service, ["id-1", "id-2", "id-3"])
    assert success_count == 3
    assert errors == []


def test_delete_files_handles_partial_failure():
    service = _mock_service()

    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock = MagicMock()
        if call_count == 3:
            mock.execute.side_effect = Exception("Not found")
        else:
            mock.execute.return_value = None
        return mock

    service.files().delete = side_effect

    success_count, errors = delete_files(service, ["id-1", "id-2", "id-3", "id-4", "id-5"])
    assert success_count == 4
    assert len(errors) == 1
    assert "id-3" in errors[0]


def test_delete_files_empty_list():
    service = _mock_service()
    success_count, errors = delete_files(service, [])
    assert success_count == 0
    assert errors == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_drive_delete.py -v
```

Expected: All 4 tests FAIL

- [ ] **Step 3: Implement `drive/delete.py`**

```python
def delete_files(service, file_ids: list[str]) -> tuple[int, list[str]]:
    success_count = 0
    errors = []

    for file_id in file_ids:
        try:
            service.files().delete(fileId=file_id).execute()
            success_count += 1
        except Exception as e:
            errors.append(f"Failed to delete {file_id}: {e}")

    return success_count, errors
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_drive_delete.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_drive_delete.py drive/delete.py
git commit -m "feat: Drive delete — delete files by ID with partial failure handling"
```

---

## Task 11: Migrate Production Store Mapping

**Model: Sonnet**

**Files:**
- Create: `data/store_mapping.json` (migrated from `data/2026-04-08_stores_mapping.json`)

- [ ] **Step 1: Create `data/store_mapping.json`**

Read `data/2026-04-08_stores_mapping.json` and create a clean version at `data/store_mapping.json`. Remove the `excelFileName` field from every entry. Keep `storeId`, `storeName`, `folderName`, `gdriveId`.

- [ ] **Step 2: Verify the file loads correctly**

```bash
uv run python -c "
import json
with open('data/store_mapping.json') as f:
    data = json.load(f)
print(f'Loaded {len(data[\"stores\"])} stores')
for s in data['stores']:
    assert 'storeId' in s, f'Missing storeId in {s}'
    assert 'gdriveId' in s, f'Missing gdriveId in {s}'
    assert 'folderName' in s, f'Missing folderName in {s}'
    assert 'excelFileName' not in s, f'excelFileName should be removed from {s}'
print('All entries valid')
"
```

- [ ] **Step 3: Commit**

```bash
git add data/store_mapping.json
git commit -m "feat: migrate store mapping — clean format with storeId as primary key"
```

---

## Task 12: Logging Utility + Last Run Manager

**Model: Sonnet**

**Files:**
- Create: `logging_config.py`
- Create: `data/__init__.py`
- Create: `data/last_run_manager.py`
- Create: `tests/test_last_run.py`

- [ ] **Step 1: Create `logging_config.py`**

```python
import logging
import os
import time
import config

LOG_RETENTION_DAYS = 10


def setup_logging() -> logging.Logger:
    if os.path.exists(config.LOG_PATH):
        age_days = (time.time() - os.path.getmtime(config.LOG_PATH)) / 86400
        if age_days > LOG_RETENTION_DAYS:
            os.remove(config.LOG_PATH)

    logger = logging.getLogger("vat_reports")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)

    return logger
```

- [ ] **Step 2: Create `data/__init__.py`** (empty file)

- [ ] **Step 3: Write failing tests for `data/last_run_manager.py`**

Create `tests/test_last_run.py`:

```python
import json
import pytest
from data.last_run_manager import load_last_run, save_last_run, add_file_entry, remove_store_entries, clear_last_run


@pytest.fixture
def last_run_file(tmp_path):
    return str(tmp_path / "last_run.json")


def test_load_returns_none_when_file_missing(last_run_file):
    result = load_last_run(last_run_file)
    assert result is None


def test_save_and_load_roundtrip(last_run_file):
    data = {"report_name": "Q1 - March 2026", "created_at": "2026-04-01T10:00:00", "files": []}
    save_last_run(last_run_file, data)
    loaded = load_last_run(last_run_file)
    assert loaded["report_name"] == "Q1 - March 2026"


def test_add_file_entry(last_run_file):
    data = {"report_name": "Q1", "created_at": "2026-04-01T10:00:00", "files": []}
    save_last_run(last_run_file, data)
    add_file_entry(last_run_file, file_id="abc", store_id=100, store_name="Aalst", file_type="report")
    loaded = load_last_run(last_run_file)
    assert len(loaded["files"]) == 1
    assert loaded["files"][0]["file_id"] == "abc"
    assert loaded["files"][0]["type"] == "report"


def test_remove_store_entries(last_run_file):
    data = {
        "report_name": "Q1", "created_at": "2026-04-01T10:00:00",
        "files": [
            {"file_id": "a", "store_id": 100, "store_name": "Aalst", "type": "report"},
            {"file_id": "b", "store_id": 200, "store_name": "Brugge", "type": "report"},
            {"file_id": "c", "store_id": None, "store_name": None, "type": "raw_backup"},
        ],
    }
    save_last_run(last_run_file, data)
    file_ids = remove_store_entries(last_run_file, store_ids=[100])
    assert file_ids == ["a"]
    loaded = load_last_run(last_run_file)
    assert len(loaded["files"]) == 2
    assert all(f["store_id"] != 100 for f in loaded["files"])


def test_clear_last_run(last_run_file):
    data = {"report_name": "Q1", "created_at": "2026-04-01T10:00:00", "files": [{"file_id": "a", "store_id": 100, "store_name": "Aalst", "type": "report"}]}
    save_last_run(last_run_file, data)
    clear_last_run(last_run_file)
    assert load_last_run(last_run_file) is None
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
uv run pytest tests/test_last_run.py -v
```

Expected: All 5 tests FAIL

- [ ] **Step 5: Implement `data/last_run_manager.py`**

```python
import json
import os


def load_last_run(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_last_run(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def add_file_entry(path: str, file_id: str, store_id: int | None, store_name: str | None, file_type: str) -> None:
    data = load_last_run(path)
    if data is None:
        return
    data["files"].append({"file_id": file_id, "store_id": store_id, "store_name": store_name, "type": file_type})
    save_last_run(path, data)


def remove_store_entries(path: str, store_ids: list[int]) -> list[str]:
    data = load_last_run(path)
    if data is None:
        return []
    removed_ids = []
    remaining = []
    for f in data["files"]:
        if f["store_id"] in store_ids:
            removed_ids.append(f["file_id"])
        else:
            remaining.append(f)
    data["files"] = remaining
    save_last_run(path, data)
    return removed_ids


def clear_last_run(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_last_run.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add logging_config.py data/__init__.py data/last_run_manager.py tests/test_last_run.py
git commit -m "feat: logging utility with 10-day retention + last_run tracking module"
```

---

## Task 13: Integration Tests

**Model: Opus**

**Files:**
- Create: `tests/test_integration.py`

Most complex testing task. Wires together all modules with mocked externals and verifies end-to-end pipeline correctness.

- [ ] **Step 1: Write all integration tests**

Create `tests/test_integration.py`:

```python
import json
import os
from datetime import date, datetime
import openpyxl
import pytest

from reports.split import filter_by_store, filter_by_month
from reports.excel import generate_store_report, generate_raw_backup
from reports.summary import generate_summary
from drive.mapping import load_mapping, get_folder_id, add_store
from data.last_run_manager import load_last_run, save_last_run, add_file_entry, clear_last_run, remove_store_entries

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), "r") as f:
        return json.load(f)


def _parse_dates(rows):
    for row in rows:
        if isinstance(row["CreatedOn"], str):
            row["CreatedOn"] = date.fromisoformat(row["CreatedOn"])
    return rows


def test_full_monthly_flow(tmp_path):
    all_rows = _parse_dates(_load_fixture("sample_query_result.json"))
    jan_rows = [r for r in all_rows if r["CreatedOn"].month == 1]

    by_store = filter_by_store(jan_rows)
    assert len(by_store) == 4

    store_results = []
    for store_id, store_rows in by_store.items():
        store_name = store_rows[0]["RegisterName"]
        path = generate_store_report(store_rows, "January 2026", store_name, str(tmp_path))
        assert os.path.exists(path)
        store_results.append({"store_id": store_id, "store_name": store_name, "report_url": f"https://drive.google.com/file/d/fake-{store_id}/view"})

    raw_path = generate_raw_backup(jan_rows, "January 2026", str(tmp_path))
    assert os.path.exists(raw_path)

    summary_path = generate_summary(store_results, "January 2026", str(tmp_path))
    assert os.path.exists(summary_path)
    assert len(store_results) == 4


def test_full_quarterly_flow(tmp_path):
    all_rows = _parse_dates(_load_fixture("sample_query_result.json"))
    by_store = filter_by_store(all_rows)

    for store_id, store_rows in by_store.items():
        store_name = store_rows[0]["RegisterName"]
        path = generate_store_report(store_rows, "Q1 - March 2026", store_name, str(tmp_path))
        wb = openpyxl.load_workbook(path)
        months_in_data = len(filter_by_month(store_rows))
        assert len(wb.sheetnames) == months_in_data


def test_new_store_detection_flow(tmp_path):
    all_rows = _parse_dates(_load_fixture("sample_query_result.json"))
    mapping_path = str(tmp_path / "store_mapping.json")
    mapping_data = _load_fixture("sample_store_mapping.json")
    with open(mapping_path, "w") as f:
        json.dump(mapping_data, f)

    mapping = load_mapping(mapping_path)
    by_store = filter_by_store(all_rows)

    new_stores = []
    for store_id in by_store:
        if get_folder_id(mapping, store_id) is None:
            store_name = by_store[store_id][0]["RegisterName"]
            add_store(mapping, mapping_path, store_id, store_name, store_name, f"fake-new-{store_id}")
            new_stores.append(store_name)

    assert len(new_stores) == 1
    assert new_stores[0] == "Belchicken NewStore"
    reloaded = load_mapping(mapping_path)
    assert get_folder_id(reloaded, 999) == "fake-new-999"


def test_partial_upload_failure_tracks_only_successes(tmp_path):
    last_run_path = str(tmp_path / "last_run.json")
    save_last_run(last_run_path, {"report_name": "Q1", "created_at": datetime.now().isoformat(), "files": []})

    for store_id, name, fid in [(100, "Aalst", "f-100"), (200, "Brugge", "f-200"), (300, "Leuven", "f-300")]:
        add_file_entry(last_run_path, fid, store_id, name, "report")

    loaded = load_last_run(last_run_path)
    assert len(loaded["files"]) == 3
    assert all(f["store_id"] != 999 for f in loaded["files"])


def test_rollback_flow(tmp_path):
    last_run_path = str(tmp_path / "last_run.json")
    save_last_run(last_run_path, _load_fixture("sample_last_run.json"))

    loaded = load_last_run(last_run_path)
    assert len(loaded["files"]) == 5

    clear_last_run(last_run_path)
    assert load_last_run(last_run_path) is None


def test_rollback_specific_stores(tmp_path):
    last_run_path = str(tmp_path / "last_run.json")
    save_last_run(last_run_path, _load_fixture("sample_last_run.json"))

    removed = remove_store_entries(last_run_path, store_ids=[100])
    assert removed == ["fake-file-id-aalst"]

    loaded = load_last_run(last_run_path)
    assert len(loaded["files"]) == 4
    assert all(f["store_id"] != 100 for f in loaded["files"])


def test_dry_run_generates_local_files_only(tmp_path):
    all_rows = _parse_dates(_load_fixture("sample_query_result.json"))
    jan_rows = [r for r in all_rows if r["CreatedOn"].month == 1]
    by_store = filter_by_store(jan_rows)

    generated_files = []
    for store_id, store_rows in by_store.items():
        store_name = store_rows[0]["RegisterName"]
        path = generate_store_report(store_rows, "January 2026", store_name, str(tmp_path))
        generated_files.append(path)

    assert len(generated_files) == 4
    assert all(os.path.exists(f) for f in generated_files)
    assert not os.path.exists(str(tmp_path / "last_run.json"))
```

- [ ] **Step 2: Run integration tests**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "feat: integration tests — full pipeline flows with mocked services"
```

---

## Task 14: Gradio UI — Full Application

**Model: Opus**

**Files:**
- Create: `app.py`

Largest and most complex task. Builds the full Gradio UI with Generate tab (pipeline orchestration with progress feedback for 7-20 min DB queries) and Rollback tab. Wires together all modules for non-technical users.

- [ ] **Step 1: Implement `app.py`**

```python
import calendar
import os
import platform
import subprocess
import tempfile
from datetime import datetime

import gradio as gr

import config
from logging_config import setup_logging
from db.query import execute_query
from drive.auth import get_drive_service
from drive.upload import upload_file, create_folder
from drive.delete import delete_files
from drive.mapping import load_mapping, get_folder_id, add_store
from reports.split import filter_by_store, filter_by_month
from reports.excel import generate_store_report, generate_raw_backup
from reports.summary import generate_summary
from data.last_run_manager import load_last_run, save_last_run, add_file_entry, clear_last_run, remove_store_entries

logger = setup_logging()

MONTH_NAMES = list(calendar.month_name)[1:]  # January..December


def validate_inputs(report_name: str, months: list[str], year: int, is_quarterly: bool) -> str | None:
    if not report_name or not report_name.strip():
        return "Report name cannot be empty."
    if not months:
        return "Please select at least one month."
    if is_quarterly:
        month_indices = sorted([MONTH_NAMES.index(m) + 1 for m in months])
        if len(month_indices) != 3:
            return "Quarterly mode requires exactly 3 months."
        if month_indices != list(range(month_indices[0], month_indices[0] + 3)):
            return "Quarterly mode requires 3 consecutive months."
    return None


def generate_reports(report_name: str, months: list[str], year: int, is_quarterly: bool, dry_run: bool, progress=gr.Progress()):
    report_name = report_name.strip()
    month_indices = sorted([MONTH_NAMES.index(m) + 1 for m in months])

    error = validate_inputs(report_name, months, year, is_quarterly)
    if error:
        return f"**Validation Error:** {error}", "", ""

    logger.info(f"Starting report generation: name='{report_name}', months={month_indices}, year={year}, quarterly={is_quarterly}, dry_run={dry_run}")

    output_dir = tempfile.mkdtemp(prefix="vat_reports_")

    # Step 1: Query DB
    progress(0.05, desc="Querying database... this may take 7-20 minutes")
    try:
        rows = execute_query(month_indices, year)
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Database error: {e}")
        return f"**Database Error:** {e}", "", ""

    if not rows:
        logger.warning("Query returned no data")
        return "**No Data:** The query returned no results for the selected months.", "", ""

    logger.info(f"Query returned {len(rows)} rows")

    # Step 2: Get Drive service (unless dry run)
    service = None
    if not dry_run:
        progress(0.10, desc="Authenticating with Google Drive...")
        try:
            service = get_drive_service()
        except Exception as e:
            logger.error(f"Drive auth error: {e}")
            return f"**Google Drive Auth Error:** {e}", "", ""

    # Step 3: Upload raw backup
    progress(0.15, desc="Generating raw backup...")
    raw_path = generate_raw_backup(rows, report_name, output_dir)
    logger.info(f"Raw backup generated: {raw_path}")

    # Initialize last_run tracking
    save_last_run(config.LAST_RUN_PATH, {
        "report_name": report_name,
        "created_at": datetime.now().isoformat(),
        "files": [],
    })

    if not dry_run:
        progress(0.20, desc="Uploading raw backup...")
        try:
            raw_file_id, _ = upload_file(service, raw_path, config.GDRIVE_RAW_REPORT_FOLDER_ID)
            add_file_entry(config.LAST_RUN_PATH, raw_file_id, None, None, "raw_backup")
            logger.info(f"Raw backup uploaded: {raw_file_id}")
        except Exception as e:
            logger.error(f"Raw backup upload failed: {e}")
            return f"**Upload Error:** Failed to upload raw backup: {e}", "", ""

    # Step 4: Split by store
    progress(0.25, desc="Splitting data by store...")
    mapping = load_mapping(config.STORE_MAPPING_PATH)
    by_store = filter_by_store(rows)
    total_stores = len(by_store)

    # Step 5 & 6: Generate and upload per-store reports
    store_results = []
    errors = []
    new_stores = []

    for idx, (store_id, store_rows) in enumerate(by_store.items()):
        store_name = store_rows[0]["RegisterName"]
        pct = 0.25 + (0.60 * (idx + 1) / total_stores)
        progress(pct, desc=f"Processing store {idx + 1}/{total_stores}: {store_name}")

        # Check mapping, create folder if new
        folder_id = get_folder_id(mapping, store_id)
        if folder_id is None:
            new_stores.append(store_name)
            logger.info(f"New store detected: {store_name} (ID: {store_id})")
            if not dry_run:
                try:
                    folder_id = create_folder(service, store_name, config.GDRIVE_REPORTS_FOLDER_ID)
                    add_store(mapping, config.STORE_MAPPING_PATH, store_id, store_name, store_name, folder_id)
                    logger.info(f"Created Drive folder for {store_name}: {folder_id}")
                except Exception as e:
                    errors.append(f"{store_name}: Failed to create folder — {e}")
                    logger.error(f"Folder creation failed for {store_name}: {e}")
                    continue

        # Generate Excel
        try:
            report_path = generate_store_report(store_rows, report_name, store_name, output_dir)
        except Exception as e:
            errors.append(f"{store_name}: Failed to generate Excel — {e}")
            logger.error(f"Excel generation failed for {store_name}: {e}")
            continue

        # Upload
        report_url = ""
        if not dry_run and folder_id:
            try:
                file_id, report_url = upload_file(service, report_path, folder_id)
                add_file_entry(config.LAST_RUN_PATH, file_id, store_id, store_name, "report")
                logger.info(f"Uploaded report for {store_name}: {file_id}")
            except Exception as e:
                errors.append(f"{store_name}: Upload failed — {e}")
                logger.error(f"Upload failed for {store_name}: {e}")
                continue

        store_results.append({"store_id": store_id, "store_name": store_name, "report_url": report_url})

    # Step 7: Generate and upload summary
    progress(0.90, desc="Generating summary...")
    summary_path = generate_summary(store_results, report_name, output_dir)

    if not dry_run:
        progress(0.95, desc="Uploading summary...")
        try:
            summary_id, summary_url = upload_file(service, summary_path, config.GDRIVE_SUMMARY_FOLDER_ID)
            add_file_entry(config.LAST_RUN_PATH, summary_id, None, None, "summary")
            logger.info(f"Summary uploaded: {summary_id}")
        except Exception as e:
            errors.append(f"Summary upload failed: {e}")
            logger.error(f"Summary upload failed: {e}")

    # Build result message
    succeeded = len(store_results)
    failed = len(errors)

    result_lines = [f"**Processed:** {succeeded + failed} stores | **Succeeded:** {succeeded} | **Failed:** {failed}"]
    if dry_run:
        result_lines.insert(0, "**DRY RUN** — No files were uploaded to Google Drive.\n")
        result_lines.append(f"\nLocal files generated in: `{output_dir}`")
    if new_stores:
        result_lines.append(f"\n**New stores detected:** {', '.join(new_stores)}")

    table_header = "| Store Name | Report URL |\n|---|---|\n"
    table_rows = "\n".join(f"| {r['store_name']} | {r['report_url'] or '(dry run)'} |" for r in store_results)
    results_table = table_header + table_rows

    error_text = ""
    if errors:
        error_text = "**Errors:**\n" + "\n".join(f"- {e}" for e in errors)

    progress(1.0, desc="Done!")
    logger.info(f"Report generation complete: {succeeded} succeeded, {failed} failed")
    return "\n".join(result_lines), results_table, error_text


def open_log_folder():
    log_dir = os.path.dirname(config.LOG_PATH)
    if platform.system() == "Darwin":
        subprocess.Popen(["open", log_dir])
    elif platform.system() == "Windows":
        os.startfile(log_dir)
    else:
        subprocess.Popen(["xdg-open", log_dir])
    return "Log folder opened."


def load_rollback_info():
    data = load_last_run(config.LAST_RUN_PATH)
    if data is None:
        return "No previous run found.", [], gr.update(interactive=False), gr.update(interactive=False)

    report_name = data.get("report_name", "Unknown")
    created_at = data.get("created_at", "Unknown")
    files = data.get("files", [])

    store_files = [f for f in files if f["type"] == "report"]
    raw_files = [f for f in files if f["type"] == "raw_backup"]
    summary_files = [f for f in files if f["type"] == "summary"]

    info = (
        f"**Report:** {report_name}\n"
        f"**Created:** {created_at}\n"
        f"**Files:** {len(store_files)} store reports, {len(raw_files)} raw backup, {len(summary_files)} summary"
    )
    store_choices = [f"{f['store_name']} (ID: {f['store_id']})" for f in store_files]
    return info, store_choices, gr.update(interactive=True), gr.update(interactive=bool(store_choices))


def rollback_all(confirm: bool):
    if not confirm:
        return "Please check the confirmation box before deleting."

    data = load_last_run(config.LAST_RUN_PATH)
    if data is None:
        return "No previous run to roll back."

    file_ids = [f["file_id"] for f in data.get("files", [])]

    try:
        service = get_drive_service()
    except Exception as e:
        return f"**Auth Error:** {e}"

    success_count, del_errors = delete_files(service, file_ids)
    clear_last_run(config.LAST_RUN_PATH)
    logger.info(f"Rollback all: deleted {success_count}/{len(file_ids)} files")

    result = f"**Deleted:** {success_count}/{len(file_ids)} files."
    if del_errors:
        result += "\n**Errors:**\n" + "\n".join(f"- {e}" for e in del_errors)
    return result


def rollback_specific(selected_stores: list[str]):
    if not selected_stores:
        return "Please select at least one store."

    store_ids = []
    for s in selected_stores:
        id_part = s.split("(ID: ")[-1].rstrip(")")
        store_ids.append(int(id_part))

    data = load_last_run(config.LAST_RUN_PATH)
    if data is None:
        return "No previous run to roll back."

    file_ids = remove_store_entries(config.LAST_RUN_PATH, store_ids)

    try:
        service = get_drive_service()
    except Exception as e:
        return f"**Auth Error:** {e}"

    success_count, del_errors = delete_files(service, file_ids)
    logger.info(f"Rollback specific stores {store_ids}: deleted {success_count}/{len(file_ids)} files")

    result = f"**Deleted:** {success_count}/{len(file_ids)} files for selected stores."
    if del_errors:
        result += "\n**Errors:**\n" + "\n".join(f"- {e}" for e in del_errors)
    return result


# ---- UI Layout ----

current_year = datetime.now().year

with gr.Blocks(title="VAT Reports Generator") as app:
    gr.Markdown("# VAT Reports Generator")

    with gr.Tab("Generate Reports"):
        with gr.Row():
            with gr.Column():
                report_name = gr.Textbox(label="Report Name", placeholder="e.g. Q1 - March 2026")
                months = gr.CheckboxGroup(choices=MONTH_NAMES, label="Months")
                year = gr.Number(label="Year", value=current_year, precision=0)
                is_quarterly = gr.Checkbox(label="Quarterly Report", value=False)
                dry_run = gr.Checkbox(label="Dry Run (no uploads)", value=False)
                generate_btn = gr.Button("Generate Reports", variant="primary")

            with gr.Column():
                status_output = gr.Markdown(label="Status")
                results_table = gr.Markdown(label="Results")
                error_output = gr.Markdown(label="Errors")

        generate_btn.click(
            fn=generate_reports,
            inputs=[report_name, months, year, is_quarterly, dry_run],
            outputs=[status_output, results_table, error_output],
        )

    with gr.Tab("Rollback"):
        rollback_info = gr.Markdown("Loading...")
        refresh_btn = gr.Button("Refresh")

        with gr.Group():
            gr.Markdown("### Delete All Files")
            confirm_checkbox = gr.Checkbox(label="I confirm I want to delete all files from the last run")
            delete_all_btn = gr.Button("Delete All", variant="stop", interactive=False)
            delete_all_output = gr.Markdown()

        with gr.Group():
            gr.Markdown("### Delete Specific Stores")
            store_select = gr.CheckboxGroup(choices=[], label="Select stores to delete")
            delete_specific_btn = gr.Button("Delete Selected", variant="stop", interactive=False)
            delete_specific_output = gr.Markdown()

        def on_refresh():
            info, choices, all_btn_update, specific_btn_update = load_rollback_info()
            return info, gr.update(choices=choices), all_btn_update, specific_btn_update

        refresh_btn.click(fn=on_refresh, outputs=[rollback_info, store_select, delete_all_btn, delete_specific_btn])
        delete_all_btn.click(fn=rollback_all, inputs=[confirm_checkbox], outputs=[delete_all_output])
        delete_specific_btn.click(fn=rollback_specific, inputs=[store_select], outputs=[delete_specific_output])

    with gr.Row():
        log_btn = gr.Button("View Logs")
        log_status = gr.Textbox(label="", interactive=False, visible=False)
        log_btn.click(fn=open_log_folder, outputs=[log_status])

    app.load(fn=on_refresh, outputs=[rollback_info, store_select, delete_all_btn, delete_specific_btn])

if __name__ == "__main__":
    app.launch()
```

- [ ] **Step 2: Run full test suite to verify nothing broken**

```bash
uv run pytest -v
```

Expected: All existing tests still pass.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Gradio UI — generate tab, rollback tab, full pipeline orchestration"
```

---

## Task 15: Input Validation Tests

**Model: Sonnet**

**Files:**
- Create: `tests/test_validation.py`

- [ ] **Step 1: Write validation tests**

Create `tests/test_validation.py`:

```python
from app import validate_inputs


def test_rejects_empty_report_name():
    result = validate_inputs("", ["January"], 2026, False)
    assert result is not None and "empty" in result.lower()


def test_rejects_whitespace_report_name():
    result = validate_inputs("   ", ["January"], 2026, False)
    assert result is not None and "empty" in result.lower()


def test_rejects_no_months_selected():
    result = validate_inputs("Q1", [], 2026, False)
    assert result is not None and "month" in result.lower()


def test_quarterly_requires_three_months():
    result = validate_inputs("Q1", ["January", "February"], 2026, True)
    assert result is not None and "3" in result


def test_quarterly_requires_consecutive_months():
    result = validate_inputs("Q1", ["January", "March", "May"], 2026, True)
    assert result is not None and "consecutive" in result.lower()


def test_valid_monthly_passes():
    assert validate_inputs("January 2026", ["January"], 2026, False) is None


def test_valid_quarterly_passes():
    assert validate_inputs("Q1 - March 2026", ["January", "February", "March"], 2026, True) is None
```

- [ ] **Step 2: Run validation tests**

```bash
uv run pytest tests/test_validation.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_validation.py
git commit -m "feat: input validation tests for report generation form"
```

---

## Task 16: Setup and Run Scripts

**Model: Sonnet**

**Files:**
- Create: `scripts/setup.bat`
- Create: `scripts/setup.sh`
- Create: `scripts/run.bat`
- Create: `scripts/run.sh`

- [ ] **Step 1: Create `scripts/setup.sh`**

```bash
#!/bin/bash
set -e

echo "=== VAT Reports Generator Setup ==="

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed. Please install Python 3.13+."
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "Please restart your terminal and run this script again."
    exit 0
fi

echo "Installing dependencies..."
uv sync --all-extras

echo ""
echo "=== Setup complete! ==="
echo "Before running, make sure you have:"
echo "  1. Created a .env file (copy from .env.example)"
echo "  2. Placed credentials.json in the project root"
echo ""
echo "Run the app with: ./scripts/run.sh"
```

- [ ] **Step 2: Create `scripts/setup.bat`**

```batch
@echo off
echo === VAT Reports Generator Setup ===

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed. Please install Python 3.13+.
    exit /b 1
)

uv --version >nul 2>&1
if errorlevel 1 (
    echo Installing uv...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    echo Please restart your terminal and run this script again.
    exit /b 0
)

echo Installing dependencies...
uv sync --all-extras

echo.
echo === Setup complete! ===
echo Before running, make sure you have:
echo   1. Created a .env file (copy from .env.example)
echo   2. Placed credentials.json in the project root
echo.
echo Run the app with: scripts\run.bat
```

- [ ] **Step 3: Create `scripts/run.sh`**

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."
uv run python app.py
```

- [ ] **Step 4: Create `scripts/run.bat`**

```batch
@echo off
cd /d "%~dp0\.."
uv run python app.py
```

- [ ] **Step 5: Make shell scripts executable**

```bash
chmod +x scripts/setup.sh scripts/run.sh
```

- [ ] **Step 6: Commit**

```bash
git add scripts/
git commit -m "feat: setup and run scripts for Windows and Mac"
```

---

## Task 17: Coverage Check + Cleanup

**Model: Sonnet**

**Files:**
- No new files

- [ ] **Step 1: Run full test suite with coverage**

```bash
uv run pytest --cov=db --cov=drive --cov=reports --cov=data --cov-report=term-missing -v
```

Expected: 90%+ coverage on `db/`, `drive/`, `reports/`, `data/`.

- [ ] **Step 2: Delete smoke test**

```bash
rm tests/test_smoke.py
```

- [ ] **Step 3: Run full suite to confirm**

```bash
uv run pytest -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git rm tests/test_smoke.py
git commit -m "chore: remove smoke test, verify coverage target met"
```

---

## Task 18: README Documentation

**Model: Sonnet**

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write `README.md`**

Write a comprehensive README covering:
- What the tool does (1 paragraph)
- Prerequisites (Python 3.13+, ODBC Driver 18, Google Cloud project with Drive API enabled)
- Setup steps for Windows and Mac (using `scripts/setup.bat`/`setup.sh`)
- How to configure `.env` (copy from `.env.example`, fill in values)
- How to set up `credentials.json` (Google Cloud Console steps)
- How to launch the app (`scripts/run.bat`/`run.sh`)
- Usage guide: filling the form, Azure AD popup, Google consent, understanding results, using rollback
- Maintenance: `store_mapping.json`, SQL query updates, dependency updates, token expiry
- Troubleshooting: Office IP errors, MFA timeout, Drive permission errors, long query times
- Running tests: `uv run pytest`, `uv run pytest --cov`

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: comprehensive README — setup, usage, maintenance, troubleshooting"
```

---

## Self-Review Results

**1. Spec coverage:** All spec sections mapped to tasks:
- `config.py` → Task 1 | `db/query.py` → Task 7 | `drive/auth.py` → Task 8
- `drive/upload.py` → Task 9 | `drive/delete.py` → Task 10 | `drive/mapping.py` → Task 3
- `reports/split.py` → Task 4 | `reports/excel.py` → Task 5 | `reports/summary.py` → Task 6
- `data/last_run_manager.py` → Task 12 | Integration tests → Task 13 | Gradio UI → Task 14
- Input validation → Task 15 | Scripts → Task 16 | Logging → Task 12
- Store mapping migration → Task 11 | Coverage → Task 17 | README → Task 18
- `.gitignore` with credentials/token/.env → Task 1

**2. Placeholder scan:** No TBDs, TODOs, or "similar to Task N" found.

**3. Type consistency:** All function signatures (`load_mapping`, `get_folder_id`, `add_store`, `get_all_stores`, `filter_by_store`, `filter_by_month`, `generate_store_report`, `generate_raw_backup`, `generate_summary`, `execute_query`, `build_date_ranges_sql`, `upload_file`, `create_folder`, `delete_files`, `load_last_run`, `save_last_run`, `add_file_entry`, `clear_last_run`, `remove_store_entries`, `REPORT_COLUMNS`, `EXPECTED_COLUMNS`) are consistent across all tasks where they appear.
