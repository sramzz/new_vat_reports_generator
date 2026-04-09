from datetime import date
from reports.split import filter_by_store, filter_by_month


def _make_rows():
    return [
        {"CreatedOn": date(2026, 1, 2), "StoreId": 100, "RegisterName": "Store A", "6%": 500},
        {"CreatedOn": date(2026, 1, 3), "StoreId": 100, "RegisterName": "Store A", "6%": 600},
        {"CreatedOn": date(2026, 2, 1), "StoreId": 100, "RegisterName": "Store A", "6%": 700},
        {"CreatedOn": date(2026, 1, 2), "StoreId": 200, "RegisterName": "Store B", "6%": 1200},
        {"CreatedOn": date(2026, 2, 1), "StoreId": 200, "RegisterName": "Store B", "6%": 1100},
        {"CreatedOn": date(2026, 3, 1), "StoreId": 200, "RegisterName": "Store B", "6%": 1400},
        {"CreatedOn": date(2026, 1, 5), "StoreId": 300, "RegisterName": "Store C", "6%": 800},
    ]


def test_filter_by_store_returns_correct_groups():
    rows = _make_rows()
    result = filter_by_store(rows)
    assert set(result.keys()) == {100, 200, 300}
    assert len(result[100]) == 3
    assert len(result[200]) == 3
    assert len(result[300]) == 1


def test_filter_by_store_preserves_all_rows():
    rows = _make_rows()
    result = filter_by_store(rows)
    total = sum(len(store_rows) for store_rows in result.values())
    assert total == len(rows)


def test_filter_by_store_single_store():
    rows = [{"CreatedOn": date(2026, 1, 2), "StoreId": 100, "RegisterName": "A", "6%": 500}]
    result = filter_by_store(rows)
    assert set(result.keys()) == {100}
    assert len(result[100]) == 1


def test_filter_by_store_empty_input():
    result = filter_by_store([])
    assert result == {}


def test_filter_by_month_returns_correct_groups():
    rows = [
        {"CreatedOn": date(2026, 1, 2), "StoreId": 100, "RegisterName": "A", "6%": 500},
        {"CreatedOn": date(2026, 1, 3), "StoreId": 100, "RegisterName": "A", "6%": 600},
        {"CreatedOn": date(2026, 2, 1), "StoreId": 100, "RegisterName": "A", "6%": 700},
        {"CreatedOn": date(2026, 3, 1), "StoreId": 100, "RegisterName": "A", "6%": 900},
    ]
    result = filter_by_month(rows)
    assert set(result.keys()) == {"January", "February", "March"}
    assert len(result["January"]) == 2
    assert len(result["February"]) == 1
    assert len(result["March"]) == 1


def test_filter_by_month_single_month():
    rows = [
        {"CreatedOn": date(2026, 3, 1), "StoreId": 100, "RegisterName": "A", "6%": 900},
        {"CreatedOn": date(2026, 3, 5), "StoreId": 100, "RegisterName": "A", "6%": 800},
    ]
    result = filter_by_month(rows)
    assert set(result.keys()) == {"March"}
    assert len(result["March"]) == 2


def test_filter_by_month_empty_input():
    result = filter_by_month([])
    assert result == {}
