import csv
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------------- CONFIG ----------------
SCOPES = ["https://www.googleapis.com/auth/drive"]  # upload + permissions

STORES_JSON_PATH = "list_stores_full.json"

# Folder on your computer containing all Excel files
LOCAL_EXCEL_DIR = "./outputApril"

# Output CSV
OUTPUT_CSV_PATH = "./Q1 Summary 2026 VAT Reports BC BE.csv"

# If True, and a file with the same name already exists in the target folder,
# the script will upload anyway (creating duplicates).
# If False, it will REPLACE the first matching file (update content).
ALLOW_DUPLICATES = True
# ----------------------------------------


def get_drive_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def load_stores(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    stores = payload.get("stores", [])
    if not isinstance(stores, list):
        raise ValueError("Invalid JSON: 'stores' must be a list.")
    return stores


def is_blank(value: Optional[str]) -> bool:
    return value is None or str(value).strip() == ""


def guess_excel_mime_type(file_path: Path) -> str:
    # Drive is fine with application/octet-stream, but we can be nicer.
    # Common Excel:
    # .xlsx -> application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    # .xls  -> application/vnd.ms-excel
    mime, _ = mimetypes.guess_type(str(file_path))
    return mime or "application/octet-stream"


def find_local_excel_file(local_dir: Path, filename: str) -> Path:
    # Exact match in the folder
    candidate = local_dir / filename
    if candidate.exists() and candidate.is_file():
        return candidate

    # If not found, try case-insensitive match
    lower = filename.lower()
    for p in local_dir.iterdir():
        if p.is_file() and p.name.lower() == lower:
            return p

    raise FileNotFoundError(f"Excel file not found locally: {filename}")


def find_existing_drive_file_id(
    service, parent_folder_id: str, filename: str
) -> Optional[str]:
    # Search for a file with this name directly in that folder
    q = (
        f"'{parent_folder_id}' in parents and name = '{filename.replace("'", "\\'")}' "
        "and trashed = false"
    )
    resp = service.files().list(q=q, fields="files(id, name)", pageSize=10).execute()
    files = resp.get("files", [])
    if not files:
        return None
    return files[0]["id"]


def upload_or_replace_file(
    service,
    local_path: Path,
    parent_folder_id: str,
    allow_duplicates: bool,
) -> Tuple[str, str]:
    """
    Returns (file_id, web_view_link).
    """
    filename = local_path.name
    mime_type = guess_excel_mime_type(local_path)

    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)

    existing_id = None
    if not allow_duplicates:
        existing_id = find_existing_drive_file_id(service, parent_folder_id, filename)

    if existing_id:
        # Replace content (update)
        updated = (
            service.files()
            .update(
                fileId=existing_id,
                media_body=media,
                fields="id, webViewLink",
            )
            .execute()
        )
        return updated["id"], updated.get("webViewLink", "")
    else:
        # Create new file in folder
        file_metadata = {"name": filename, "parents": [parent_folder_id]}
        created = (
            service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink",
            )
            .execute()
        )
        return created["id"], created.get("webViewLink", "")


def set_anyone_can_edit(service, file_id: str) -> None:
    permission_body = {"type": "anyone", "role": "writer"}
    service.permissions().create(
        fileId=file_id,
        body=permission_body,
        fields="id",
    ).execute()


def get_shareable_url(service, file_id: str) -> str:
    # webViewLink is usually enough, but ensure we have something.
    meta = service.files().get(fileId=file_id, fields="webViewLink").execute()
    link = meta.get("webViewLink")
    if link:
        return link
    # Fallback (still works in many cases):
    return f"https://drive.google.com/file/d/{file_id}/view"


def main():
    local_dir = Path(LOCAL_EXCEL_DIR).resolve()
    if not local_dir.exists() or not local_dir.is_dir():
        raise FileNotFoundError(
            f"LOCAL_EXCEL_DIR does not exist or is not a folder: {local_dir}"
        )

    stores = load_stores(STORES_JSON_PATH)
    service = get_drive_service()

    rows: List[Tuple[str, str]] = []
    skipped_no_excel = 0
    skipped_missing_local = 0
    uploaded = 0

    for store in stores:
        store_name = store.get("storeName")
        # CSV requires StoreName. If null, you can decide what to do; here we use folderName as fallback.
        if is_blank(store_name):
            store_name = store.get("folderName") or ""

        parent_folder_id = store.get("gdriveId")
        excel_filename = store.get("excelFileName")

        if is_blank(excel_filename):
            skipped_no_excel += 1
            continue

        try:
            local_file = find_local_excel_file(local_dir, str(excel_filename))
        except FileNotFoundError:
            skipped_missing_local += 1
            continue

        file_id, web_view_link = upload_or_replace_file(
            service=service,
            local_path=local_file,
            parent_folder_id=str(parent_folder_id),
            allow_duplicates=ALLOW_DUPLICATES,
        )

        # Set sharing: Anyone with link can edit
        set_anyone_can_edit(service, file_id)

        # Get a link to put in CSV
        report_url = web_view_link or get_shareable_url(service, file_id)

        rows.append((store_name, report_url))
        uploaded += 1

    # Write CSV
    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["StoreName", "ReportURL"])
        writer.writerows(rows)

    print("Done.")
    print(f"Uploaded/Updated: {uploaded}")
    print(f"Skipped (no excelFileName): {skipped_no_excel}")
    print(f"Skipped (local file missing): {skipped_missing_local}")
    print(f"CSV written: {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()
