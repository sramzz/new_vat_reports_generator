import json
import os


def load_last_run(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_last_run(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def add_file_entry(path: str, file_id: str, store_id: int | None, store_name: str | None, file_type: str) -> None:
    data = load_last_run(path)
    if data is None:
        return
    data["files"].append({"file_id": file_id, "store_id": store_id, "store_name": store_name, "type": file_type})
    save_last_run(path, data)


def remove_store_entries(path: str, store_ids: list[int]) -> list[str]:
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
    return removed_ids


def clear_last_run(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
