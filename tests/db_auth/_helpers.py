import platform
import re
import socket
import ssl
import time

from mssql_python import connect

VERIFICATION_QUERY = "SELECT s.id FROM store AS s WHERE s.active = 1;"


def load_config():
    import config

    return config


def platform_name() -> str:
    return platform.system()


def has_connection_string() -> bool:
    try:
        cfg = load_config()
        return bool(cfg.AZURE_SQL_CONNECTIONSTRING)
    except Exception:
        return False


def has_sql_auth() -> bool:
    try:
        cfg = load_config()
        return bool(cfg.AZURE_SQL_AUTH_USERNAME and cfg.AZURE_SQL_AUTH_PASSWORD)
    except Exception:
        return False


def has_service_principal() -> bool:
    try:
        cfg = load_config()
        return bool(cfg.AZURE_CLIENT_ID and cfg.AZURE_CLIENT_SECRET)
    except Exception:
        return False


def extract_server_host(connection_string: str) -> str:
    """Extract the hostname from a connection string like Server=host.database.windows.net;..."""
    match = re.search(r"Server=([^;,]+)", connection_string, re.IGNORECASE)
    if not match:
        raise ValueError(f"Cannot extract Server from connection string: {connection_string}")
    return match.group(1).replace("tcp:", "")


def print_preflight(cfg, auth_label: str, username: str = ""):
    print("\n  Preflight:")
    print(f"    Platform:    {platform_name()}")
    print(f"    Conn String: {cfg.AZURE_SQL_CONNECTIONSTRING[:60]}...")
    print(f"    Auth:        {auth_label}")
    if username:
        print(f"    Username:    {username}")


def build_connection_string(cfg, auth_method: str) -> str:
    """Build a full connection string for the given auth method, for live tests."""
    base = cfg.AZURE_SQL_CONNECTIONSTRING

    if auth_method == "active_directory_interactive":
        return base + "Authentication=ActiveDirectoryInteractive;"

    if auth_method == "active_directory_default":
        return base + "Authentication=ActiveDirectoryDefault;"

    if auth_method == "sql_auth":
        return base + f"UID={cfg.AZURE_SQL_AUTH_USERNAME};PWD={cfg.AZURE_SQL_AUTH_PASSWORD};"

    if auth_method == "service_principal":
        return base + (
            "Authentication=ActiveDirectoryServicePrincipal;"
            f"UID={cfg.AZURE_CLIENT_ID};"
            f"PWD={cfg.AZURE_CLIENT_SECRET};"
        )

    raise ValueError(f"Unknown auth method: {auth_method}")


def connect_and_verify(conn_str: str, timeout: int = 30):
    """Connect using mssql-python and run the verification query."""
    print("  Connecting...")
    start = time.time()
    conn = connect(conn_str)
    conn.timeout = timeout
    elapsed = time.time() - start
    print(f"  Connected in {elapsed:.1f}s")

    try:
        cursor = conn.cursor()
        print(f"  Running: {VERIFICATION_QUERY}")
        cursor.execute(VERIFICATION_QUERY)
        rows = cursor.fetchall()
    finally:
        conn.close()

    print(f"  Got {len(rows)} active stores")
    for row in rows[:5]:
        print(f"    ID: {row[0]}")
    if len(rows) > 5:
        print(f"    ... and {len(rows) - 5} more")

    assert len(rows) > 0, "Expected at least 1 active store"
    return rows


def resolve_server_addresses(server_host: str) -> list[str]:
    infos = socket.getaddrinfo(server_host, 1433, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def probe_tcp_port(server_host: str, port: int = 1433, timeout: float = 5.0) -> float:
    start = time.time()
    with socket.create_connection((server_host, port), timeout=timeout):
        return time.time() - start


def probe_tls(server_host: str, port: int = 1433, timeout: float = 5.0) -> str:
    """Attempt a TLS handshake and return the server certificate subject."""
    context = ssl.create_default_context()
    with socket.create_connection((server_host, port), timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=server_host) as ssock:
            cert = ssock.getpeercert()
            subject = dict(x[0] for x in cert.get("subject", ()))
            return subject.get("commonName", str(cert.get("subject", "unknown")))
