import re
import pyodbc

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
    import config
    with open(config.SQL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _connect() -> pyodbc.Connection:
    import config
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
        while cursor.nextset():
            pass
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except pyodbc.Error as e:
        error_code = getattr(e, "args", [""])[0] if e.args else ""
        if "HYT00" in str(error_code) or "timeout" in str(e).lower():
            raise TimeoutError(f"Database query timed out: {e}") from e
        raise ConnectionError(f"Database query failed: {e}") from e
    finally:
        conn.close()
