# pyodbc to mssql-python Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace pyodbc with Microsoft's mssql-python driver, enabling native Entra ID MFA authentication on macOS and simplifying the codebase.

**Architecture:** Single connection string (`AZURE_SQL_CONNECTIONSTRING`) with auth method appended based on `AUTH_METHOD` env var. Three auth methods: `active_directory_interactive` (default), `sql_auth`, `service_principal`. All use mssql-python's built-in auth — no manual token handling.

**Tech Stack:** Python 3.13, mssql-python, pytest, uv

**Spec:** `docs/superpowers/specs/2026-04-10-pyodbc-to-mssql-python-migration-design.md`

**Implementation Note:** Final implementation state is complete. `uv.lock` still contains `azure-identity` because it is a transitive dependency of `mssql-python`, and the original per-task red-phase/commit choreography was not followed literally.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `config.py` | Load env vars (connection string, auth method, timeout, credentials) | Simplify — remove old DB vars |
| `.env.example` | Template for env vars | Rewrite — new format |
| `pyproject.toml` | Dependencies | Update — swap pyodbc/azure-identity for mssql-python |
| `db/query.py` | Connection, auth, query execution, error handling, logging | Rewrite — mssql-python API |
| `tests/test_db_query.py` | Unit tests for db/query.py | Rewrite — mock mssql_python.connect |
| `tests/conftest.py` | Shared fixtures | Update — no pyodbc references |
| `tests/db_auth/_helpers.py` | Shared live test helpers | Rewrite — mssql-python, no ODBC |
| `tests/db_auth/conftest.py` | Live test fixture | Update — use new helpers |
| `tests/db_auth/test_sql_auth.py` | Live SQL auth test | Rewrite — mssql-python |
| `tests/db_auth/test_service_principal.py` | Live service principal test | Rewrite — mssql-python |
| `tests/db_auth/test_active_directory_interactive.py` | Live interactive MFA test | Create |
| `tests/db_auth/test_network.py` | DNS, TCP, TLS reachability | Rewrite from test_driver_and_network.py |
| `app.py` | Gradio UI — auth method display | Update — new auth method names |
| `README.md` | User-facing docs | Update — new setup, config, auth |
| `tests/db_auth/test_azure_ad_interactive.py` | Old Windows-only test | Delete |
| `tests/db_auth/test_azure_ad_password.py` | Deprecated auth test | Delete |
| `tests/db_auth/test_driver_and_network.py` | ODBC driver checks | Delete |
| `tests/db_auth/diagnose_db_auth.py` | Diagnostic script | Delete |
| `tests/test_db_connection.py` | ODBC smoke test | Delete |

---

## Task 1: Update Dependencies (Sonnet)

**Files:**
- Modify: `pyproject.toml:7-16`

- [x] **Step 1: Replace pyodbc and azure-identity with mssql-python in pyproject.toml**

Open `pyproject.toml` and replace the dependencies list. Change lines 7-16 from:

```python
dependencies = [
    "pyodbc",
    "azure-identity",
    "openpyxl",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "gradio",
    "python-dotenv",
]
```

to:

```python
dependencies = [
    "mssql-python",
    "openpyxl",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "gradio",
    "python-dotenv",
]
```

- [x] **Step 2: Lock and install the new dependencies**

Run:
```bash
uv lock && uv sync --all-extras
```

Expected: Lock file regenerated, mssql-python installed, pyodbc and azure-identity removed.

- [x] **Step 3: Verify mssql-python is importable**

Run:
```bash
uv run python -c "import mssql_python; print('mssql-python OK')"
```

Expected: `mssql-python OK`

- [x] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: replace pyodbc and azure-identity with mssql-python"
```

---

## Task 2: Simplify config.py (Sonnet)

**Files:**
- Modify: `config.py:1-18`

- [x] **Step 1: Rewrite the Azure SQL section of config.py**

Replace the entire Azure SQL section (lines 6-18) of `config.py`. Keep lines 1-5 (imports and load_dotenv) and lines 20-36 (Google Drive, paths, OAuth) exactly as they are.

Replace:

```python
# Azure SQL
DB_SERVER = os.environ["DB_SERVER"]
DB_DATABASE = os.environ["DB_DATABASE"]
DB_DRIVER = os.environ.get("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
DB_TIMEOUT = int(os.environ.get("DB_TIMEOUT", "1800"))
AUTH_METHOD = os.environ.get("AUTH_METHOD", "sql_auth")
AZURE_SQL_USERNAME = os.environ.get("AZURE_SQL_USERNAME", "")
AZURE_SQL_PASSWORD = os.environ.get("AZURE_SQL_PASSWORD", "")
AZURE_SQL_AUTH_USERNAME = os.environ.get("AZURE_SQL_AUTH_USERNAME", "")
AZURE_SQL_AUTH_PASSWORD = os.environ.get("AZURE_SQL_AUTH_PASSWORD", "")
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
```

With:

```python
# Azure SQL
AZURE_SQL_CONNECTIONSTRING = os.environ["AZURE_SQL_CONNECTIONSTRING"]
DB_TIMEOUT = int(os.environ.get("DB_TIMEOUT", "1800"))
AUTH_METHOD = os.environ.get("AUTH_METHOD", "active_directory_interactive")

# SQL auth (AUTH_METHOD=sql_auth)
AZURE_SQL_AUTH_USERNAME = os.environ.get("AZURE_SQL_AUTH_USERNAME", "")
AZURE_SQL_AUTH_PASSWORD = os.environ.get("AZURE_SQL_AUTH_PASSWORD", "")

# Service principal (AUTH_METHOD=service_principal)
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
```

- [x] **Step 2: Verify config loads without error (with a test .env)**

Run:
```bash
AZURE_SQL_CONNECTIONSTRING="Server=test;Database=test;" GDRIVE_RAW_REPORT_FOLDER_ID=x GDRIVE_REPORTS_FOLDER_ID=x GDRIVE_SUMMARY_FOLDER_ID=x uv run python -c "import config; print('AUTH_METHOD:', config.AUTH_METHOD); print('TIMEOUT:', config.DB_TIMEOUT)"
```

Expected:
```
AUTH_METHOD: active_directory_interactive
TIMEOUT: 1800
```

- [x] **Step 3: Commit**

```bash
git add config.py
git commit -m "refactor: simplify config.py — single connection string, new auth default"
```

---

## Task 3: Rewrite .env.example (Sonnet)

**Files:**
- Modify: `.env.example:1-28`

- [x] **Step 1: Replace .env.example with new format**

Replace the entire contents of `.env.example` with:

```
# Azure SQL connection string (required)
# Contains server, database, encryption settings — auth is appended by the app
AZURE_SQL_CONNECTIONSTRING=Server=your-server.database.windows.net;Database=your-database;Encrypt=yes;TrustServerCertificate=no;

# Auth method: active_directory_interactive | sql_auth | service_principal
# active_directory_interactive: Opens browser for MFA login (default, recommended for Mac)
# sql_auth: Native SQL Server username/password
# service_principal: App-only Entra token (CI/production)
AUTH_METHOD=active_directory_interactive

# Query timeout in seconds (default 1800 = 30 minutes)
DB_TIMEOUT=1800

# For sql_auth only:
AZURE_SQL_AUTH_USERNAME=
AZURE_SQL_AUTH_PASSWORD=

# For service_principal only:
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=

# Google Drive folder IDs
GDRIVE_RAW_REPORT_FOLDER_ID=your-raw-report-folder-id
GDRIVE_REPORTS_FOLDER_ID=your-reports-folder-id
GDRIVE_SUMMARY_FOLDER_ID=your-summary-folder-id
GDRIVE_TEST_FOLDER_ID=your-test-folder-id
```

- [x] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: rewrite .env.example for mssql-python migration"
```

---

## Task 4: Write Unit Tests for db/query.py — TDD (Opus)

This is the TDD phase: write all the failing tests first, then implement in Task 5. The tests define the contract for the new `db/query.py`.

**Files:**
- Modify: `tests/test_db_query.py:1-257` (full rewrite)

- [x] **Step 1: Write the complete test file**

Replace the entire contents of `tests/test_db_query.py` with:

```python
import re
import pytest
from unittest.mock import MagicMock, patch, call

from db.query import (
    EXPECTED_COLUMNS,
    build_date_ranges_sql,
    execute_query,
    _build_connection_string,
    _connect,
)


SQL_TEMPLATE = """DROP TABLE IF EXISTS #DateRanges;
CREATE TABLE #DateRanges (StartDate DATE, EndDate DATE);

INSERT INTO #DateRanges (StartDate, EndDate)
VALUES
    (N'2025-04-01', N'2025-05-01'),
    (N'2025-05-01', N'2025-06-01'),
    (N'2025-06-01', N'2025-07-01');

SELECT CreatedOn, StoreId, RegisterName FROM #FinalResult;"""

BASE_CONN_STR = "Server=test.database.windows.net;Database=testdb;Encrypt=yes;TrustServerCertificate=no;"


# ── Date Range SQL ──────────────────────────────────────────────────────────


class TestBuildDateRangesSql:
    def test_single_month(self):
        result = build_date_ranges_sql([1], 2026)
        assert result == (
            "INSERT INTO #DateRanges (StartDate, EndDate)\n"
            "VALUES\n"
            "    (N'2026-01-01', N'2026-02-01');"
        )

    def test_three_months(self):
        result = build_date_ranges_sql([1, 2, 3], 2026)
        assert "(N'2026-01-01', N'2026-02-01')" in result
        assert "(N'2026-02-01', N'2026-03-01')" in result
        assert "(N'2026-03-01', N'2026-04-01')" in result

    def test_december_wraps_to_next_year(self):
        result = build_date_ranges_sql([12], 2026)
        assert "(N'2026-12-01', N'2027-01-01')" in result


# ── Connection String Building ──────────────────────────────────────────────


class TestBuildConnectionString:
    def test_active_directory_interactive_default(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "active_directory_interactive"
            result = _build_connection_string()
        assert "Authentication=ActiveDirectoryInteractive;" in result
        assert BASE_CONN_STR in result

    def test_invalid_auth_method_is_unsupported(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "unsupported_auth"
            with pytest.raises(ValueError, match="Unsupported AUTH_METHOD"):
                _build_connection_string()

    def test_sql_auth_appends_uid_and_pwd(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "sql_auth"
            mock_config.AZURE_SQL_AUTH_USERNAME = "sql-user"
            mock_config.AZURE_SQL_AUTH_PASSWORD = "sql-pass"
            result = _build_connection_string()
        assert "UID=sql-user;" in result
        assert "PWD=sql-pass;" in result
        assert "Authentication=" not in result

    def test_service_principal_appends_auth_uid_pwd(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "service_principal"
            mock_config.AZURE_CLIENT_ID = "my-client-id"
            mock_config.AZURE_CLIENT_SECRET = "my-secret"
            result = _build_connection_string()
        assert "Authentication=ActiveDirectoryServicePrincipal;" in result
        assert "UID=my-client-id;" in result
        assert "PWD=my-secret;" in result

    def test_unsupported_auth_method_raises(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "bogus_method"
            with pytest.raises(ValueError, match="Unsupported AUTH_METHOD"):
                _build_connection_string()

    def test_sql_auth_missing_username_raises(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "sql_auth"
            mock_config.AZURE_SQL_AUTH_USERNAME = ""
            mock_config.AZURE_SQL_AUTH_PASSWORD = "pass"
            with pytest.raises(ValueError, match="AZURE_SQL_AUTH_USERNAME"):
                _build_connection_string()

    def test_sql_auth_missing_password_raises(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "sql_auth"
            mock_config.AZURE_SQL_AUTH_USERNAME = "user"
            mock_config.AZURE_SQL_AUTH_PASSWORD = ""
            with pytest.raises(ValueError, match="AZURE_SQL_AUTH_PASSWORD"):
                _build_connection_string()

    def test_service_principal_missing_client_id_raises(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "service_principal"
            mock_config.AZURE_CLIENT_ID = ""
            mock_config.AZURE_CLIENT_SECRET = "secret"
            with pytest.raises(ValueError, match="AZURE_CLIENT_ID"):
                _build_connection_string()

    def test_service_principal_missing_client_secret_raises(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "service_principal"
            mock_config.AZURE_CLIENT_ID = "id"
            mock_config.AZURE_CLIENT_SECRET = ""
            with pytest.raises(ValueError, match="AZURE_CLIENT_SECRET"):
                _build_connection_string()


# ── Connection ──────────────────────────────────────────────────────────────


class TestConnect:
    def test_connect_calls_mssql_python_and_sets_timeout(self):
        mock_conn = MagicMock()
        with patch("db.query._build_connection_string", return_value="conn_str"), \
             patch("db.query.connect", return_value=mock_conn) as mock_connect, \
             patch("db.query.config") as mock_config:
            mock_config.DB_TIMEOUT = 1800
            result = _connect()
        mock_connect.assert_called_once_with("conn_str")
        assert mock_conn.timeout == 1800
        assert result is mock_conn

    def test_connect_uses_custom_timeout(self):
        mock_conn = MagicMock()
        with patch("db.query._build_connection_string", return_value="conn_str"), \
             patch("db.query.connect", return_value=mock_conn), \
             patch("db.query.config") as mock_config:
            mock_config.DB_TIMEOUT = 60
            _connect()
        assert mock_conn.timeout == 60


# ── Query Execution ─────────────────────────────────────────────────────────


class TestExecuteQuery:
    def _mock_conn_with_rows(self, rows, columns=None):
        if columns is None:
            columns = EXPECTED_COLUMNS
        mock_cursor = MagicMock()
        mock_cursor.description = [
            (col, None, None, None, None, None, None) for col in columns
        ]
        mock_cursor.fetchall.return_value = rows
        mock_cursor.nextset.return_value = False
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_returns_list_of_dicts(self):
        row = ("2026-01-02", 100, "Store A", 0, 500, 0, 0, 200, 100, 200, 0, 0, 0)
        mock_conn = self._mock_conn_with_rows([row])
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", return_value=mock_conn):
            result = execute_query([1], 2026)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["StoreId"] == 100
        assert result[0]["RegisterName"] == "Store A"

    def test_returns_expected_columns(self):
        row = ("2026-01-02", 100, "Store A", 0, 500, 0, 0, 200, 100, 200, 0, 0, 0)
        mock_conn = self._mock_conn_with_rows([row])
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", return_value=mock_conn):
            result = execute_query([1], 2026)
        assert set(result[0].keys()) == set(EXPECTED_COLUMNS)

    def test_handles_empty_result(self):
        mock_conn = self._mock_conn_with_rows([])
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", return_value=mock_conn):
            result = execute_query([1], 2026)
        assert result == []

    def test_iterates_through_multiple_resultsets(self):
        mock_conn = self._mock_conn_with_rows([])
        mock_conn.cursor.return_value.nextset.side_effect = [True, False]
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", return_value=mock_conn):
            result = execute_query([1], 2026)
        assert result == []

    def test_reads_sql_template_file(self, tmp_path):
        from db.query import _read_sql_template
        sql_content = "SELECT 1;"
        sql_file = tmp_path / "test_template.sql"
        sql_file.write_text(sql_content, encoding="utf-8")
        with patch("db.query.config") as mock_config:
            mock_config.SQL_TEMPLATE_PATH = str(sql_file)
            result = _read_sql_template()
        assert result == sql_content


# ── Error Handling ──────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_connection_failure_raises_connection_error(self):
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", side_effect=Exception("Connection refused")):
            with pytest.raises(ConnectionError, match="connect"):
                execute_query([1], 2026)

    def test_timeout_error_mapped_from_operational_error(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("HYT00 Query timeout expired")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", return_value=mock_conn):
            with pytest.raises(TimeoutError, match="timed out"):
                execute_query([1], 2026)

    def test_non_timeout_db_error_raises_connection_error(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("42000 Syntax error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", return_value=mock_conn):
            with pytest.raises(ConnectionError, match="query failed"):
                execute_query([1], 2026)

    def test_connection_closed_even_on_error(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("42000 Syntax error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", return_value=mock_conn):
            with pytest.raises(ConnectionError):
                execute_query([1], 2026)
        mock_conn.__exit__.assert_called_once()


# ── Logging ─────────────────────────────────────────────────────────────────


class TestLogging:
    def test_logs_auth_method(self, caplog):
        row = ("2026-01-02", 100, "Store A", 0, 500, 0, 0, 200, 100, 200, 0, 0, 0)
        mock_cursor = MagicMock()
        mock_cursor.description = [
            (col, None, None, None, None, None, None) for col in EXPECTED_COLUMNS
        ]
        mock_cursor.fetchall.return_value = [row]
        mock_cursor.nextset.return_value = False
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
             patch("db.query._connect", return_value=mock_conn), \
             patch("db.query.config") as mock_config:
            mock_config.AUTH_METHOD = "active_directory_interactive"
            import logging
            with caplog.at_level(logging.INFO, logger="vat_reports"):
                execute_query([1], 2026)
        assert any("active_directory_interactive" in r.message for r in caplog.records)

    def test_masks_password_in_connection_string_log(self, caplog):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "sql_auth"
            mock_config.AZURE_SQL_AUTH_USERNAME = "user"
            mock_config.AZURE_SQL_AUTH_PASSWORD = "supersecret"
            import logging
            with caplog.at_level(logging.INFO, logger="vat_reports"):
                conn_str = _build_connection_string()
        # The actual password must not appear in any log record
        for record in caplog.records:
            assert "supersecret" not in record.message
```

- [x] **Step 2: Run the tests — verify they fail**

Run:
```bash
uv run pytest tests/test_db_query.py -v 2>&1 | head -80
```

Expected: All tests FAIL (ImportError or AttributeError because `db/query.py` still uses pyodbc and doesn't have `_build_connection_string`). This is correct — we haven't implemented yet.

- [x] **Step 3: Commit the failing tests**

```bash
git add tests/test_db_query.py
git commit -m "test: write failing unit tests for mssql-python migration (TDD red phase)"
```

---

## Task 5: Rewrite db/query.py (Opus)

**Files:**
- Modify: `db/query.py:1-187` (full rewrite)

- [x] **Step 1: Replace the entire contents of db/query.py**

Replace the full file with:

```python
import logging
import re
import time

import config
from mssql_python import connect

logger = logging.getLogger("vat_reports")

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

_VALID_AUTH_METHODS = {
    "active_directory_interactive",
    "sql_auth",
    "service_principal",
}


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


def _require_setting(name: str, value: str) -> str:
    if value:
        return value
    raise ValueError(
        f"Missing required setting: {name}. "
        f"Set it in your .env file or environment variables."
    )


def _mask_connection_string(conn_str: str) -> str:
    """Replace PWD=<value> with PWD=*** for safe logging."""
    return re.sub(r"PWD=[^;]*", "PWD=***", conn_str)


def _build_connection_string() -> str:
    base = config.AZURE_SQL_CONNECTIONSTRING
    auth = config.AUTH_METHOD

    if auth not in _VALID_AUTH_METHODS:
        raise ValueError(
            f"Unsupported AUTH_METHOD='{auth}'. "
            f"Use one of: {', '.join(sorted(_VALID_AUTH_METHODS))}"
        )

    if auth == "active_directory_interactive":
        return base + "Authentication=ActiveDirectoryInteractive;"

    if auth == "sql_auth":
        username = _require_setting("AZURE_SQL_AUTH_USERNAME", config.AZURE_SQL_AUTH_USERNAME)
        password = _require_setting("AZURE_SQL_AUTH_PASSWORD", config.AZURE_SQL_AUTH_PASSWORD)
        return base + f"UID={username};PWD={password};"

    if auth == "service_principal":
        client_id = _require_setting("AZURE_CLIENT_ID", config.AZURE_CLIENT_ID)
        client_secret = _require_setting("AZURE_CLIENT_SECRET", config.AZURE_CLIENT_SECRET)
        return base + f"Authentication=ActiveDirectoryServicePrincipal;UID={client_id};PWD={client_secret};"

    raise ValueError(f"Unsupported AUTH_METHOD='{auth}'")


def _connect():
    auth = config.AUTH_METHOD
    logger.info(f"Auth method: {auth} (set via AUTH_METHOD env var)")

    conn_str = _build_connection_string()
    logger.info(f"Connection string: {_mask_connection_string(conn_str)}")

    if auth == "active_directory_interactive":
        logger.info("Connecting to database... (this may open a browser window for MFA)")
    else:
        logger.info("Connecting to database...")

    conn = connect(conn_str)
    conn.timeout = config.DB_TIMEOUT
    logger.info("Database connection established successfully")
    return conn


def execute_query(months: list[int], year: int) -> list[dict]:
    logger.info(f"execute_query called: months={months}, year={year}")

    logger.info(f"Loading SQL template from {config.SQL_TEMPLATE_PATH}")
    template = _read_sql_template()
    new_insert = build_date_ranges_sql(months, year)
    sql = _DATE_RANGES_PATTERN.sub(new_insert, template)
    logger.info("SQL template prepared with date ranges injected")

    try:
        conn = _connect()
    except ValueError as e:
        logger.error(f"Database auth configuration failed: {e}")
        raise ConnectionError(f"Failed to connect to database: {e}") from e
    except Exception as e:
        logger.error(f"Database connection failed using auth method '{config.AUTH_METHOD}'")
        logger.error(f"Error: {e}")
        logger.error(
            "Suggestions: 1) Check your Azure permissions "
            "2) Complete the browser MFA flow for interactive login "
            "3) Check IP whitelist in Azure portal"
        )
        raise ConnectionError(f"Failed to connect to database: {e}") from e

    try:
        with conn:
            cursor = conn.cursor()
            logger.info(f"Executing query for months {months}, year {year}...")
            start_time = time.time()
            cursor.execute(sql)
            while cursor.nextset():
                pass
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            elapsed = time.time() - start_time
            logger.info(f"Query complete: {len(rows)} rows, {len(columns)} columns in {elapsed:.1f}s")
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        error_str = str(e)
        if "HYT00" in error_str or "HYT01" in error_str or "timeout" in error_str.lower():
            logger.error(f"Database query timed out after {config.DB_TIMEOUT}s")
            logger.error(
                "Suggestions: 1) Increase DB_TIMEOUT env var "
                "2) Check if the query is running in Azure portal "
                "3) Try fewer months at once"
            )
            raise TimeoutError(f"Database query timed out: {e}") from e
        logger.error(f"Database query failed: {e}")
        raise ConnectionError(f"Database query failed: {e}") from e
    finally:
        logger.info("Database connection closed")
```

- [x] **Step 2: Run the unit tests — verify they pass**

Run:
```bash
uv run pytest tests/test_db_query.py -v
```

Expected: All tests PASS. If any fail, fix the implementation to match the test contract, not the other way around.

- [x] **Step 3: Commit**

```bash
git add db/query.py
git commit -m "feat: rewrite db/query.py — mssql-python with 4 auth methods and verbose logging"
```

---

## Task 6: Update tests/conftest.py (Sonnet)

**Files:**
- Modify: `tests/conftest.py`

The conftest currently has no pyodbc references, but verify it doesn't need changes. The `_patch_media_upload`, `sample_query_result`, `sample_store_mapping`, and `sample_last_run` fixtures are unrelated to the DB layer.

- [x] **Step 1: Verify conftest has no pyodbc references**

Read `tests/conftest.py`. It should not import or reference `pyodbc`. If it does, remove those references. Based on current state, no changes are needed.

- [x] **Step 2: Run the full test suite to verify nothing is broken**

Run:
```bash
uv run pytest tests/test_db_query.py tests/test_input_validation.py -v 2>&1 | tail -20
```

Expected: All tests pass. No import errors.

- [x] **Step 3: Commit (only if changes were made)**

```bash
git add tests/conftest.py
git commit -m "chore: verify conftest.py has no pyodbc references"
```

---

## Task 7: Rewrite Live Test Helpers (Sonnet)

**Files:**
- Modify: `tests/db_auth/_helpers.py:1-183` (full rewrite)
- Modify: `tests/db_auth/conftest.py:1-8`

- [x] **Step 1: Replace tests/db_auth/_helpers.py**

Replace the entire file with:

```python
import os
import platform
import re
import socket
import ssl
import time

from mssql_python import connect

VERIFICATION_QUERY = "SELECT s.id FROM store AS s WHERE s.active = 1;"


def load_config():
    import config
    return config


def platform_name() -> str:
    return platform.system()


def has_connection_string() -> bool:
    try:
        cfg = load_config()
        return bool(cfg.AZURE_SQL_CONNECTIONSTRING)
    except Exception:
        return False


def has_sql_auth() -> bool:
    try:
        cfg = load_config()
        return bool(cfg.AZURE_SQL_AUTH_USERNAME and cfg.AZURE_SQL_AUTH_PASSWORD)
    except Exception:
        return False


def has_service_principal() -> bool:
    try:
        cfg = load_config()
        return bool(cfg.AZURE_CLIENT_ID and cfg.AZURE_CLIENT_SECRET)
    except Exception:
        return False


def extract_server_host(connection_string: str) -> str:
    """Extract the hostname from a connection string like Server=host.database.windows.net;..."""
    match = re.search(r"Server=([^;,]+)", connection_string, re.IGNORECASE)
    if not match:
        raise ValueError(f"Cannot extract Server from connection string: {connection_string}")
    return match.group(1).replace("tcp:", "")


def print_preflight(cfg, auth_label: str, username: str = ""):
    print("\n  Preflight:")
    print(f"    Platform:    {platform_name()}")
    print(f"    Conn String: {cfg.AZURE_SQL_CONNECTIONSTRING[:60]}...")
    print(f"    Auth:        {auth_label}")
    if username:
        print(f"    Username:    {username}")


def build_connection_string(cfg, auth_method: str) -> str:
    """Build a full connection string for the given auth method, for live tests."""
    base = cfg.AZURE_SQL_CONNECTIONSTRING

    if auth_method == "active_directory_interactive":
        return base + "Authentication=ActiveDirectoryInteractive;"

    if auth_method == "sql_auth":
        return base + f"UID={cfg.AZURE_SQL_AUTH_USERNAME};PWD={cfg.AZURE_SQL_AUTH_PASSWORD};"

    if auth_method == "service_principal":
        return base + f"Authentication=ActiveDirectoryServicePrincipal;UID={cfg.AZURE_CLIENT_ID};PWD={cfg.AZURE_CLIENT_SECRET};"

    raise ValueError(f"Unknown auth method: {auth_method}")


def connect_and_verify(conn_str: str, timeout: int = 30):
    """Connect using mssql-python and run the verification query."""
    print("  Connecting...")
    start = time.time()
    conn = connect(conn_str)
    conn.timeout = timeout
    elapsed = time.time() - start
    print(f"  Connected in {elapsed:.1f}s")

    cursor = conn.cursor()
    print(f"  Running: {VERIFICATION_QUERY}")
    cursor.execute(VERIFICATION_QUERY)
    rows = cursor.fetchall()
    conn.close()

    print(f"  Got {len(rows)} active stores")
    for row in rows[:5]:
        print(f"    ID: {row[0]}")
    if len(rows) > 5:
        print(f"    ... and {len(rows) - 5} more")

    assert len(rows) > 0, "Expected at least 1 active store"
    return rows


def resolve_server_addresses(server_host: str) -> list[str]:
    infos = socket.getaddrinfo(server_host, 1433, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def probe_tcp_port(server_host: str, port: int = 1433, timeout: float = 5.0) -> float:
    start = time.time()
    with socket.create_connection((server_host, port), timeout=timeout):
        return time.time() - start


def probe_tls(server_host: str, port: int = 1433, timeout: float = 5.0) -> str:
    """Attempt a TLS handshake and return the server certificate subject."""
    context = ssl.create_default_context()
    with socket.create_connection((server_host, port), timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=server_host) as ssock:
            cert = ssock.getpeercert()
            subject = dict(x[0] for x in cert.get("subject", ()))
            return subject.get("commonName", str(cert.get("subject", "unknown")))
```

- [x] **Step 2: Update tests/db_auth/conftest.py**

Replace the entire file with:

```python
import pytest

from tests.db_auth._helpers import load_config


@pytest.fixture
def cfg():
    return load_config()
```

(This is the same content, but confirms it doesn't need changes.)

- [x] **Step 3: Verify the helpers module imports cleanly**

Run:
```bash
uv run python -c "from tests.db_auth._helpers import has_connection_string, has_sql_auth; print('helpers OK')"
```

Expected: `helpers OK`

- [x] **Step 4: Commit**

```bash
git add tests/db_auth/_helpers.py tests/db_auth/conftest.py
git commit -m "refactor: rewrite live test helpers for mssql-python"
```

---

## Task 8: Rewrite Live Auth Tests (Sonnet)

**Files:**
- Modify: `tests/db_auth/test_sql_auth.py:1-37` (full rewrite)
- Modify: `tests/db_auth/test_service_principal.py:1-39` (full rewrite)
- Create: `tests/db_auth/test_active_directory_interactive.py`
Each test follows the same pattern: build connection string → connect → run `SELECT s.id FROM store AS s WHERE s.active = 1;` → assert rows.

- [x] **Step 1: Rewrite tests/db_auth/test_sql_auth.py**

Replace the entire file with:

```python
import pytest

from tests.db_auth._helpers import (
    build_connection_string,
    connect_and_verify,
    has_sql_auth,
    print_preflight,
)

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not has_sql_auth(),
    reason="AZURE_SQL_AUTH_USERNAME/AZURE_SQL_AUTH_PASSWORD not in .env",
)
def test_sql_auth(cfg):
    """Connect using SQL Server native username/password and verify with active stores query."""
    print_preflight(cfg, "SQL Server Authentication", cfg.AZURE_SQL_AUTH_USERNAME)
    conn_str = build_connection_string(cfg, "sql_auth")
    connect_and_verify(conn_str, timeout=min(cfg.DB_TIMEOUT, 30))
```

- [x] **Step 2: Rewrite tests/db_auth/test_service_principal.py**

Replace the entire file with:

```python
import pytest

from tests.db_auth._helpers import (
    build_connection_string,
    connect_and_verify,
    has_service_principal,
    print_preflight,
)

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not has_service_principal(),
    reason="AZURE_CLIENT_ID/AZURE_CLIENT_SECRET not in .env",
)
def test_service_principal(cfg):
    """Connect using service principal (Entra app) and verify with active stores query."""
    print_preflight(cfg, "Service Principal (ActiveDirectoryServicePrincipal)")
    conn_str = build_connection_string(cfg, "service_principal")
    connect_and_verify(conn_str, timeout=min(cfg.DB_TIMEOUT, 30))
```

- [x] **Step 3: Create tests/db_auth/test_active_directory_interactive.py**

Create the file with:

```python
import pytest

from tests.db_auth._helpers import (
    build_connection_string,
    connect_and_verify,
    has_connection_string,
    print_preflight,
)

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not has_connection_string(),
    reason="AZURE_SQL_CONNECTIONSTRING not in .env",
)
def test_active_directory_interactive(cfg):
    """Connect using Entra ID interactive MFA (browser popup) and verify with active stores query.

    NOTE: This test will open a browser window for MFA authentication.
    It cannot be run in headless/CI environments.
    """
    print_preflight(cfg, "ActiveDirectoryInteractive (MFA browser popup)")
    print("  >> A browser window should open for MFA authentication...")
    conn_str = build_connection_string(cfg, "active_directory_interactive")
    connect_and_verify(conn_str, timeout=min(cfg.DB_TIMEOUT, 60))
```

- [x] **Step 4: Verify tests are collected (they'll be skipped without live creds)**

Run:
```bash
uv run pytest tests/db_auth/ --collect-only 2>&1 | tail -20
```

Expected: All 4 test files collected, tests shown as either `<Function test_...>` or marked for skip.

- [x] **Step 5: Commit**

```bash
git add tests/db_auth/test_sql_auth.py tests/db_auth/test_service_principal.py tests/db_auth/test_active_directory_interactive.py
git commit -m "test: rewrite live auth tests for mssql-python with active stores verification"
```

---

## Task 9: Rewrite Network Tests (Sonnet)

**Files:**
- Create: `tests/db_auth/test_network.py` (replaces test_driver_and_network.py)

- [x] **Step 1: Create tests/db_auth/test_network.py**

Create the file with:

```python
import pytest

from tests.db_auth._helpers import (
    extract_server_host,
    has_connection_string,
    probe_tcp_port,
    probe_tls,
    resolve_server_addresses,
)

pytestmark = pytest.mark.live


@pytest.mark.skipif(not has_connection_string(), reason="AZURE_SQL_CONNECTIONSTRING not in .env")
def test_dns_resolution(cfg):
    """Resolve the configured DB hostname to one or more IP addresses.

    If this fails: Is the server name correct in AZURE_SQL_CONNECTIONSTRING?
    """
    host = extract_server_host(cfg.AZURE_SQL_CONNECTIONSTRING)
    addresses = resolve_server_addresses(host)
    print(f"\n  Host:      {host}")
    print("  Resolved addresses:")
    for address in addresses:
        print(f"    - {address}")
    assert addresses, (
        f"DNS resolution failed for '{host}'. "
        f"Check the Server= value in AZURE_SQL_CONNECTIONSTRING."
    )


@pytest.mark.skipif(not has_connection_string(), reason="AZURE_SQL_CONNECTIONSTRING not in .env")
def test_tcp_port_1433_reachable(cfg):
    """Probe raw TCP connectivity to the SQL Server port.

    If this fails: Is your VPN on? Is your IP whitelisted in the Azure SQL firewall?
    """
    host = extract_server_host(cfg.AZURE_SQL_CONNECTIONSTRING)
    print(f"\n  Host: {host}")
    print("  Port: 1433")
    try:
        elapsed = probe_tcp_port(host)
        print(f"  Connected in {elapsed:.2f}s")
    except (OSError, TimeoutError) as e:
        pytest.fail(
            f"TCP connection to {host}:1433 failed: {e}. "
            f"Is your VPN on? Is your IP whitelisted in the Azure SQL firewall?"
        )


@pytest.mark.skipif(not has_connection_string(), reason="AZURE_SQL_CONNECTIONSTRING not in .env")
def test_tls_handshake(cfg):
    """Attempt a TLS handshake with the SQL Server.

    If this fails: Check certificate/encryption settings.
    """
    host = extract_server_host(cfg.AZURE_SQL_CONNECTIONSTRING)
    print(f"\n  Host: {host}")
    try:
        cn = probe_tls(host)
        print(f"  TLS handshake OK — certificate CN: {cn}")
    except Exception as e:
        pytest.fail(
            f"TLS handshake with {host}:1433 failed: {e}. "
            f"Check certificate/encryption settings in AZURE_SQL_CONNECTIONSTRING."
        )
```

- [x] **Step 2: Verify test collection**

Run:
```bash
uv run pytest tests/db_auth/test_network.py --collect-only
```

Expected: 3 tests collected.

- [x] **Step 3: Commit**

```bash
git add tests/db_auth/test_network.py
git commit -m "test: add network reachability tests (DNS, TCP, TLS) for mssql-python"
```

---

## Task 10: Delete Old Files (Sonnet)

**Files:**
- Delete: `tests/db_auth/test_azure_ad_interactive.py`
- Delete: `tests/db_auth/test_azure_ad_password.py`
- Delete: `tests/db_auth/test_driver_and_network.py`
- Delete: `tests/db_auth/diagnose_db_auth.py`
- Delete: `tests/test_db_connection.py`
- Delete: `tests/db_auth/README.md` (references old auth methods)

- [x] **Step 1: Delete all obsolete files**

Run:
```bash
git rm tests/db_auth/test_azure_ad_interactive.py tests/db_auth/test_azure_ad_password.py tests/db_auth/test_driver_and_network.py tests/db_auth/diagnose_db_auth.py tests/test_db_connection.py tests/db_auth/README.md
```

- [x] **Step 2: Verify no remaining pyodbc references in test files**

Run:
```bash
grep -r "pyodbc" tests/
```

Expected: No matches. If any remain, fix them.

- [x] **Step 3: Commit**

```bash
git commit -m "chore: delete obsolete pyodbc test files and diagnostics"
```

---

## Task 11: Update app.py Auth Method Display (Sonnet)

**Files:**
- Modify: `app.py:90-113`

- [x] **Step 1: Replace the auth method display block in app.py**

In `app.py`, replace lines 91-111 (the auth method if/elif/else block inside `generate_reports`) with the new auth methods:

Replace:

```python
        auth_method = cfg.AUTH_METHOD
        log(f"Auth method: {auth_method}")
        log("Connecting to database...")
        if auth_method == "sql_auth":
            log(f">> Using SQL Server authentication (user: {cfg.AZURE_SQL_AUTH_USERNAME})")
            yield state(status="**Connecting to database...** Using SQL username/password.")
        elif auth_method == "service_principal":
            log(">> Using service principal authentication (app-only Entra token)")
            yield state(status="**Connecting to database...** Service principal token auth.")
        elif auth_method == "azure_ad_password":
            log(">> AUTH_METHOD=azure_ad_password is deprecated for this project")
            log(">> Use AUTH_METHOD=sql_auth on macOS, or service_principal if IT approves it")
            yield state(status="**Database Configuration Error:** azure_ad_password is deprecated.")
        else:
            if platform.system() == "Windows":
                log(">> Azure AD Interactive — MFA popup should appear")
                yield state(status="**Connecting to database...** Azure AD popup should appear.")
            else:
                log(">> AUTH_METHOD=azure_ad is Windows-only with the current ODBC driver")
                log(">> Use AUTH_METHOD=sql_auth on macOS, or service_principal if IT approves it")
                yield state(status="**Database Configuration Error:** azure_ad is Windows-only.")
```

With:

```python
        auth_method = cfg.AUTH_METHOD
        log(f"Auth method: {auth_method}")
        log("Connecting to database...")
        if auth_method == "active_directory_interactive":
            log(">> Entra ID Interactive — a browser window may open for MFA")
            yield state(status="**Connecting to database...** MFA browser popup may appear.")
        elif auth_method == "sql_auth":
            log(f">> Using SQL Server authentication (user: {cfg.AZURE_SQL_AUTH_USERNAME})")
            yield state(status="**Connecting to database...** Using SQL username/password.")
        elif auth_method == "service_principal":
            log(">> Using service principal authentication (Entra app)")
            yield state(status="**Connecting to database...** Service principal token auth.")
        else:
            log(f">> Unknown AUTH_METHOD='{auth_method}'")
            yield state(status=f"**Configuration Error:** Unknown AUTH_METHOD='{auth_method}'.")
```

- [x] **Step 2: Remove the `platform` import if no longer used elsewhere**

Check if `platform` is still used in `app.py`. It is — in `open_log_folder()` (line 287). So keep the import.

- [x] **Step 3: Verify the app module imports without error**

Run:
```bash
AZURE_SQL_CONNECTIONSTRING="Server=test;Database=test;" GDRIVE_RAW_REPORT_FOLDER_ID=x GDRIVE_REPORTS_FOLDER_ID=x GDRIVE_SUMMARY_FOLDER_ID=x uv run python -c "import app; print('app.py OK')"
```

Expected: `app.py OK`

- [x] **Step 4: Commit**

```bash
git add app.py
git commit -m "refactor: update app.py auth method display for mssql-python"
```

---

## Task 12: Update README.md (Sonnet)

**Files:**
- Modify: `README.md`

- [x] **Step 1: Update Prerequisites section (section 2)**

Replace the Prerequisites section. Remove the ODBC Driver 18 bullet. Add `openssl` for macOS and Azure CLI for MFA.

Replace:

```markdown
## 2. Prerequisites

Before setting up, make sure the following are in place:

- **Python 3.13 or higher** installed on your machine.
- **ODBC Driver 18 for SQL Server** installed. Download it from the [Microsoft documentation](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).
- A **Google Cloud project** with the Google Drive API enabled.
- A **`credentials.json`** file downloaded from Google Cloud Console (OAuth 2.0 Client ID, Desktop app type). Place this file in the project root folder.
- **Network access** to the Azure SQL database — your office IP address must be whitelisted. If working remotely, connect via the office VPN first.
```

With:

```markdown
## 2. Prerequisites

Before setting up, make sure the following are in place:

- **Python 3.13 or higher** installed on your machine.
- **OpenSSL** installed (macOS: `brew install openssl`).
- **Azure CLI** installed for MFA authentication (macOS: `brew install azure-cli`). Run `az login` once to cache your credential.
- A **Google Cloud project** with the Google Drive API enabled.
- A **`credentials.json`** file downloaded from Google Cloud Console (OAuth 2.0 Client ID, Desktop app type). Place this file in the project root folder.
- **Network access** to the Azure SQL database — your office IP address must be whitelisted. If working remotely, connect via the office VPN first.
```

- [x] **Step 2: Update Setup section (section 3, step 3)**

Replace the AUTH_METHOD description block. Replace:

```markdown
   - Set `AUTH_METHOD` to match the credential type you actually have:
     - `sql_auth` is the preferred macOS path. It uses a native SQL Server login via `AZURE_SQL_AUTH_USERNAME` and `AZURE_SQL_AUTH_PASSWORD`.
     - `service_principal` uses an app-only Microsoft Entra access token. Configure `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET` only if DBA / tenant policy explicitly allows it.
     - `azure_ad` uses `ActiveDirectoryInteractive` and is only supported by the current ODBC approach on Windows.
     - `azure_ad_password` is deprecated and kept only as a manual diagnostic path. Do not use it as the normal app configuration.
```

With:

```markdown
   - Set `AUTH_METHOD` to match the credential type you actually have:
     - `active_directory_interactive` **(default, recommended)** — opens a browser window for Entra ID MFA login. Works on macOS, Windows, and Linux.
     - `sql_auth` — native SQL Server login via `AZURE_SQL_AUTH_USERNAME` and `AZURE_SQL_AUTH_PASSWORD`.
     - `service_principal` — app-only Entra token via `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET`. For CI/production use.
```

- [x] **Step 3: Update Running the App section (section 4)**

Replace the two paragraphs after the run commands. Replace:

```markdown
If you run on Windows with `AUTH_METHOD=azure_ad`, an **Azure AD MFA popup** may appear on your screen. Approve it promptly. If it takes a moment to appear, wait before clicking anything else.

On macOS, use `sql_auth` first. If IT approves app-only database access, `service_principal` is the other supported path in this project.
```

With:

```markdown
With `AUTH_METHOD=active_directory_interactive` (the default), a **browser window** will open for Entra ID MFA authentication. Complete the login and return to the app. This works on macOS, Windows, and Linux.
```

- [x] **Step 4: Update Troubleshooting table (section 7)**

Replace the entire troubleshooting table with:

```markdown
| Problem | What to do |
|---|---|
| "Connection failed" when querying the database | Check that you are on the office network or connected via VPN. Your IP must be whitelisted on the Azure SQL firewall. |
| MFA browser window does not appear | Make sure `AUTH_METHOD=active_directory_interactive` is set. If the popup is blocked, try a different browser as default. |
| SQL auth says it cannot open the server requested by the login | `sql_auth` is only for native SQL Server logins. Use `AZURE_SQL_AUTH_USERNAME` / `AZURE_SQL_AUTH_PASSWORD` for that path. Do not use an email address there. |
| Service principal auth fails | Confirm that `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` are correct, and the service principal is allowed to access Azure SQL. |
| Google Drive permission error | Confirm that `credentials.json` is present in the project root and is valid. If the issue persists, delete `token.json` and re-run to go through the authorization flow again. |
| The query is taking a very long time | This is expected. Queries typically take 7 to 20 minutes depending on the date range selected. Do not close the browser or terminal. |
```

- [x] **Step 5: Update Running Tests section (section 8)**

Replace the diagnostic commands block. Replace:

```markdown
Database auth diagnostics live in `tests/db_auth/` and are intended for isolated live experiments:

```bash
uv run pytest tests/db_auth -m live -v -s
```

For a single real-credential diagnostic sweep with a final summary table:

```bash
uv run python tests/db_auth/diagnose_db_auth.py
```

Run one diagnostic area at a time when investigating DB access:

```bash
uv run pytest tests/db_auth/test_driver_and_network.py -m live -v -s
uv run pytest tests/db_auth/test_azure_ad_interactive.py -m live -v -s
uv run pytest tests/db_auth/test_azure_ad_password.py -m live -v -s
uv run pytest tests/db_auth/test_sql_auth.py -m live -v -s
uv run pytest tests/db_auth/test_service_principal.py -m live -v -s
```

The legacy `tests/test_db_connection.py` file remains as a small smoke/preflight suite only.
```

With:

```markdown
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
```

- [x] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: update README for mssql-python migration — new auth methods, no ODBC"
```

---

## Task 13: Final Verification (Opus)

- [x] **Step 1: Run full unit test suite**

Run:
```bash
uv run pytest --tb=short -v 2>&1 | tail -40
```

Expected: All unit tests pass. No import errors. No pyodbc references.

- [x] **Step 2: Verify no pyodbc or azure-identity references remain in source code**

Run:
```bash
grep -r "pyodbc\|azure.identity\|azure-identity\|ODBC Driver" --include="*.py" --include="*.toml" --include="*.md" --include="*.example" . | grep -v ".git/" | grep -v "__pycache__" | grep -v "uv.lock" | grep -v "docs/superpowers/"
```

Expected: No matches. If any remain, fix them.

- [x] **Step 3: Verify the app starts without error**

Run:
```bash
AZURE_SQL_CONNECTIONSTRING="Server=test;Database=test;" GDRIVE_RAW_REPORT_FOLDER_ID=x GDRIVE_REPORTS_FOLDER_ID=x GDRIVE_SUMMARY_FOLDER_ID=x uv run python -c "import app; print('Full app import OK')"
```

Expected: `Full app import OK`

- [x] **Step 4: Run coverage report**

Run:
```bash
uv run pytest --cov=db --cov-report=term-missing tests/test_db_query.py -v 2>&1 | tail -20
```

Expected: High coverage on `db/query.py`. All branches for auth methods and error handling covered.

- [x] **Step 5: Commit any final fixes**

If any issues were found in steps 1-4, fix them and commit:
```bash
git add -A
git commit -m "fix: address final verification issues from mssql-python migration"
```
