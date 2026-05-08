from datetime import datetime

from data.store_cache import load_store_cache, save_store_cache


def test_save_and_load_store_cache_round_trips_stores(tmp_path):
    path = tmp_path / "stores_cache.json"
    stores = [
        {"id": 217, "name": "Belchicken Aalst"},
        {"id": "218", "name": "Belchicken Ruisbroek"},
    ]

    save_store_cache(str(path), stores)
    result = load_store_cache(str(path))

    assert datetime.fromisoformat(result["updated_at"])
    assert result["stores"] == [
        {"id": 217, "name": "Belchicken Aalst"},
        {"id": 218, "name": "Belchicken Ruisbroek"},
    ]


def test_load_store_cache_returns_empty_cache_when_file_missing(tmp_path):
    result = load_store_cache(str(tmp_path / "missing.json"))

    assert result == {"updated_at": None, "stores": []}
