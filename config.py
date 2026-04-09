import os
from dotenv import load_dotenv

load_dotenv()

# Azure SQL
DB_SERVER = os.environ["DB_SERVER"]
DB_DATABASE = os.environ["DB_DATABASE"]
DB_DRIVER = os.environ.get("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
DB_TIMEOUT = int(os.environ.get("DB_TIMEOUT", "1800"))

# Google Drive folder IDs
GDRIVE_RAW_REPORT_FOLDER_ID = os.environ["GDRIVE_RAW_REPORT_FOLDER_ID"]
GDRIVE_REPORTS_FOLDER_ID = os.environ["GDRIVE_REPORTS_FOLDER_ID"]
GDRIVE_SUMMARY_FOLDER_ID = os.environ["GDRIVE_SUMMARY_FOLDER_ID"]

# Paths
STORE_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "data", "store_mapping.json")
LAST_RUN_PATH = os.path.join(os.path.dirname(__file__), "data", "last_run.json")
SQL_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "db", "SQL_Query.sql")
LOG_PATH = os.path.join(os.path.dirname(__file__), "run.log")

# Google OAuth
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
