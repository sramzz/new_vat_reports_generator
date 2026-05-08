import pytest

from tests.db_auth._helpers import has_connection_string, print_preflight

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not has_connection_string(),
    reason="AZURE_SQL_CONNECTIONSTRING not in .env",
)
def test_vat_query_returns_final_resultset(cfg):
    """Run the VAT SQL batch through execute_query against one store.

    This catches driver result-set handling regressions where row-count or
    non-row result sets leave cursor.description as None before the final SELECT.
    """
    from db.query import EXPECTED_COLUMNS, execute_query

    print_preflight(cfg, f"VAT query via {cfg.AUTH_METHOD}")
    print("  Running VAT query for store 266, April 2026...")

    rows = execute_query([4], 2026, store_ids=[266])

    print(f"  VAT query returned {len(rows)} rows")
    assert isinstance(rows, list)
    if rows:
        assert set(rows[0].keys()) == set(EXPECTED_COLUMNS)
