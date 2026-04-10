# Migration: pyodbc to mssql-python with Entra ID MFA Support

**Date:** 2026-04-10
**Approach:** Big Bang — swap everything at once, TDD-first
**Status:** Design approved

---

## 1. Overview

Replace `pyodbc` with Microsoft's `mssql-python` driver for all SQL Server connectivity. This removes the ODBC Driver Manager dependency, enables native Microsoft Entra ID MFA authentication on macOS, and simplifies the codebase by eliminating manual token handling.

### Why

- Current pyodbc setup does not work for Entra ID MFA on Mac
- `mssql-python` has built-in Entra ID support (no manual token structs)
- Removes ODBC Driver 18 system dependency
- Removes `azure-identity` package dependency
- Performance improvements (DDBC vs ODBC Driver Manager)
- Microsoft-recommended driver going forward

### What Changes

| Component | Before | After |
|---|---|---|
| Driver | `pyodbc` + ODBC Driver 18 | `mssql-python` (DDBC) |
| Auth default | `sql_auth` | `active_directory_interactive` |
| Token handling | Manual binary struct encoding | Built-in to driver |
| Config pattern | Individual env vars (`DB_SERVER`, `DB_DATABASE`, `DB_DRIVER`) | Single `AZURE_SQL_CONNECTIONSTRING` |
| Dependencies | `pyodbc`, `azure-identity` | `mssql-python` |

---

## 2. Authentication Architecture

Four auth methods, all using `mssql-python`'s built-in connection string authentication:

| `AUTH_METHOD` value | Connection String Auth Param | Extra Params | Use Case |
|---|---|---|---|
| `active_directory_interactive` **(DEFAULT)** | `Authentication=ActiveDirectoryInteractive` | none | Mac dev with MFA browser popup |
| `active_directory_default` | `Authentication=ActiveDirectoryDefault` | none | Mac dev after `az login` (silent) |
| `sql_auth` | none (uses `UID`/`PWD`) | `UID`, `PWD` from env | Legacy/simple auth |
| `service_principal` | `Authentication=ActiveDirectoryServicePrincipal` | `UID=client_id`, `PWD=client_secret` from env; `AZURE_TENANT_ID` read from env by driver if needed | CI/production |

### Removed Auth Methods

- `azure_ad` — replaced by `active_directory_interactive` (now works cross-platform)
- `azure_ad_password` — was already deprecated and rejected in code

### Connection String Construction

1. Read `AZURE_SQL_CONNECTIONSTRING` from env (contains Server, Database, Encrypt, TrustServerCertificate)
2. Read `AUTH_METHOD` from env (default: `active_directory_interactive`)
3. Append `Authentication=...` param based on method
4. For `sql_auth`: append `UID` and `PWD` from env vars
5. For `service_principal`: append `UID=AZURE_CLIENT_ID` and `PWD=AZURE_CLIENT_SECRET` from env vars
6. Call `mssql_python.connect(full_connection_string)`
7. Set `conn.timeout = DB_TIMEOUT`

---

## 3. `db/query.py` Rewrite

### Public API (unchanged)

```python
def execute_query(months: list[int], year: int) -> list[dict]:
```

Same signature, same return type. Callers (`app.py`) require zero changes.

### Internal Functions

**`_connect() -> Connection`**
- Reads config, builds connection string, appends auth params
- Calls `mssql_python.connect(conn_str)`
- Sets `conn.timeout = config.DB_TIMEOUT`
- Returns connection object

**`_build_connection_string() -> str`**
- Takes base `AZURE_SQL_CONNECTIONSTRING` and `AUTH_METHOD`
- Appends auth-specific parameters
- Validates required config per auth method (raises `ValueError` with clear message)
- Returns complete connection string

**`build_date_ranges_sql(months, year) -> str`** — unchanged logic

**`execute_query(months, year) -> list[dict]`**
- Uses `with _connect() as conn:` context manager for auto-cleanup
- Loads SQL template from `db/SQL_Query.sql`
- Injects date ranges via `build_date_ranges_sql()`
- Executes query, iterates multi-result-sets via `cursor.nextset()`
- Converts to list of dicts using `cursor.description`

### Removed Functions

- `_build_access_token_struct()` — no longer needed
- `_get_service_principal_attrs_before()` — no longer needed

### Error Handling

| mssql-python Exception | Condition | Raised As |
|---|---|---|
| `OperationalError` SQLSTATE `HYT00`/`HYT01` | Query timeout | `TimeoutError` |
| `OperationalError` / `DatabaseError` | Connection or query failure | `ConnectionError` |
| N/A | Missing config | `ValueError` |

Every error log includes: auth method used, what was attempted, and actionable suggestions.

---

## 4. Configuration

### `config.py`

```python
AZURE_SQL_CONNECTIONSTRING = os.environ["AZURE_SQL_CONNECTIONSTRING"]  # REQUIRED
DB_TIMEOUT = int(os.environ.get("DB_TIMEOUT", "1800"))
AUTH_METHOD = os.environ.get("AUTH_METHOD", "active_directory_interactive")

# Service principal (AUTH_METHOD=service_principal)
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")

# SQL auth (AUTH_METHOD=sql_auth)
AZURE_SQL_AUTH_USERNAME = os.environ.get("AZURE_SQL_AUTH_USERNAME", "")
AZURE_SQL_AUTH_PASSWORD = os.environ.get("AZURE_SQL_AUTH_PASSWORD", "")
```

### Removed Config

- `DB_SERVER` — now inside connection string
- `DB_DATABASE` — now inside connection string
- `DB_DRIVER` — no longer needed (no ODBC driver)
- `AZURE_SQL_USERNAME` — deprecated auth removed
- `AZURE_SQL_PASSWORD` — deprecated auth removed

### `.env.example`

```
# Connection string (required)
AZURE_SQL_CONNECTIONSTRING=Server=your-server.database.windows.net;Database=your-database;Encrypt=yes;TrustServerCertificate=no;

# Auth method: active_directory_interactive | active_directory_default | sql_auth | service_principal
AUTH_METHOD=active_directory_interactive

# Timeout in seconds (default 1800 = 30 min)
DB_TIMEOUT=1800

# For sql_auth only:
AZURE_SQL_AUTH_USERNAME=
AZURE_SQL_AUTH_PASSWORD=

# For service_principal only:
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
```

### `pyproject.toml`

- Remove: `pyodbc`, `azure-identity`
- Add: `mssql-python`

---

## 5. Logging

Every log line answers **what**, **why**, and **what to do if it fails**.

### Success Path

```
INFO  - Auth method: active_directory_interactive (set via AUTH_METHOD env var)
INFO  - Connection string: Server=myserver.database.windows.net;Database=mydb;Encrypt=yes;...;Authentication=ActiveDirectoryInteractive (PWD=***)
INFO  - Connecting to database... (this may open a browser window for MFA)
INFO  - Database connection established successfully
INFO  - Loading SQL template from db/SQL_Query.sql
INFO  - Executing query for months [1, 2, 3], year 2026...
INFO  - Query complete: 1542 rows, 14 columns in 487.3s
INFO  - Database connection closed
```

### Error Path

```
ERROR - Database connection failed using auth method 'active_directory_interactive'
ERROR - Error: [OperationalError] Login failed for user 'someone@company.com'
ERROR - Suggestions: 1) Check your Azure permissions 2) Run 'az login' and try AUTH_METHOD=active_directory_default 3) Check IP whitelist in Azure portal

ERROR - Database query timed out after 1800s
ERROR - Suggestions: 1) Increase DB_TIMEOUT env var 2) Check if the query is running in Azure portal 3) Try fewer months at once
```

### Secret Masking

Connection strings logged with `PWD=***` — never log actual passwords or client secrets.

---

## 6. Testing Strategy

### Unit Tests (`tests/test_db_query.py`) — TDD-first, all mock `mssql_python.connect`

| Test Group | What It Covers |
|---|---|
| Connection string building | Each auth method appends correct params; default is `active_directory_interactive` |
| Config validation | Missing `AZURE_SQL_CONNECTIONSTRING` raises `ValueError`; missing `UID`/`PWD` for `sql_auth` raises; missing client credentials for `service_principal` raises; unsupported auth method raises |
| Timeout | `conn.timeout` set to `DB_TIMEOUT` value; default 1800 |
| Query execution | SQL template loaded, date ranges injected, results converted to list of dicts |
| Multi-result-set | `cursor.nextset()` iteration works correctly |
| Date range SQL | Single month, multiple months, December wraparound |
| Error mapping | `OperationalError` HYT00 → `TimeoutError`; other DB errors → `ConnectionError` |
| Logging output | Auth method logged, secrets masked in connection string logs, timing logged |
| Connection cleanup | Connection closed even on error (context manager) |

### Live Integration Tests (`tests/db_auth/`) — `@pytest.mark.live`

Each live test follows the same pattern:
1. Build connection string with that auth method
2. Connect
3. Run verification query: `SELECT s.id FROM store AS s WHERE s.active = 1;`
4. Assert rows returned (at least one active store)
5. Close connection

| File | Auth Method |
|---|---|
| `test_sql_auth.py` | SQL username/password |
| `test_service_principal.py` | Client ID/secret |
| `test_active_directory_interactive.py` | Browser MFA popup |
| `test_active_directory_default.py` | `az login` cached credential |

### Network Tests (`tests/db_auth/test_network.py`) — `@pytest.mark.live`

| Test | What It Checks | Failure Message |
|---|---|---|
| TCP reachability | Socket connect to server:1433 | "Is your VPN on? Is your IP whitelisted in Azure firewall?" |
| DNS resolution | Server hostname resolves | "Is the server name correct in AZURE_SQL_CONNECTIONSTRING?" |
| TLS handshake | SSL connection succeeds | "Check certificate/encryption settings" |

### Deleted Tests

- `test_azure_ad_interactive.py` — old Windows-only method removed
- `test_azure_ad_password.py` — deprecated method removed
- `test_driver_and_network.py` — ODBC driver checks no longer relevant
- `diagnose_db_auth.py` — no longer needed

---

## 7. `app.py` Changes

Minimal — same public API (`execute_query`), same error handling.

- Import stays: `from db.query import execute_query`
- Auth method display in Gradio UI stays (reads `config.AUTH_METHOD`)
- No changes to report generation, Drive upload, or rollback logic

---

## 8. Files Changed

| File | Action | Complexity |
|---|---|---|
| `db/query.py` | Rewrite | High — auth logic, connection, error handling |
| `config.py` | Simplify | Low — remove old vars, add connection string |
| `.env.example` | Rewrite | Low — new format |
| `pyproject.toml` | Update deps | Low — swap pyodbc/azure-identity for mssql-python |
| `uv.lock` | Regenerate | Auto — `uv lock` |
| `tests/test_db_query.py` | Rewrite | High — all mocks change to mssql-python |
| `tests/conftest.py` | Update | Low — fixtures for new config shape |
| `tests/db_auth/test_sql_auth.py` | Rewrite | Medium — new driver API |
| `tests/db_auth/test_service_principal.py` | Rewrite | Medium — new driver API |
| `tests/db_auth/test_active_directory_interactive.py` | New | Medium — new auth method |
| `tests/db_auth/test_active_directory_default.py` | New | Medium — new auth method |
| `tests/db_auth/test_network.py` | Rewrite | Low — remove ODBC checks |
| `tests/db_auth/test_azure_ad_interactive.py` | Delete | — |
| `tests/db_auth/test_azure_ad_password.py` | Delete | — |
| `tests/db_auth/test_driver_and_network.py` | Delete | — |
| `tests/db_auth/diagnose_db_auth.py` | Delete | — |
| `tests/test_db_connection.py` | Delete | — (ODBC smoke test) |
| `tests/test_drive_connection.py` | Review | Low — check for DB references |
| `app.py` | Minor update | Low — log message tweaks if needed |
| `README.md` | Update | Low — installation, config, auth docs |

---

## 9. Task Assignment

**Opus (complex tasks):**
- Rewrite `db/query.py` — auth logic, connection string building, error handling, logging
- Rewrite `tests/test_db_query.py` — all unit tests TDD-first

**Sonnet (well-explained smaller tasks):**
- Update `config.py` — remove old vars, add new ones
- Update `.env.example` — new format
- Update `pyproject.toml` — swap dependencies
- Rewrite live integration tests in `tests/db_auth/`
- Rewrite `tests/db_auth/test_network.py`
- Delete old files
- Update `tests/conftest.py`
- Update `app.py` if needed
- Update `README.md`
