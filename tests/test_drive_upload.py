import pytest
from unittest.mock import MagicMock
from drive.upload import upload_file, create_folder

def _mock_service():
    return MagicMock()

def test_upload_file_returns_id_and_link():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "file-123", "webViewLink": "https://drive.google.com/file/d/file-123/view"}
    service.permissions().create().execute.return_value = {"id": "perm-1"}
    file_id, link = upload_file(service, "/tmp/report.xlsx", "parent-folder-id")
    assert file_id == "file-123"
    assert link == "https://drive.google.com/file/d/file-123/view"

def test_upload_file_sends_correct_parent_folder():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "file-123", "webViewLink": "https://example.com"}
    service.permissions().create().execute.return_value = {"id": "perm-1"}
    upload_file(service, "/tmp/report.xlsx", "my-parent-folder")
    create_call = service.files().create.call_args
    body = create_call[1]["body"] if "body" in create_call[1] else create_call[0][0]
    assert body["parents"] == ["my-parent-folder"]

def test_upload_file_sends_correct_filename():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "file-123", "webViewLink": "https://example.com"}
    service.permissions().create().execute.return_value = {"id": "perm-1"}
    upload_file(service, "/tmp/My Report - Store A.xlsx", "parent-id")
    create_call = service.files().create.call_args
    body = create_call[1]["body"] if "body" in create_call[1] else create_call[0][0]
    assert body["name"] == "My Report - Store A.xlsx"

def test_upload_file_sets_anyone_can_edit():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "file-123", "webViewLink": "https://example.com"}
    service.permissions().create().execute.return_value = {"id": "perm-1"}
    upload_file(service, "/tmp/report.xlsx", "parent-id")
    perm_call = service.permissions().create.call_args
    assert perm_call[1]["fileId"] == "file-123"
    assert perm_call[1]["body"]["type"] == "anyone"
    assert perm_call[1]["body"]["role"] == "writer"

def test_upload_file_handles_api_error():
    service = _mock_service()
    service.files().create().execute.side_effect = Exception("Drive API error")
    with pytest.raises(RuntimeError, match="Failed to upload"):
        upload_file(service, "/tmp/report.xlsx", "parent-id")

def test_create_folder_returns_folder_id():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "new-folder-123"}
    folder_id = create_folder(service, "Belchicken NewStore", "reports-parent-id")
    assert folder_id == "new-folder-123"

def test_create_folder_sets_correct_parent():
    service = _mock_service()
    service.files().create().execute.return_value = {"id": "new-folder-123"}
    create_folder(service, "Belchicken NewStore", "reports-parent-id")
    create_call = service.files().create.call_args
    body = create_call[1]["body"] if "body" in create_call[1] else create_call[0][0]
    assert body["parents"] == ["reports-parent-id"]
    assert body["mimeType"] == "application/vnd.google-apps.folder"
    assert body["name"] == "Belchicken NewStore"
