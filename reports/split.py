import calendar
import logging
from collections import defaultdict

logger = logging.getLogger("vat_reports")


def filter_by_store(rows: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        result[row["StoreId"]].append(row)
    logger.info(f"Split {len(rows)} rows into {len(result)} stores")
    return dict(result)


def filter_rows_by_store_ids(rows: list[dict], store_ids: list[int | str] | None) -> list[dict]:
    if store_ids is None:
        return rows
    selected = {int(store_id) for store_id in store_ids}
    filtered = [row for row in rows if int(row["StoreId"]) in selected]
    logger.info(f"Filtered {len(rows)} rows to {len(filtered)} rows for {len(selected)} selected stores")
    return filtered


def filter_by_month(rows: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        month_name = calendar.month_name[row["CreatedOn"].month]
        result[month_name].append(row)
    logger.info(f"Split {len(rows)} rows into {len(result)} months: {list(result.keys())}")
    return dict(result)
