import calendar
from collections import defaultdict


def filter_by_store(rows: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        result[row["StoreId"]].append(row)
    return dict(result)


def filter_by_month(rows: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        month_name = calendar.month_name[row["CreatedOn"].month]
        result[month_name].append(row)
    return dict(result)
