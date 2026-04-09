import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Lazy import config to avoid .env requirement at import time
_SCOPES = ["https://www.googleapis.com/auth/drive"]

def _get_config():
    import config
    return config

def get_drive_service():
    cfg = _get_config()
    creds = None

    if os.path.exists(cfg.TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(cfg.TOKEN_PATH, cfg.GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cfg.CREDENTIALS_PATH, cfg.GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)

        with open(cfg.TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)
