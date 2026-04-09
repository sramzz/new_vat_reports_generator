from unittest.mock import MagicMock, patch, mock_open
from drive.auth import get_drive_service

@patch("drive.auth.build")
@patch("drive.auth.InstalledAppFlow")
@patch("drive.auth.os.path.exists", return_value=False)
@patch("drive.auth._get_config")
def test_auth_creates_token_on_first_run(mock_get_config, mock_exists, mock_flow_class, mock_build):
    mock_cfg = MagicMock()
    mock_cfg.TOKEN_PATH = "/fake/token.json"
    mock_cfg.CREDENTIALS_PATH = "/fake/credentials.json"
    mock_cfg.GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive"]
    mock_get_config.return_value = mock_cfg

    mock_flow = MagicMock()
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.to_json.return_value = '{"token": "fake"}'
    mock_flow.run_local_server.return_value = mock_creds
    mock_flow_class.from_client_secrets_file.return_value = mock_flow
    with patch("builtins.open", mock_open()):
        get_drive_service()
    mock_flow.run_local_server.assert_called_once()

@patch("drive.auth.build")
@patch("drive.auth.Credentials")
@patch("drive.auth.os.path.exists", return_value=True)
def test_auth_reuses_existing_valid_token(mock_exists, mock_creds_class, mock_build):
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds_class.from_authorized_user_file.return_value = mock_creds
    get_drive_service()
    mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)

@patch("drive.auth.build")
@patch("drive.auth.Request")
@patch("drive.auth.Credentials")
@patch("drive.auth.os.path.exists", return_value=True)
def test_auth_refreshes_expired_token(mock_exists, mock_creds_class, mock_request_class, mock_build):
    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "fake-refresh-token"
    mock_creds.to_json.return_value = '{"token": "refreshed"}'
    mock_creds_class.from_authorized_user_file.return_value = mock_creds
    with patch("builtins.open", mock_open()):
        get_drive_service()
    mock_creds.refresh.assert_called_once()
