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
def test_active_directory_default(cfg):
    """Connect using Entra ID default credential (cached az login) and verify with active stores query.

    Prerequisites: Run 'az login' before this test. The driver will use the cached credential.
    """
    print_preflight(cfg, "ActiveDirectoryDefault (cached az login)")
    print("  >> Using cached credential from 'az login'...")
    conn_str = build_connection_string(cfg, "active_directory_default")
    connect_and_verify(conn_str, timeout=min(cfg.DB_TIMEOUT, 30))
