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
