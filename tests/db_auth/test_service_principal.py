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
