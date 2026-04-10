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
