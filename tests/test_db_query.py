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


def test_query_handles_non_timeout_db_error():
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = pyodbc.Error("42000", "[42000] Syntax error")
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
         patch("db.query._connect", return_value=mock_conn):
        with pytest.raises(ConnectionError, match="Database query failed"):
            execute_query([1], 2026)


def test_query_iterates_through_multiple_resultsets():
    """Covers the while cursor.nextset(): pass loop body when nextset returns True."""
    mock_cursor = MagicMock()
    mock_cursor.description = [(col, None, None, None, None, None, None) for col in EXPECTED_COLUMNS]
    mock_cursor.fetchall.return_value = []
    # nextset returns True once (loop body executes), then False to stop
    mock_cursor.nextset.side_effect = [True, False]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("db.query._read_sql_template", return_value=SQL_TEMPLATE), \
         patch("db.query._connect", return_value=mock_conn):
        result = execute_query([1], 2026)
    assert result == []


def test_read_sql_template_reads_file(tmp_path):
    from db.query import _read_sql_template
    import config

    sql_content = "SELECT 1;"
    sql_file = tmp_path / "test_template.sql"
    sql_file.write_text(sql_content, encoding="utf-8")

    with patch.object(config, "SQL_TEMPLATE_PATH", str(sql_file)):
        result = _read_sql_template()
    assert result == sql_content


def test_connect_uses_config_values():
    from db.query import _connect
    import config

    mock_conn = MagicMock()
    with patch("db.query.pyodbc.connect", return_value=mock_conn) as mock_pyodbc_connect, \
         patch.object(config, "DB_DRIVER", "{ODBC Driver 18 for SQL Server}"), \
         patch.object(config, "DB_SERVER", "test-server"), \
         patch.object(config, "DB_DATABASE", "test-db"), \
         patch.object(config, "DB_TIMEOUT", 30):
        result = _connect()

    assert result is mock_conn
    call_args = mock_pyodbc_connect.call_args
    conn_str = call_args[0][0]
    assert "test-server" in conn_str
    assert "test-db" in conn_str
