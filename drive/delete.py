def delete_files(service, file_ids: list[str]) -> tuple[int, list[str]]:
    success_count = 0
    errors = []
    for file_id in file_ids:
        try:
            service.files().delete(fileId=file_id).execute()
            success_count += 1
        except Exception as e:
            errors.append(f"Failed to delete {file_id}: {e}")
    return success_count, errors
