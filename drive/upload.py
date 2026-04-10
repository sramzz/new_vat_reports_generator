import logging
import os
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger("vat_reports")

def upload_file(service, local_path: str, parent_folder_id: str) -> tuple[str, str]:
    filename = os.path.basename(local_path)
    logger.info(f"Uploading file: {filename} -> folder {parent_folder_id}")
    file_metadata = {"name": filename, "parents": [parent_folder_id]}
    media = MediaFileUpload(local_path, resumable=True)
    try:
        created = service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()
    except Exception as e:
        logger.error(f"Upload failed for {filename}: {e}")
        raise RuntimeError(f"Failed to upload {filename}: {e}") from e
    file_id = created["id"]
    web_view_link = created.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
    logger.info(f"Setting permissions for file {file_id} (anyone/writer)")
    service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "writer"}, fields="id").execute()
    logger.info(f"Upload complete: {filename} -> {file_id}")
    return file_id, web_view_link

def create_folder(service, folder_name: str, parent_folder_id: str) -> str:
    logger.info(f"Creating Drive folder: {folder_name} in {parent_folder_id}")
    file_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_folder_id]}
    created = service.files().create(body=file_metadata, fields="id").execute()
    folder_id = created["id"]
    logger.info(f"Folder created: {folder_name} -> {folder_id}")
    return folder_id
