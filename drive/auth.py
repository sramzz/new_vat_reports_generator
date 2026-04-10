import logging
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger("vat_reports")

# Lazy import config to avoid .env requirement at import time
_SCOPES = ["https://www.googleapis.com/auth/drive"]

def _get_config():
    import config
    return config

def get_drive_service():
    cfg = _get_config()
    creds = None

    if os.path.exists(cfg.TOKEN_PATH):
        logger.info(f"Loading existing token from {cfg.TOKEN_PATH}")
        creds = Credentials.from_authorized_user_file(cfg.TOKEN_PATH, cfg.GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Token expired, refreshing...")
            creds.refresh(Request())
            logger.info("Token refreshed successfully")
        else:
            logger.info("No valid token found, starting OAuth flow (browser popup)...")
            flow = InstalledAppFlow.from_client_secrets_file(cfg.CREDENTIALS_PATH, cfg.GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("OAuth flow completed")

        with open(cfg.TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        logger.info(f"Token saved to {cfg.TOKEN_PATH}")

    logger.info("Google Drive service built successfully")
    return build("drive", "v3", credentials=creds)
