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

    def test_active_directory_default(self):
        with patch("db.query.config") as mock_config:
            mock_config.AZURE_SQL_CONNECTIONSTRING = BASE_CONN_STR
            mock_config.AUTH_METHOD = "active_directory_default"
            result = _build_connection_string()
        assert "Authentication=ActiveDirectoryDefault;" in result

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
            mock_config.AUTH_METHOD = "active_directory_interactive"
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
            mock_config.AUTH_METHOD = "sql_auth"
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
            mock_config.SQL_TEMPLATE_PATH = "db/SQL_Query.sql"
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
