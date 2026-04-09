# VAT Reports Generator — Design Spec

## Overview

A Gradio-based tool that automates VAT accounting report generation for Belchicken stores in Belgium. It queries an Azure SQL database, generates per-store Excel reports, uploads them to Google Drive, and produces a summary with links.

**End users:** Non-technical accounting/finance staff who clone the repo and run setup scripts. The UI must be clear and forgiving.

## Architecture

```
┌─────────────────────────────────────┐
│            Gradio UI (app.py)       │
│  ┌──────────┐  ┌──────────────────┐ │
│  │ Generate  │  │  Rollback Tab    │ │
│  │   Tab     │  │                  │ │
│  └─────┬────┘  └───────┬──────────┘ │
└────────┼───────────────┼────────────┘
         │               │
         ▼               ▼
┌──────────────────────────────────────┐
│         Orchestrator (app.py)        │
└──┬──────┬──────────┬───────────┬─────┘
   │      │          │           │
   ▼      ▼          ▼           ▼
┌──────┐┌────────┐┌─────────┐┌────────┐
│db/   ││drive/  ││reports/ ││data/   │
│query ││auth    ││split    ││store_  │
│.py   ││upload  ││excel    ││mapping │
│      ││delete  ││summary  ││.json   │
│      ││mapping ││         ││last_run│
│      ││.py     ││         ││.json   │
└──────┘└────────┘└─────────┘└────────┘

+ config.py          — env vars, folder IDs, DB connection string
+ scripts/           — setup.bat, setup.sh, run.bat, run.sh
+ tests/             — unit + integration tests with pytest
+ fixtures/          — sample data for tests (JSON files)
```

### Project Structure

```
new_vat_reports_generator/
├── app.py
├── config.py
├── pyproject.toml
├── uv.lock
├── db/
│   ├── __init__.py
│   ├── query.py
│   └── SQL_Query.sql
├── drive/
│   ├── __init__.py
│   ├── auth.py
│   ├── upload.py
│   ├── delete.py
│   └── mapping.py
├── reports/
│   ├── __init__.py
│   ├── split.py
│   ├── excel.py
│   └── summary.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_db_query.py
│   ├── test_drive_auth.py
│   ├── test_drive_upload.py
│   ├── test_drive_delete.py
│   ├── test_drive_mapping.py
│   ├── test_report_split.py
│   ├── test_report_excel.py
│   ├── test_report_summary.py
│   └── test_integration.py
├── fixtures/
│   ├── sample_query_result.json
│   ├── sample_store_mapping.json
│   └── sample_last_run.json
├── data/
│   ├── store_mapping.json
│   └── last_run.json
├── scripts/
│   ├── setup.bat
│   ├── setup.sh
│   ├── run.bat
│   └── run.sh
├── .env
├── .gitignore
└── README.md
```

## Modules

### `db/query.py` — Database Layer

Executes the T-SQL query template (`db/SQL_Query.sql`) against Azure SQL via `pyodbc`.

**Authentication:** Azure AD Interactive — triggers a browser/MFA popup on each run. No credentials stored.

**Dynamic date injection:** The SQL template has a hardcoded `INSERT INTO #DateRanges VALUES(...)` block. Python replaces this with dynamically generated values based on user-selected months and year. For example, months [1, 2, 3] with year 2026 produces:

```sql
INSERT INTO #DateRanges (StartDate, EndDate)
VALUES
    (N'2026-01-01', N'2026-02-01'),
    (N'2026-02-01', N'2026-03-01'),
    (N'2026-03-01', N'2026-04-01');
```

The entire T-SQL script (with temp tables and cursors) is sent to the DB in one execution call.

**Timeout:** The query takes 7-20 minutes. Connection timeout is set to 1800 seconds (30 minutes) via `DB_TIMEOUT` in `.env`.

**Return value:** List of dicts, each with keys: `CreatedOn`, `StoreId`, `RegisterName` (store name), `0%`, `6%`, `12%`, `21%`, `Bancontact`, `Cash`, `Betalen met kaart`, `UberEats`, `TakeAway`, `Deliveroo`.

**Error handling:** Connection failure, timeout, and MFA cancellation return structured error messages (not raw exceptions).

### `drive/auth.py` — Google Drive Authentication

OAuth2 via `google-auth-oauthlib`. Uses `InstalledAppFlow.run_local_server()` for first-time consent (browser popup). Stores token in `token.json` at project root. Reuses token on subsequent runs; silently refreshes if expired.

**Scope:** `https://www.googleapis.com/auth/drive` (full Drive access for upload + permission management).

**Files:** `credentials.json` (OAuth client config, provided by user during setup) and `token.json` (auto-generated). Both files MUST be in `.gitignore` along with `.env` — these must never be committed.

### `drive/upload.py` — File Upload

Uploads files to Google Drive using the Drive API v3.

**Behavior:**
- `upload_file(service, local_path, parent_folder_id)` — uploads the file, returns `(file_id, web_view_link)`
- After upload, sets permissions to "anyone with link can edit"
- `create_folder(service, folder_name, parent_folder_id)` — creates a new folder under the given parent, returns `folder_id`

### `drive/delete.py` — File Deletion (Rollback)

Deletes files from Google Drive by file ID.

**Behavior:**
- `delete_files(service, file_ids)` — deletes all given file IDs. Continues on individual failures. Returns success count and list of errors.
- Only deletes files, never folders.

### `drive/mapping.py` — Store Mapping

Manages `data/store_mapping.json` — the mapping from `storeId` to Google Drive folder.

**Schema:**
```json
{
  "stores": [
    {
      "storeId": 262,
      "storeName": "Belchicken Wetteren",
      "folderName": "Belchicken Wetteren",
      "gdriveId": "19qH2-qQ0di2tcyWGDPP_GkzZa-LwSdJh"
    }
  ]
}
```

- `storeId` — primary key, integer from the database. Protects against store name changes.
- `storeName` — display name from the database. Updated if it changes.
- `folderName` — the Google Drive folder name. Can differ from `storeName` (e.g., "Belchicken Brugge Zuidzandstraat" has folder "Belchicken Brugge 2").
- `gdriveId` — Google Drive folder ID.

**Operations:**
- `get_folder_id(storeId)` — returns `gdriveId` or `None`
- `add_store(storeId, storeName, gdriveId)` — adds new entry, persists to file
- `get_all_stores()` — returns full mapping

### `reports/split.py` — Data Filtering

Partitions raw query results by store and month. The query already returns all rows tagged with `StoreId` and `CreatedOn` — this module just filters/partitions them, no aggregation.

- `filter_by_store(rows)` — partitions rows by `StoreId`, returns `dict[int, list[dict]]`
- `filter_by_month(rows)` — partitions a store's rows by month (derived from `CreatedOn`), returns `dict[str, list[dict]]` where key is month name (e.g., "January")
- Missing dates within a month are normal (store closed that day) — no padding needed.

### `reports/excel.py` — Excel Generation

Generates per-store Excel reports using `openpyxl`.

**Monthly report:** Single sheet named by month (e.g., "January"). Columns: `CreatedOn`, `RegisterName`, `0%`, `6%`, `12%`, `21%`, `Bancontact`, `Cash`, `Betalen met kaart`, `UberEats`, `TakeAway`, `Deliveroo`. Rows sorted by `CreatedOn` ascending.

**Quarterly report:** Three sheets, one per month, each named by month name (e.g., "January", "February", "March"). Same columns and sorting per sheet.

**Filename convention:** `"{report_name} - VAT Accounting Report - {store_name}.xlsx"` where `report_name` is user-provided (e.g., "Q1 - March 2026") and `store_name` comes from `RegisterName`.

**Raw backup:** `"{report_name} - VAT Raw Report.xlsx"` — single sheet with all rows from the query (all stores, all months, unsplit).

### `reports/summary.py` — Summary Report

Generates a summary Excel file with three columns:
- **Store ID** — integer
- **Store Name** — from `RegisterName`
- **Report URL** — Google Drive web view link

One row per store. Filename: `"{report_name} - VAT Summary Report.xlsx"`. Uploaded to the "Report Summary" folder on Google Drive.

## Google Drive Structure

```
Accounting VAT Reports/
├── Report Summary/       ← summary Excel goes here
├── Reports/
│   ├── Store A/          ← per-store folders (auto-created for new stores)
│   │   ├── Q1 - March 2026 - VAT Accounting Report - Store A.xlsx
│   │   └── January 2026 - VAT Accounting Report - Store A.xlsx
│   └── Store B/
│       └── ...
└── Raw Report/           ← raw backup Excel goes here
```

The three top-level folder IDs are configured in `.env` and do not change.

## Configuration

`.env` file:

```
# Azure SQL
DB_SERVER=<server address>
DB_DATABASE=<database name>
DB_DRIVER={ODBC Driver 18 for SQL Server}
DB_TIMEOUT=1800

# Google Drive folder IDs
GDRIVE_RAW_REPORT_FOLDER_ID=<id>
GDRIVE_REPORTS_FOLDER_ID=<id>
GDRIVE_SUMMARY_FOLDER_ID=<id>
```

**Azure SQL auth:** `ActiveDirectoryInteractive` — browser/MFA popup, no credentials in `.env`.

**Google Drive auth:** OAuth2 via `credentials.json` (project root) — browser consent popup on first run, then `token.json` reused/refreshed silently.

## Generate Reports — Full Pipeline

1. **User input:** Report name, selected months, year, monthly/quarterly toggle, dry run checkbox.
2. **Query DB:** Inject months/year into SQL template. Execute via `pyodbc`. UI shows "Querying database... this may take 7-20 minutes." Returns list of dicts.
3. **Upload raw backup:** Write all rows to `"{report_name} - VAT Raw Report.xlsx"`. Upload to "Raw Report" folder. Track file ID in `last_run.json`. *(Skipped in dry run.)*
4. **Split by store:** Group rows by `StoreId`. Look up each `StoreId` in `store_mapping.json`. If unknown: create new Drive folder under "Reports" using `RegisterName`, add to mapping.
5. **Generate per-store Excel:** Monthly (1 sheet) or quarterly (3 sheets). Filename: `"{report_name} - VAT Accounting Report - {store_name}.xlsx"`.
6. **Upload per-store files:** Upload each Excel to the store's Drive folder. Set "anyone can edit" permissions. Track file IDs in `last_run.json`. UI progress bar increments per store. *(Skipped in dry run.)*
7. **Generate & upload summary:** Excel with Store ID, Store Name, Report URL. Upload to "Report Summary" folder. Track in `last_run.json`. *(Skipped in dry run.)*
8. **Done:** UI shows results table, counts (processed/succeeded/failed), link to summary, new stores detected.

**Dry run:** Skips all Drive uploads (steps 3, 6, 7) but generates local Excel files so the user can verify output.

## Rollback

Tracked in `data/last_run.json` — stores file IDs of everything uploaded in the last run.

**`last_run.json` schema:**
```json
{
  "report_name": "Q1 - March 2026",
  "created_at": "2026-04-09T14:30:00",
  "files": [
    {
      "file_id": "1abc...",
      "store_id": 262,
      "store_name": "Belchicken Wetteren",
      "type": "report"
    },
    {
      "file_id": "1def...",
      "store_id": null,
      "store_name": null,
      "type": "raw_backup"
    },
    {
      "file_id": "1ghi...",
      "store_id": null,
      "store_name": null,
      "type": "summary"
    }
  ]
}
```

**Delete all:** Deletes every tracked file ID from Google Drive. Folders are left in place. `last_run.json` is cleared. Reports partial failures.

**Delete specific stores:** User selects stores from a list. Only those stores' report files are deleted. `last_run.json` is updated to remove only the deleted entries.

## Gradio UI

### Generate Tab
- Text field: report name prefix (e.g., "Q1 - March 2026")
- Multi-select checkboxes: months (January–December)
- Year selector: defaults to current year
- Toggle: "Monthly" vs "Quarterly"
- Checkbox: "Dry run"
- Button: "Generate Reports"
- Status text: current pipeline step (with note about 7-20 min DB query)
- Progress bar: per-store during upload phase
- Results table: Store Name + Report URL
- Counts: total/succeeded/failed
- Info: new stores detected
- Error section: red warning for failed uploads

### Rollback Tab
- Loads `last_run.json` on tab open, shows run metadata
- "Delete all" button with confirmation
- Multi-select for store-specific deletion
- Success/failure feedback

### Input Validation
- Report name cannot be empty
- At least one month must be selected
- Quarterly mode requires exactly 3 consecutive months

### Logging
- All actions logged to `run.log` (gitignored): timestamps, report name, months, row counts, per-store success/failure, new stores detected, rollback actions, errors.
- **Log retention:** On each run, if `run.log` is older than 10 days, it is deleted before the new run starts. No accumulation.
- UI has a "View Logs" button that opens the folder containing `run.log` in the system file explorer.

## Testing Strategy

**Framework:** `pytest` + `pytest-mock`. All external services (Azure SQL, Google Drive API) are mocked in tests.

### Unit Tests

| Test file | Scope |
|---|---|
| `test_db_query.py` | Column structure, date parameterization, return type, empty result, connection failure, timeout, MFA cancellation |
| `test_drive_auth.py` | First-run token creation, token reuse, expired token refresh |
| `test_drive_upload.py` | Upload returns ID+link, correct parent folder, correct filename, API error handling, folder creation |
| `test_drive_delete.py` | Delete all by ID, success count, partial failure continues, returns errors |
| `test_drive_mapping.py` | Lookup by storeId, unknown returns None, add store persists, get all stores |
| `test_report_split.py` | Group by store, group by store+month, preserves all rows, single store, empty input |
| `test_report_excel.py` | Monthly (1 sheet), quarterly (3 sheets named by month), correct columns, sorted by CreatedOn, file naming, valid xlsx |
| `test_report_summary.py` | 3 columns (Store ID, Store Name, Report URL), one row per store, valid xlsx |

### Integration Tests

| Test | Scope |
|---|---|
| `test_full_monthly_flow` | Full pipeline for 1 month, all services mocked |
| `test_full_quarterly_flow` | Full pipeline for 3 months, verify 3 sheets per store |
| `test_new_store_detection_flow` | Unknown storeId triggers folder creation + mapping update |
| `test_partial_upload_failure_flow` | One store fails, others succeed, last_run.json only tracks successes |
| `test_rollback_flow` | Delete all tracked files, clear last_run.json |
| `test_rollback_specific_stores` | Delete one store's files, others remain in last_run.json |
| `test_dry_run_creates_no_drive_files` | Zero Drive API calls, local files generated |

### Test Fixtures

- `fixtures/sample_query_result.json` — ~50 rows across 3 known stores + 1 unknown store, spanning 3 months
- `fixtures/sample_store_mapping.json` — mapping for the 3 known stores
- `fixtures/sample_last_run.json` — sample rollback state with file IDs

### Coverage

Target: 90%+ on `db/`, `drive/`, `reports/`. UI layer (`app.py`) excluded from coverage target.

## Dependencies

```toml
[project]
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

## Timeline

| Phase | Description | Effort |
|---|---|---|
| 0 | Project setup + test tooling + fixtures | 0.5 day |
| 1 | DB layer (7 tests -> implement -> green) | 1 day |
| 2 | Drive layer (17 tests -> implement -> green) | 2 days |
| 3 | Report logic (17 tests -> implement -> green) | 2 days |
| 3.5 | Integration tests (7 tests -> green) | 0.5 day |
| 4 | Gradio UI + validation tests | 1.5 days |
| 5 | Hardening, manual QA, coverage check | 1 day |
| 6 | Documentation and handoff | 0.5 day |
| **Total** | | **~9 working days** |
