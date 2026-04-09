import json
import pytest
from drive.mapping import load_mapping, get_folder_id, add_store, get_all_stores


@pytest.fixture
def mapping_file(tmp_path):
    data = {
        "stores": [
            {
                "storeId": 100,
                "storeName": "Belchicken Aalst",
                "folderName": "Belchicken Aalst",
                "gdriveId": "fake-gdrive-id-aalst"
            },
            {
                "storeId": 200,
                "storeName": "Belchicken Brugge",
                "folderName": "Belchicken Brugge",
                "gdriveId": "fake-gdrive-id-brugge"
            }
        ]
    }
    path = tmp_path / "store_mapping.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_get_folder_id_returns_id_for_known_store(mapping_file):
    mapping = load_mapping(mapping_file)
    result = get_folder_id(mapping, 100)
    assert result == "fake-gdrive-id-aalst"


def test_get_folder_id_returns_none_for_unknown_store(mapping_file):
    mapping = load_mapping(mapping_file)
    result = get_folder_id(mapping, 999)
    assert result is None


def test_add_store_persists_to_file(mapping_file):
    mapping = load_mapping(mapping_file)
    add_store(mapping, mapping_file, store_id=999, store_name="Belchicken NewStore", folder_name="Belchicken NewStore", gdrive_id="new-gdrive-id")
    reloaded = load_mapping(mapping_file)
    assert get_folder_id(reloaded, 999) == "new-gdrive-id"


def test_add_store_includes_all_fields(mapping_file):
    mapping = load_mapping(mapping_file)
    add_store(mapping, mapping_file, store_id=999, store_name="Belchicken NewStore", folder_name="Belchicken NewStore", gdrive_id="new-gdrive-id")
    reloaded = load_mapping(mapping_file)
    store = next(s for s in reloaded["stores"] if s["storeId"] == 999)
    assert store["storeName"] == "Belchicken NewStore"
    assert store["folderName"] == "Belchicken NewStore"
    assert store["gdriveId"] == "new-gdrive-id"


def test_get_all_stores_returns_full_mapping(mapping_file):
    mapping = load_mapping(mapping_file)
    stores = get_all_stores(mapping)
    assert len(stores) == 2
    assert stores[0]["storeId"] == 100
    assert stores[1]["storeId"] == 200
