from datetime import datetime
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
