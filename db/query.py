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
    "active_directory_default",
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

    if auth == "active_directory_default":
        return base + "Authentication=ActiveDirectoryDefault;"

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
    elif auth == "active_directory_default":
        logger.info("Connecting to database... (using cached az login credential)")
    else:
        logger.info("Connecting to database...")

    conn = connect(conn_str)
    conn.timeout = config.DB_TIMEOUT
    logger.info("Database connection established successfully")
    return conn


def execute_query(months: list[int], year: int) -> list[dict]:
    logger.info(f"execute_query called: months={months}, year={year}")
    logger.info(f"Using auth method: {config.AUTH_METHOD}")

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
            "2) Run 'az login' and try AUTH_METHOD=active_directory_default "
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
