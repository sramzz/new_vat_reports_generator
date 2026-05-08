import json
import os
from datetime import datetime


def _normalize_stores(stores: list[dict]) -> list[dict]:
    normalized = []
    for store in stores:
        normalized.append({
            "id": int(store["id"]),
            "name": str(store["name"]),
        })
    return sorted(normalized, key=lambda item: item["name"].lower())


def load_store_cache(path: str) -> dict:
    if not os.path.exists(path):
        return {"updated_at": None, "stores": []}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "updated_at": data.get("updated_at"),
        "stores": _normalize_stores(data.get("stores", [])),
    }


def save_store_cache(path: str, stores: list[dict]) -> dict:
    data = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "stores": _normalize_stores(stores),
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return data
