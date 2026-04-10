# VAT Reports Generator

## 1. What is this?

The VAT Reports Generator is an internal tool built for Belchicken accounting staff. It connects to the Azure SQL database, queries VAT transaction data for all stores, and automatically produces per-store Excel reports — either monthly or quarterly. The generated reports are uploaded to the appropriate Google Drive folders, and a summary spreadsheet with direct links to each store's file is created at the end. The tool runs through a simple web interface (Gradio) that opens in your browser. It also supports rollback, allowing you to delete all or specific store files from the most recent upload if something went wrong.

---

## 2. Prerequisites

Before setting up, make sure the following are in place:

- **Python 3.13 or higher** installed on your machine.
- **OpenSSL** installed (macOS: `brew install openssl`).
- A **Google Cloud project** with the Google Drive API enabled.
- A **`credentials.json`** file downloaded from Google Cloud Console (OAuth 2.0 Client ID, Desktop app type). Place this file in the project root folder.
- **Network access** to the Azure SQL database — your office IP address must be whitelisted. If working remotely, connect via the office VPN first.

---

## 3. Setup

1. **Clone the repository** to your local machine.

2. **Run the setup script** for your operating system. Open a terminal in the project folder and run:
   - Windows: `scripts\setup.bat`
   - Mac: `./scripts/setup.sh`

   This will create a virtual environment and install all dependencies automatically.

3. **Configure environment variables:**
   - Copy `.env.example` to `.env` in the project root.
   - Open `.env` and fill in the real values for the Azure SQL connection string and Google Drive folder IDs.
   - Set `AUTH_METHOD` to match the credential type you actually have:
     - `active_directory_interactive` **(default, recommended)** — opens a browser window for Entra ID MFA login. Works on macOS, Windows, and Linux.
     - `sql_auth` — native SQL Server login via `AZURE_SQL_AUTH_USERNAME` and `AZURE_SQL_AUTH_PASSWORD`.
     - `service_principal` — app-only Entra token via `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET`. For CI/production use.

4. **Place `credentials.json`** (downloaded from Google Cloud Console) in the project root folder.

5. **First-time Google Drive authorization:** The first time you run the app, a browser window will open asking you to sign in to your Google account and grant access to Google Drive. This is a one-time step. A `token.json` file will be saved locally to skip this step on future runs.

---

## 4. Running the App

- Windows: `scripts\run.bat`
- Mac: `./scripts/run.sh`

The script activates the virtual environment and starts the application. A local web address (e.g. `http://127.0.0.1:7860`) will appear in the terminal — open it in your browser.

With `AUTH_METHOD=active_directory_interactive` (the default), a **browser window** will open for Entra ID MFA authentication. Complete the login and return to the app. This works on macOS, Windows, and Linux.

---

## 5. Usage

### Generate Reports tab

1. Enter a **report name** (this is used in file names and the summary).
2. Select the **months** to include in the report.
3. Choose the report mode: **monthly** (one file per store per month) or **quarterly** (one combined file per store).
4. Optionally check **Dry Run** to test the process without uploading anything to Drive.
5. Click **Generate**. The database query takes between **7 and 20 minutes** — this is normal. Do not close the browser tab while it is running.
6. When complete, a table will appear with each store's name and a link to the uploaded Drive file.

### Rollback tab

Use this tab to undo the most recent upload. You can either:
- **Delete all** files uploaded in the last run, or
- **Select specific stores** and delete only those files.

---

## 6. Maintenance

- **`data/store_mapping.json`** — Maps store identifiers from the database to their Google Drive folder names. New stores are detected automatically and added to this file. You can manually edit the folder name for any store if needed.

- **`db/SQL_Query.sql`** — The SQL query sent to the Azure database. If the database column structure changes, this file may need to be updated accordingly.

- **Updating dependencies** — After pulling new changes from the repository, run the following command to keep dependencies in sync:
  ```
  uv sync --all-extras
  ```

- **`token.json`** — Stores your Google Drive authentication token and refreshes automatically. If you experience authentication errors with Google Drive, delete this file and re-run the app to re-authorize.

---

## 7. Troubleshooting

| Problem | What to do |
|---|---|
| "Connection failed" when querying the database | Check that you are on the office network or connected via VPN. Your IP must be whitelisted on the Azure SQL firewall. |
| MFA browser window does not appear | Make sure `AUTH_METHOD=active_directory_interactive` is set. If the popup is blocked, try a different browser as default. |
| SQL auth says it cannot open the server requested by the login | `sql_auth` is only for native SQL Server logins. Use `AZURE_SQL_AUTH_USERNAME` / `AZURE_SQL_AUTH_PASSWORD` for that path. Do not use an email address there. |
| Service principal auth fails | Confirm that `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` are correct, and the service principal is allowed to access Azure SQL. |
| Google Drive permission error | Confirm that `credentials.json` is present in the project root and is valid. If the issue persists, delete `token.json` and re-run to go through the authorization flow again. |
| The query is taking a very long time | This is expected. Queries typically take 7 to 20 minutes depending on the date range selected. Do not close the browser or terminal. |

---

## 8. Running Tests

Run the full test suite:
```
uv run pytest
```

Run with coverage reporting:
```
uv run pytest --cov=db --cov=drive --cov=reports --cov=data
```

All tests mock external services (database and Google Drive). No real connections are made during testing, so tests can be run from any machine without VPN or credentials.

Live database auth tests require real credentials and are skipped by default. Run them with:

```bash
uv run pytest tests/db_auth -m live -v -s
```

Run specific auth methods or network diagnostics:

```bash
uv run pytest tests/db_auth/test_network.py -m live -v -s
uv run pytest tests/db_auth/test_active_directory_interactive.py -m live -v -s
uv run pytest tests/db_auth/test_sql_auth.py -m live -v -s
uv run pytest tests/db_auth/test_service_principal.py -m live -v -s
```

---

## 9. Project Structure

```
new_vat_reports_generator/
|
|-- app.py                  # Gradio web interface
|-- main.py                 # Core orchestration logic
|-- config.py               # Environment variable loading and settings
|-- logging_config.py       # Logging setup
|
|-- db/
|   |-- SQL_Query.sql       # The SQL query sent to Azure
|   `-- query.py            # Database connection and query execution
|
|-- reports/
|   |-- excel.py            # Excel file generation per store
|   |-- split.py            # Splits raw data by store
|   `-- summary.py          # Generates the summary spreadsheet
|
|-- drive/
|   |-- auth.py             # Google Drive OAuth authentication
|   |-- upload.py           # Uploads files to Drive folders
|   |-- delete.py           # Deletes files (used by rollback)
|   `-- mapping.py          # Resolves store-to-folder mappings in Drive
|
|-- data/
|   |-- store_mapping.json  # Store name to Drive folder mapping (editable)
|   `-- last_run_manager.py # Tracks files uploaded in the last run
|
|-- scripts/
|   |-- setup.bat / setup.sh    # One-time environment setup
|   `-- run.bat / run.sh        # Launch the application
|
|-- tests/                  # Automated test suite (all external calls mocked)
|-- fixtures/               # Sample data files used by tests
|-- .env.example            # Template for environment variables
`-- pyproject.toml          # Project dependencies and metadata
```
