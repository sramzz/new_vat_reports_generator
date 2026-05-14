import logging
from collections.abc import Iterator

logger = logging.getLogger("vat_reports")


def delete_files_with_progress(service, file_ids: list[str]) -> Iterator[dict]:
    logger.info(f"Deleting {len(file_ids)} files from Google Drive: {file_ids}")
    success_count = 0
    errors = []
    total = len(file_ids)
    for index, file_id in enumerate(file_ids, start=1):
        success = False
        try:
            service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
            success_count += 1
            success = True
            logger.info(f"Deleted file: {file_id}")
        except Exception as e:
            logger.error(f"Failed to delete {file_id}: {e}")
            errors.append(f"Failed to delete {file_id}: {e}")
        yield {
            "file_id": file_id,
            "index": index,
            "total": total,
            "success": success,
            "success_count": success_count,
            "errors": list(errors),
        }
    logger.info(f"Delete complete: {success_count}/{len(file_ids)} succeeded, {len(errors)} errors")


def delete_files(service, file_ids: list[str]) -> tuple[int, list[str]]:
    success_count = 0
    errors = []
    for event in delete_files_with_progress(service, file_ids):
        success_count = event["success_count"]
        errors = event["errors"]
    return success_count, errors
