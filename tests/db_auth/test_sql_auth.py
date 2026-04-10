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
