import os
from dotenv import load_dotenv

load_dotenv()

# Azure SQL
AZURE_SQL_CONNECTIONSTRING = os.environ["AZURE_SQL_CONNECTIONSTRING"]
DB_TIMEOUT = int(os.environ.get("DB_TIMEOUT", "1800"))
AUTH_METHOD = os.environ.get("AUTH_METHOD", "active_directory_interactive")

# SQL auth (AUTH_METHOD=sql_auth)
AZURE_SQL_AUTH_USERNAME = os.environ.get("AZURE_SQL_AUTH_USERNAME", "")
AZURE_SQL_AUTH_PASSWORD = os.environ.get("AZURE_SQL_AUTH_PASSWORD", "")

# Service principal (AUTH_METHOD=service_principal)
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")

# Google Drive folder IDs
GDRIVE_RAW_REPORT_FOLDER_ID = os.environ["GDRIVE_RAW_REPORT_FOLDER_ID"]
GDRIVE_REPORTS_FOLDER_ID = os.environ["GDRIVE_REPORTS_FOLDER_ID"]
GDRIVE_SUMMARY_FOLDER_ID = os.environ["GDRIVE_SUMMARY_FOLDER_ID"]
GDRIVE_TEST_FOLDER_ID = os.environ.get("GDRIVE_TEST_FOLDER_ID", "")

# Paths
STORE_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "data", "store_mapping.json")
LAST_RUN_PATH = os.path.join(os.path.dirname(__file__), "data", "last_run.json")
SQL_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "db", "SQL_Query.sql")
LOG_PATH = os.path.join(os.path.dirname(__file__), "run.log")

# Google OAuth
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
