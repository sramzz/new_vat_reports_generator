"""
Live Google Drive connection tests.

Run with:  uv run pytest tests/test_drive_connection.py -m live -v -s
The -s flag is needed to see print output (file IDs, links).

Requires:
  - credentials.json in project root (download from Google Cloud Console)
  - GDRIVE_TEST_FOLDER_ID in .env (a Drive folder where test files can be uploaded/deleted)
"""

import os
import tempfile
import time

import pytest

pytestmark = pytest.mark.live


def _load_config():
    import config
    return config


def _has_drive_test_config():
    try:
        cfg = _load_config()
        return bool(cfg.GDRIVE_TEST_FOLDER_ID)
    except Exception:
        return False


def _has_credentials_file():
    try:
        cfg = _load_config()
        return os.path.exists(cfg.CREDENTIALS_PATH)
    except Exception:
        return False


@pytest.fixture
def cfg():
    return _load_config()


@pytest.fixture
def drive_service(cfg):
    if not os.path.exists(cfg.CREDENTIALS_PATH):
        pytest.skip(
            f"credentials.json not found at {cfg.CREDENTIALS_PATH}. "
            f"Download it from Google Cloud Console > APIs & Services > Credentials > OAuth 2.0 Client ID"
        )
    from drive.auth import get_drive_service
    return get_drive_service()


# -- Test 1: Authentication --

@pytest.mark.skipif(not _has_drive_test_config(), reason="GDRIVE_TEST_FOLDER_ID not in .env")
def test_drive_auth(cfg):
    """Authenticate with Google Drive (browser popup may appear for OAuth)."""
    print(f"\n  Credentials: {cfg.CREDENTIALS_PATH}")
    print(f"  Token:       {cfg.TOKEN_PATH}")

    if not os.path.exists(cfg.CREDENTIALS_PATH):
        pytest.fail(
            f"credentials.json not found at {cfg.CREDENTIALS_PATH}.\n"
            f"  Download it from: Google Cloud Console > APIs & Services > Credentials > OAuth 2.0 Client ID\n"
            f"  Place it at: {cfg.CREDENTIALS_PATH}"
        )

    has_token = os.path.exists(cfg.TOKEN_PATH)
    print(f"  Token exists: {has_token}")
    if not has_token:
        print("  >> First run — browser popup will appear for OAuth consent")

    print("  Authenticating...")
    start = time.time()
    from drive.auth import get_drive_service
    service = get_drive_service()
    elapsed = time.time() - start

    print(f"  Authenticated in {elapsed:.1f}s")
    assert service is not None


# -- Test 2: Upload + Delete round-trip --

@pytest.mark.skipif(not _has_drive_test_config(), reason="GDRIVE_TEST_FOLDER_ID not in .env")
def test_drive_upload_and_delete(cfg, drive_service):
    """Upload a test file to GDRIVE_TEST_FOLDER_ID, then delete it."""
    from drive.upload import upload_file
    from drive.delete import delete_files

    test_folder_id = cfg.GDRIVE_TEST_FOLDER_ID
    print(f"\n  Test folder: {test_folder_id}")

    # Create temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="pytest_drive_test_", delete=False) as f:
        f.write("Test file from test_drive_connection.py. Safe to delete.")
        test_file_path = f.name

    file_id = None
    try:
        # Upload
        print(f"  Uploading {os.path.basename(test_file_path)}...")
        start = time.time()
        file_id, web_link = upload_file(drive_service, test_file_path, test_folder_id)
        elapsed = time.time() - start
        print(f"  Uploaded in {elapsed:.1f}s: {file_id}")
        print(f"  Link: {web_link}")
        assert file_id, "Expected a file ID"
        assert web_link, "Expected a web view link"

        # Delete
        print(f"  Deleting {file_id}...")
        success_count, errors = delete_files(drive_service, [file_id])
        print(f"  Deleted: {success_count}/1")
        assert success_count == 1, f"Delete failed: {errors}"
        assert not errors, f"Delete had errors: {errors}"
        file_id = None  # mark as cleaned up

    finally:
        # Cleanup local file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)
        # If upload succeeded but delete failed, warn
        if file_id:
            print(f"  WARNING: test file {file_id} was NOT cleaned up — delete manually")
