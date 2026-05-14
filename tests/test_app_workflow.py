from datetime import datetime
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import app as vat_app


def _store_choices():
    return ["217 - Belchicken Aalst", "218 - Belchicken Ruisbroek"]


def test_clear_session_values_reset_generate_tab():
    result = vat_app.clear_session_values(["217 - Belchicken Aalst", "218 - Belchicken Ruisbroek"])

    assert result[0] == ""
    assert result[1] == []
    assert result[2] == datetime.now().year
    assert result[3] is False
    assert result[4] is False
    assert result[5] == "Query database"
    assert result[6] is None
    assert result[7]["value"] == ["217 - Belchicken Aalst", "218 - Belchicken Ruisbroek"]
    assert "Ready" in result[8]
    assert result[9] == ""
    assert result[10] == ""
    assert result[11] == ""


def test_clear_session_values_does_not_clear_latest_dry_run_folder(tmp_path):
    vat_app._set_latest_dry_run_dir(str(tmp_path))

    vat_app.clear_session_values(["217 - Belchicken Aalst"])

    assert vat_app._get_latest_dry_run_dir() == str(tmp_path)


def test_refresh_stores_fetches_database_and_writes_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "stores_cache.json"
    monkeypatch.setattr(vat_app, "_get_config", lambda: SimpleNamespace(STORE_CACHE_PATH=str(cache_path)))

    with patch("db.query.fetch_stores", return_value=[{"id": 217, "name": "Belchicken Aalst"}]):
        status, update = vat_app.refresh_stores()

    assert "Refreshed 1 stores" in status
    assert update["choices"] == ["217 - Belchicken Aalst"]
    assert update["value"] == ["217 - Belchicken Aalst"]


def test_generate_reports_csv_mode_skips_database_query(monkeypatch, tmp_path):
    monkeypatch.setattr(vat_app, "_get_logger", lambda: logging.getLogger("vat_reports_test"))
    monkeypatch.setattr(vat_app.tempfile, "mkdtemp", lambda prefix: str(tmp_path))
    monkeypatch.setattr(
        vat_app,
        "_get_config",
        lambda: SimpleNamespace(
            STORE_MAPPING_PATH=vat_app.os.path.join(
                vat_app.os.path.dirname(__file__), "..", "data", "store_mapping.json"
            ),
            STORE_CACHE_PATH=str(tmp_path / "stores_cache.json"),
            LAST_RUN_PATH=str(tmp_path / "last_run.json"),
        ),
    )

    with patch("db.query.execute_query") as execute_query:
        outputs = list(vat_app.generate_reports(
            report_name="Q2 2026",
            months=["April", "May", "June"],
            year=2026,
            is_quarterly=True,
            dry_run=True,
            input_mode="Import CSV",
            csv_file="Examples_Reports/ Q1 VAT Raw Report 2026 _ BC BE.csv",
            selected_stores=["266 - Belchicken A12 Drive"],
        ))

    execute_query.assert_not_called()
    final_status, final_log, final_results, final_errors = outputs[-1]
    assert "DRY RUN" in final_status
    assert "Loaded" in final_log
    assert "Belchicken A12 Drive" in final_results
    assert final_errors == ""


def test_toggle_store_selection_selects_all_cached_stores(monkeypatch):
    monkeypatch.setattr(vat_app, "load_cached_store_choices", _store_choices)

    update = vat_app.toggle_store_selection(["217 - Belchicken Aalst"])

    assert update["value"] == _store_choices()


def test_toggle_store_selection_clears_when_all_cached_stores_selected(monkeypatch):
    monkeypatch.setattr(vat_app, "load_cached_store_choices", _store_choices)

    update = vat_app.toggle_store_selection(_store_choices())

    assert update["value"] == []


def test_check_query_status_reports_running_and_idle():
    vat_app._clear_query_status()

    assert vat_app.check_query_status() == "No query is currently running."

    vat_app._set_query_status("Q2 2026", "Query database")
    running = vat_app.check_query_status()
    vat_app._clear_query_status()

    assert "Query is running" in running
    assert "Q2 2026" in running
    assert "Query database" in running
    assert "Started:" in running
    assert vat_app.check_query_status() == "No query is currently running."


def test_generate_reports_live_upload_outputs_summary_url(monkeypatch, tmp_path):
    rows = [{"StoreId": 217, "RegisterName": "Belchicken Aalst"}]
    summary_url = "https://drive.google.com/file/d/summary/view"

    monkeypatch.setattr(vat_app, "_get_logger", lambda: logging.getLogger("vat_reports_test"))
    monkeypatch.setattr(vat_app.tempfile, "mkdtemp", lambda prefix: str(tmp_path))
    monkeypatch.setattr(
        vat_app,
        "_get_config",
        lambda: SimpleNamespace(
            STORE_MAPPING_PATH=str(tmp_path / "store_mapping.json"),
            STORE_CACHE_PATH=str(tmp_path / "stores_cache.json"),
            LAST_RUN_PATH=str(tmp_path / "last_run.json"),
            GDRIVE_RAW_REPORT_FOLDER_ID="raw-folder",
            GDRIVE_REPORTS_FOLDER_ID="reports-folder",
            GDRIVE_SUMMARY_FOLDER_ID="summary-folder",
        ),
    )

    def fake_upload_file(service, local_path, parent_folder_id):
        if parent_folder_id == "summary-folder":
            return "summary-file-id", summary_url
        return f"{parent_folder_id}-file-id", f"https://drive.google.com/file/d/{parent_folder_id}/view"

    with (
        patch("data.csv_import.parse_query_csv", return_value=rows),
        patch("drive.auth.get_drive_service", return_value=object()),
        patch("drive.upload.upload_file", side_effect=fake_upload_file),
        patch("drive.mapping.load_mapping", return_value={"stores": [{"storeId": 217, "gdriveId": "store-folder"}]}),
        patch("reports.excel.generate_raw_backup", return_value=str(tmp_path / "raw.xlsx")),
        patch("reports.excel.generate_store_report", return_value=str(tmp_path / "store.xlsx")),
        patch("reports.summary.generate_summary", return_value=str(tmp_path / "summary.xlsx")),
    ):
        outputs = list(vat_app.generate_reports(
            report_name="Q2 2026",
            months=["April", "May", "June"],
            year=2026,
            is_quarterly=True,
            dry_run=False,
            input_mode="Import CSV",
            csv_file="query.csv",
            selected_stores=[],
        ))

    final_status, final_log, final_results, final_errors = outputs[-1]
    assert f"[Open summary report]({summary_url})" in final_status
    assert f"[Open summary report]({summary_url})" in final_results
    assert f"Summary uploaded. Click here: {summary_url}" in final_log
    assert final_errors == ""


def test_generate_reports_dry_run_status_names_temp_output_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(vat_app, "_get_logger", lambda: logging.getLogger("vat_reports_test"))
    monkeypatch.setattr(vat_app.tempfile, "mkdtemp", lambda prefix: str(tmp_path))
    monkeypatch.setattr(
        vat_app,
        "_get_config",
        lambda: SimpleNamespace(
            STORE_MAPPING_PATH=vat_app.os.path.join(
                vat_app.os.path.dirname(__file__), "..", "data", "store_mapping.json"
            ),
            STORE_CACHE_PATH=str(tmp_path / "stores_cache.json"),
            LAST_RUN_PATH=str(tmp_path / "last_run.json"),
        ),
    )

    with patch("db.query.execute_query") as execute_query:
        outputs = list(vat_app.generate_reports(
            report_name="Q2 2026",
            months=["April", "May", "June"],
            year=2026,
            is_quarterly=True,
            dry_run=True,
            input_mode="Import CSV",
            csv_file="Examples_Reports/ Q1 VAT Raw Report 2026 _ BC BE.csv",
            selected_stores=["266 - Belchicken A12 Drive"],
        ))

    execute_query.assert_not_called()
    final_status = outputs[-1][0]
    assert f"Dry-run local files were generated here: `{tmp_path}`" in final_status
    assert f"[Open dry-run folder]({Path(tmp_path).as_uri()})" in final_status
    assert vat_app._get_latest_dry_run_dir() == str(tmp_path)
    manifest = vat_app._get_latest_dry_run_manifest()
    assert manifest["report_name"] == "Q2 2026"
    assert manifest["output_dir"] == str(tmp_path)
    assert manifest["raw_path"] == str(tmp_path / "Q2 2026 - VAT Raw Report.xlsx")
    assert manifest["summary_path"] == str(tmp_path / "Q2 2026 - VAT Summary Report.xlsx")
    assert manifest["stores"][0]["store_name"] == "Belchicken A12 Drive"
    assert manifest["stores"][0]["report_path"] == str(
        tmp_path / "Q2 2026 - VAT Accounting Report - Belchicken A12 Drive.xlsx"
    )


def test_open_last_dry_run_folder_reports_missing_folder(monkeypatch):
    vat_app._clear_latest_dry_run_dir()

    assert vat_app.open_last_dry_run_folder() == "No dry-run folder available yet."


def test_open_last_dry_run_folder_opens_latest_folder(monkeypatch, tmp_path):
    vat_app._set_latest_dry_run_dir(str(tmp_path))
    popen_calls = []
    monkeypatch.setattr(vat_app.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(vat_app.subprocess, "Popen", lambda args: popen_calls.append(args))

    result = vat_app.open_last_dry_run_folder()

    assert result == f"Opened dry-run folder: {tmp_path}"
    assert popen_calls == [["open", str(tmp_path)]]


def test_open_log_folder_uses_log_dir(monkeypatch, tmp_path):
    popen_calls = []
    monkeypatch.setattr(vat_app, "_get_config", lambda: SimpleNamespace(LOG_DIR=str(tmp_path / "logs")))
    monkeypatch.setattr(vat_app.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(vat_app.subprocess, "Popen", lambda args: popen_calls.append(args))

    result = vat_app.open_log_folder()

    assert result == "Log folder opened."
    assert popen_calls == [["open", str(tmp_path / "logs")]]


def test_upload_last_dry_run_requires_manifest():
    vat_app._clear_latest_dry_run_manifest()

    status, log, results, errors = vat_app.upload_last_dry_run_to_drive(confirm=False)

    assert status == "**No dry-run results available to upload.**"
    assert log == ""
    assert results == ""
    assert errors == ""


def test_upload_last_dry_run_requires_confirmation(monkeypatch, tmp_path):
    vat_app._set_latest_dry_run_manifest({
        "report_name": "Q2 2026",
        "output_dir": str(tmp_path),
        "raw_path": str(tmp_path / "raw.xlsx"),
        "summary_path": str(tmp_path / "summary.xlsx"),
        "stores": [],
    })

    with patch("drive.auth.get_drive_service") as get_drive_service:
        status, log, results, errors = vat_app.upload_last_dry_run_to_drive(confirm=False)

    get_drive_service.assert_not_called()
    assert status == "**Validation Error:** Check the confirmation box before uploading dry-run results."
    assert log == {"__type__": "update"}
    assert results == {"__type__": "update"}
    assert errors == {"__type__": "update"}


def test_upload_last_dry_run_uploads_manifest_and_updates_last_run(monkeypatch, tmp_path):
    raw_path = tmp_path / "raw.xlsx"
    store_path = tmp_path / "store.xlsx"
    summary_path = tmp_path / "summary.xlsx"
    for path in [raw_path, store_path, summary_path]:
        path.write_text("xlsx", encoding="utf-8")
    last_run_path = tmp_path / "last_run.json"
    mapping_path = tmp_path / "store_mapping.json"
    mapping_path.write_text(json.dumps({"stores": [{"storeId": 217, "gdriveId": "store-folder"}]}), encoding="utf-8")
    summary_url = "https://drive.google.com/file/d/summary/view"

    vat_app._set_latest_dry_run_manifest({
        "report_name": "Q2 2026",
        "output_dir": str(tmp_path),
        "raw_path": str(raw_path),
        "summary_path": str(summary_path),
        "stores": [
            {
                "store_id": 217,
                "store_name": "Belchicken Aalst",
                "report_path": str(store_path),
                "folder_id": "store-folder",
                "is_new_store": False,
            }
        ],
    })
    monkeypatch.setattr(vat_app, "_get_logger", lambda: logging.getLogger("vat_reports_test"))
    monkeypatch.setattr(
        vat_app,
        "_get_config",
        lambda: SimpleNamespace(
            STORE_MAPPING_PATH=str(tmp_path / "store_mapping.json"),
            LAST_RUN_PATH=str(last_run_path),
            GDRIVE_RAW_REPORT_FOLDER_ID="raw-folder",
            GDRIVE_REPORTS_FOLDER_ID="reports-folder",
            GDRIVE_SUMMARY_FOLDER_ID="summary-folder",
        ),
    )

    uploaded = []

    def fake_upload_file(service, local_path, parent_folder_id):
        uploaded.append((local_path, parent_folder_id))
        if parent_folder_id == "summary-folder":
            return "summary-id", summary_url
        if parent_folder_id == "raw-folder":
            return "raw-id", "https://drive.google.com/file/d/raw/view"
        return "store-id", "https://drive.google.com/file/d/store/view"

    with (
        patch("drive.auth.get_drive_service", return_value=object()),
        patch("drive.upload.upload_file", side_effect=fake_upload_file),
        patch("reports.summary.generate_summary", return_value=str(summary_path)) as generate_summary,
    ):
        status, log, results, errors = vat_app.upload_last_dry_run_to_drive(confirm=True)

    assert uploaded == [
        (str(raw_path), "raw-folder"),
        (str(store_path), "store-folder"),
        (str(summary_path), "summary-folder"),
    ]
    generate_summary.assert_called_once()
    assert f"[Open summary report]({summary_url})" in status
    assert "https://drive.google.com/file/d/store/view" in results
    assert f"Summary uploaded. Click here: {summary_url}" in log
    assert errors == ""
    last_run = json.loads(last_run_path.read_text(encoding="utf-8"))
    assert [entry["type"] for entry in last_run["files"]] == ["raw_backup", "report", "summary"]


def test_upload_last_dry_run_creates_new_store_folder_and_updates_mapping(monkeypatch, tmp_path):
    raw_path = tmp_path / "raw.xlsx"
    store_path = tmp_path / "store.xlsx"
    summary_path = tmp_path / "summary.xlsx"
    mapping_path = tmp_path / "store_mapping.json"
    mapping_path.write_text(json.dumps({"stores": []}), encoding="utf-8")
    for path in [raw_path, store_path, summary_path]:
        path.write_text("xlsx", encoding="utf-8")

    vat_app._set_latest_dry_run_manifest({
        "report_name": "Q2 2026",
        "output_dir": str(tmp_path),
        "raw_path": str(raw_path),
        "summary_path": str(summary_path),
        "stores": [
            {
                "store_id": 999,
                "store_name": "Belchicken New",
                "report_path": str(store_path),
                "folder_id": None,
                "is_new_store": True,
            }
        ],
    })
    monkeypatch.setattr(vat_app, "_get_logger", lambda: logging.getLogger("vat_reports_test"))
    monkeypatch.setattr(
        vat_app,
        "_get_config",
        lambda: SimpleNamespace(
            STORE_MAPPING_PATH=str(mapping_path),
            LAST_RUN_PATH=str(tmp_path / "last_run.json"),
            GDRIVE_RAW_REPORT_FOLDER_ID="raw-folder",
            GDRIVE_REPORTS_FOLDER_ID="reports-folder",
            GDRIVE_SUMMARY_FOLDER_ID="summary-folder",
        ),
    )

    with (
        patch("drive.auth.get_drive_service", return_value=object()),
        patch("drive.upload.upload_file", return_value=("file-id", "https://drive.google.com/file/d/file/view")),
        patch("drive.upload.create_folder", return_value="new-folder") as create_folder,
        patch("reports.summary.generate_summary", return_value=str(summary_path)),
    ):
        status, log, results, errors = vat_app.upload_last_dry_run_to_drive(confirm=True)

    create_folder.assert_called_once_with(ANY, "Belchicken New", "reports-folder")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert mapping["stores"][0]["storeId"] == 999
    assert mapping["stores"][0]["gdriveId"] == "new-folder"
    assert "Uploaded to Google Drive" in status
    assert errors == ""


def test_rollback_all_requires_confirmation(monkeypatch):
    with patch("drive.auth.get_drive_service") as get_drive_service:
        outputs = list(vat_app.rollback_all(confirm=False))

    get_drive_service.assert_not_called()
    assert outputs == ["Please check the confirmation box before deleting."]


def test_rollback_all_yields_started_progress_and_final_messages(monkeypatch, tmp_path):
    last_run_path = tmp_path / "last_run.json"
    last_run_path.write_text(
        json.dumps({
            "report_name": "Q2 2026",
            "created_at": "2026-05-13T10:00:00",
            "files": [
                {"file_id": "raw-id", "store_id": None, "store_name": None, "type": "raw_backup"},
                {"file_id": "store-id", "store_id": 217, "store_name": "Belchicken Aalst", "type": "report"},
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(vat_app, "_get_logger", lambda: logging.getLogger("vat_reports_test"))
    monkeypatch.setattr(vat_app, "_get_config", lambda: SimpleNamespace(LAST_RUN_PATH=str(last_run_path)))

    service = MagicMock()
    service.files().delete().execute.return_value = None

    with patch("drive.auth.get_drive_service", return_value=service):
        outputs = list(vat_app.rollback_all(confirm=True))

    assert outputs[0] == "**Rollback started.** Preparing to delete files from the last run..."
    assert "Deleting 1 of 2 files..." in outputs[2]
    assert "Deleting 2 of 2 files..." in outputs[3]
    assert outputs[-1] == "**Deleted:** 2/2 files."
    assert not last_run_path.exists()


def test_rollback_specific_yields_started_progress_and_final_messages(monkeypatch, tmp_path):
    last_run_path = tmp_path / "last_run.json"
    last_run_path.write_text(
        json.dumps({
            "report_name": "Q2 2026",
            "created_at": "2026-05-13T10:00:00",
            "files": [
                {"file_id": "store-id-217", "store_id": 217, "store_name": "Belchicken Aalst", "type": "report"},
                {"file_id": "store-id-218", "store_id": 218, "store_name": "Belchicken Ruisbroek", "type": "report"},
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(vat_app, "_get_logger", lambda: logging.getLogger("vat_reports_test"))
    monkeypatch.setattr(vat_app, "_get_config", lambda: SimpleNamespace(LAST_RUN_PATH=str(last_run_path)))

    service = MagicMock()
    service.files().delete().execute.return_value = None

    with patch("drive.auth.get_drive_service", return_value=service):
        outputs = list(vat_app.rollback_specific(["Belchicken Aalst (ID: 217)"]))

    assert outputs[0] == "**Rollback started.** Preparing to delete selected store files..."
    assert "Deleting 1 of 1 files..." in outputs[2]
    assert outputs[-1] == "**Deleted:** 1/1 files for selected stores."
    remaining = json.loads(last_run_path.read_text(encoding="utf-8"))
    assert [entry["file_id"] for entry in remaining["files"]] == ["store-id-218"]


def test_rollback_specific_auth_failure_does_not_mutate_last_run(monkeypatch, tmp_path):
    last_run_path = tmp_path / "last_run.json"
    last_run = {
        "report_name": "Q2 2026",
        "created_at": "2026-05-13T10:00:00",
        "files": [
            {"file_id": "store-id-217", "store_id": 217, "store_name": "Belchicken Aalst", "type": "report"},
        ],
    }
    last_run_path.write_text(json.dumps(last_run), encoding="utf-8")
    monkeypatch.setattr(vat_app, "_get_logger", lambda: logging.getLogger("vat_reports_test"))
    monkeypatch.setattr(vat_app, "_get_config", lambda: SimpleNamespace(LAST_RUN_PATH=str(last_run_path)))

    with patch("drive.auth.get_drive_service", side_effect=Exception("No token")):
        outputs = list(vat_app.rollback_specific(["Belchicken Aalst (ID: 217)"]))

    assert outputs[-1] == "**Auth Error:** No token"
    assert json.loads(last_run_path.read_text(encoding="utf-8")) == last_run
