import json
import pytest
from data.last_run_manager import load_last_run, save_last_run, add_file_entry, remove_store_entries, clear_last_run

@pytest.fixture
def last_run_file(tmp_path):
    return str(tmp_path / "last_run.json")

def test_load_returns_none_when_file_missing(last_run_file):
    result = load_last_run(last_run_file)
    assert result is None

def test_save_and_load_roundtrip(last_run_file):
    data = {"report_name": "Q1 - March 2026", "created_at": "2026-04-01T10:00:00", "files": []}
    save_last_run(last_run_file, data)
    loaded = load_last_run(last_run_file)
    assert loaded["report_name"] == "Q1 - March 2026"

def test_add_file_entry(last_run_file):
    data = {"report_name": "Q1", "created_at": "2026-04-01T10:00:00", "files": []}
    save_last_run(last_run_file, data)
    add_file_entry(last_run_file, file_id="abc", store_id=100, store_name="Aalst", file_type="report")
    loaded = load_last_run(last_run_file)
    assert len(loaded["files"]) == 1
    assert loaded["files"][0]["file_id"] == "abc"
    assert loaded["files"][0]["type"] == "report"

def test_remove_store_entries(last_run_file):
    data = {
        "report_name": "Q1", "created_at": "2026-04-01T10:00:00",
        "files": [
            {"file_id": "a", "store_id": 100, "store_name": "Aalst", "type": "report"},
            {"file_id": "b", "store_id": 200, "store_name": "Brugge", "type": "report"},
            {"file_id": "c", "store_id": None, "store_name": None, "type": "raw_backup"},
        ],
    }
    save_last_run(last_run_file, data)
    file_ids = remove_store_entries(last_run_file, store_ids=[100])
    assert file_ids == ["a"]
    loaded = load_last_run(last_run_file)
    assert len(loaded["files"]) == 2
    assert all(f["store_id"] != 100 for f in loaded["files"])

def test_clear_last_run(last_run_file):
    data = {"report_name": "Q1", "created_at": "2026-04-01T10:00:00", "files": [{"file_id": "a", "store_id": 100, "store_name": "Aalst", "type": "report"}]}
    save_last_run(last_run_file, data)
    clear_last_run(last_run_file)
    assert load_last_run(last_run_file) is None
