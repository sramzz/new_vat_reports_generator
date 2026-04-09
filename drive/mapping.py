import json


def load_mapping(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_folder_id(mapping: dict, store_id: int) -> str | None:
    for store in mapping["stores"]:
        if store["storeId"] == store_id:
            return store["gdriveId"]
    return None


def add_store(
    mapping: dict,
    path: str,
    store_id: int,
    store_name: str,
    folder_name: str,
    gdrive_id: str,
) -> None:
    mapping["stores"].append({
        "storeId": store_id,
        "storeName": store_name,
        "folderName": folder_name,
        "gdriveId": gdrive_id,
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)


def get_all_stores(mapping: dict) -> list[dict]:
    return mapping["stores"]
