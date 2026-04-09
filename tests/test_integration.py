import json
import os
from datetime import date, datetime
import openpyxl
import pytest

from reports.split import filter_by_store, filter_by_month
from reports.excel import generate_store_report, generate_raw_backup
from reports.summary import generate_summary
from drive.mapping import load_mapping, get_folder_id, add_store
from data.last_run_manager import load_last_run, save_last_run, add_file_entry, clear_last_run, remove_store_entries

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), "r") as f:
        return json.load(f)


def _parse_dates(rows):
    for row in rows:
        if isinstance(row["CreatedOn"], str):
            row["CreatedOn"] = date.fromisoformat(row["CreatedOn"])
    return rows


def test_full_monthly_flow(tmp_path):
    all_rows = _parse_dates(_load_fixture("sample_query_result.json"))
    jan_rows = [r for r in all_rows if r["CreatedOn"].month == 1]
    by_store = filter_by_store(jan_rows)
    assert len(by_store) == 4

    store_results = []
    for store_id, store_rows in by_store.items():
        store_name = store_rows[0]["RegisterName"]
        path = generate_store_report(store_rows, "January 2026", store_name, str(tmp_path))
        assert os.path.exists(path)
        store_results.append({"store_id": store_id, "store_name": store_name, "report_url": f"https://drive.google.com/file/d/fake-{store_id}/view"})

    raw_path = generate_raw_backup(jan_rows, "January 2026", str(tmp_path))
    assert os.path.exists(raw_path)

    summary_path = generate_summary(store_results, "January 2026", str(tmp_path))
    assert os.path.exists(summary_path)
    assert len(store_results) == 4


def test_full_quarterly_flow(tmp_path):
    all_rows = _parse_dates(_load_fixture("sample_query_result.json"))
    by_store = filter_by_store(all_rows)

    for store_id, store_rows in by_store.items():
        store_name = store_rows[0]["RegisterName"]
        path = generate_store_report(store_rows, "Q1 - March 2026", store_name, str(tmp_path))
        wb = openpyxl.load_workbook(path)
        months_in_data = len(filter_by_month(store_rows))
        assert len(wb.sheetnames) == months_in_data


def test_new_store_detection_flow(tmp_path):
    all_rows = _parse_dates(_load_fixture("sample_query_result.json"))
    mapping_path = str(tmp_path / "store_mapping.json")
    mapping_data = _load_fixture("sample_store_mapping.json")
    with open(mapping_path, "w") as f:
        json.dump(mapping_data, f)

    mapping = load_mapping(mapping_path)
    by_store = filter_by_store(all_rows)

    new_stores = []
    for store_id in by_store:
        if get_folder_id(mapping, store_id) is None:
            store_name = by_store[store_id][0]["RegisterName"]
            add_store(mapping, mapping_path, store_id, store_name, store_name, f"fake-new-{store_id}")
            new_stores.append(store_name)

    assert len(new_stores) == 1
    assert new_stores[0] == "Belchicken NewStore"
    reloaded = load_mapping(mapping_path)
    assert get_folder_id(reloaded, 999) == "fake-new-999"


def test_partial_upload_failure_tracks_only_successes(tmp_path):
    last_run_path = str(tmp_path / "last_run.json")
    save_last_run(last_run_path, {"report_name": "Q1", "created_at": datetime.now().isoformat(), "files": []})

    for store_id, name, fid in [(100, "Aalst", "f-100"), (200, "Brugge", "f-200"), (300, "Leuven", "f-300")]:
        add_file_entry(last_run_path, fid, store_id, name, "report")

    loaded = load_last_run(last_run_path)
    assert len(loaded["files"]) == 3
    assert all(f["store_id"] != 999 for f in loaded["files"])


def test_rollback_flow(tmp_path):
    last_run_path = str(tmp_path / "last_run.json")
    save_last_run(last_run_path, _load_fixture("sample_last_run.json"))
    loaded = load_last_run(last_run_path)
    assert len(loaded["files"]) == 5
    clear_last_run(last_run_path)
    assert load_last_run(last_run_path) is None


def test_rollback_specific_stores(tmp_path):
    last_run_path = str(tmp_path / "last_run.json")
    save_last_run(last_run_path, _load_fixture("sample_last_run.json"))
    removed = remove_store_entries(last_run_path, store_ids=[100])
    assert removed == ["fake-file-id-aalst"]
    loaded = load_last_run(last_run_path)
    assert len(loaded["files"]) == 4
    assert all(f["store_id"] != 100 for f in loaded["files"])


def test_dry_run_generates_local_files_only(tmp_path):
    all_rows = _parse_dates(_load_fixture("sample_query_result.json"))
    jan_rows = [r for r in all_rows if r["CreatedOn"].month == 1]
    by_store = filter_by_store(jan_rows)

    generated_files = []
    for store_id, store_rows in by_store.items():
        store_name = store_rows[0]["RegisterName"]
        path = generate_store_report(store_rows, "January 2026", store_name, str(tmp_path))
        generated_files.append(path)

    assert len(generated_files) == 4
    assert all(os.path.exists(f) for f in generated_files)
    assert not os.path.exists(str(tmp_path / "last_run.json"))
