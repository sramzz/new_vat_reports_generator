import json
import logging
import os

logger = logging.getLogger("vat_reports")


def load_last_run(path: str) -> dict | None:
    if not os.path.exists(path):
        logger.info(f"No last_run file at {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"Loaded last_run: {data.get('report_name', '?')}, {len(data.get('files', []))} files")
    return data


def save_last_run(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info(f"Saved last_run to {path}")


def add_file_entry(path: str, file_id: str, store_id: int | None, store_name: str | None, file_type: str) -> None:
    data = load_last_run(path)
    if data is None:
        return
    data["files"].append({"file_id": file_id, "store_id": store_id, "store_name": store_name, "type": file_type})
    save_last_run(path, data)
    logger.info(f"Added file entry: {file_type} {file_id} (store: {store_name})")


def remove_store_entries(path: str, store_ids: list[int]) -> list[str]:
    logger.info(f"Removing store entries for store IDs: {store_ids}")
    data = load_last_run(path)
    if data is None:
        return []
    removed_ids = []
    remaining = []
    for f in data["files"]:
        if f["store_id"] in store_ids:
            removed_ids.append(f["file_id"])
        else:
            remaining.append(f)
    data["files"] = remaining
    save_last_run(path, data)
    logger.info(f"Removed {len(removed_ids)} file entries")
    return removed_ids


def clear_last_run(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
        logger.info(f"Cleared last_run file: {path}")
