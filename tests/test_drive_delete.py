from unittest.mock import MagicMock
from drive.delete import delete_files

def _mock_service():
    return MagicMock()

def test_delete_files_removes_all_by_id():
    service = _mock_service()
    service.files().delete().execute.return_value = None
    service.files().delete.reset_mock()
    file_ids = ["id-1", "id-2", "id-3", "id-4", "id-5"]
    success_count, errors = delete_files(service, file_ids)
    assert service.files().delete.call_count == 5
    assert success_count == 5

def test_delete_files_returns_success_count():
    service = _mock_service()
    service.files().delete().execute.return_value = None
    success_count, errors = delete_files(service, ["id-1", "id-2", "id-3"])
    assert success_count == 3
    assert errors == []

def test_delete_files_handles_partial_failure():
    service = _mock_service()
    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock = MagicMock()
        if call_count == 3:
            mock.execute.side_effect = Exception("Not found")
        else:
            mock.execute.return_value = None
        return mock
    service.files().delete = side_effect
    success_count, errors = delete_files(service, ["id-1", "id-2", "id-3", "id-4", "id-5"])
    assert success_count == 4
    assert len(errors) == 1
    assert "id-3" in errors[0]

def test_delete_files_empty_list():
    service = _mock_service()
    success_count, errors = delete_files(service, [])
    assert success_count == 0
    assert errors == []
