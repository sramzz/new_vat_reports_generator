import logging

logger = logging.getLogger("vat_reports")


def delete_files(service, file_ids: list[str]) -> tuple[int, list[str]]:
    logger.info(f"Deleting {len(file_ids)} files from Google Drive")
    success_count = 0
    errors = []
    for file_id in file_ids:
        try:
            service.files().delete(fileId=file_id).execute()
            success_count += 1
            logger.info(f"Deleted file: {file_id}")
        except Exception as e:
            logger.error(f"Failed to delete {file_id}: {e}")
            errors.append(f"Failed to delete {file_id}: {e}")
    logger.info(f"Delete complete: {success_count}/{len(file_ids)} succeeded, {len(errors)} errors")
    return success_count, errors
