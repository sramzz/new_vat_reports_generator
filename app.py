import calendar
import os
import platform
import subprocess
import tempfile
import time
import traceback
from datetime import datetime

import gradio as gr

MONTH_NAMES = list(calendar.month_name)[1:]  # January..December


def _get_config():
    import config
    return config


def _get_logger():
    from logging_config import setup_logging
    return setup_logging()


def _timestamp():
    return datetime.now().strftime("%H:%M:%S")


def validate_inputs(report_name: str, months: list[str], year: int, is_quarterly: bool) -> str | None:
    if not report_name or not report_name.strip():
        return "Report name cannot be empty."
    if not months:
        return "Please select at least one month."
    if is_quarterly:
        month_indices = sorted([MONTH_NAMES.index(m) + 1 for m in months])
        if len(month_indices) != 3:
            return "Quarterly mode requires exactly 3 months."
        if month_indices != list(range(month_indices[0], month_indices[0] + 3)):
            return "Quarterly mode requires 3 consecutive months."
    return None


def generate_reports(report_name: str, months: list[str], year: int, is_quarterly: bool, dry_run: bool):
    """Generator that yields (status, log, results_table, error_text) after each step."""
    log_lines = []

    def log(msg):
        line = f"[{_timestamp()}] {msg}"
        log_lines.append(line)
        return "\n".join(log_lines)

    def state(status="", results="", errors=""):
        return status, "\n".join(log_lines), results, errors

    # -- Validate --
    error = validate_inputs(report_name, months, year, is_quarterly)
    if error:
        log(f"Validation failed: {error}")
        yield state(status=f"**Validation Error:** {error}")
        return

    try:
        cfg = _get_config()
        logger = _get_logger()
    except Exception as e:
        log(f"Configuration error: {e}")
        yield state(status=f"**Configuration Error:** {e}")
        return

    report_name = report_name.strip()
    month_indices = sorted([MONTH_NAMES.index(m) + 1 for m in months])
    mode = "DRY RUN" if dry_run else "LIVE"

    log(f"Starting report generation ({mode})")
    log(f"Report: {report_name} | Months: {month_indices} | Year: {int(year)}")
    yield state(status=f"**Starting** ({mode})...")

    try:
        from db.query import execute_query
        from drive.auth import get_drive_service
        from drive.upload import upload_file, create_folder
        from drive.mapping import load_mapping, get_folder_id, add_store
        from reports.split import filter_by_store
        from reports.excel import generate_store_report, generate_raw_backup
        from reports.summary import generate_summary
        from data.last_run_manager import save_last_run, add_file_entry

        output_dir = tempfile.mkdtemp(prefix="vat_reports_")

        # -- Step 1: Query DB --
        auth_method = cfg.AUTH_METHOD
        log(f"Auth method: {auth_method}")
        log("Connecting to database...")
        if auth_method == "active_directory_interactive":
            log(">> Entra ID Interactive — a browser window may open for MFA")
            yield state(status="**Connecting to database...** MFA browser popup may appear.")
        elif auth_method == "sql_auth":
            log(f">> Using SQL Server authentication (user: {cfg.AZURE_SQL_AUTH_USERNAME})")
            yield state(status="**Connecting to database...** Using SQL username/password.")
        elif auth_method == "service_principal":
            log(">> Using service principal authentication (Entra app)")
            yield state(status="**Connecting to database...** Service principal token auth.")
        else:
            log(f">> Unknown AUTH_METHOD='{auth_method}'")
            yield state(status=f"**Configuration Error:** Unknown AUTH_METHOD='{auth_method}'.")
            return
        log(">> Query takes 7-20 minutes after connection. Please wait.")
        yield state()
        time.sleep(0.1)  # give Gradio time to flush the yield to the browser

        try:
            rows = execute_query(month_indices, int(year))
        except Exception as e:
            logger.error(f"Database error: {e}")
            log(f"DATABASE ERROR: {e}")
            log(f"Error type: {type(e).__name__}")
            yield state(status=f"**Database Error:** {e}")
            return

        if not rows:
            logger.warning("Query returned no data")
            log("Query returned no data.")
            yield state(status="**No Data:** The query returned no results for the selected months.")
            return

        log(f"Query returned {len(rows)} rows")
        yield state(status=f"**Query complete.** {len(rows)} rows returned.")

        # -- Step 2: Drive auth (unless dry run) --
        service = None
        if not dry_run:
            log("Authenticating with Google Drive...")
            yield state(status="**Authenticating with Google Drive...**")
            try:
                service = get_drive_service()
                log("Google Drive authenticated.")
            except Exception as e:
                logger.error(f"Drive auth error: {e}")
                log(f"DRIVE AUTH ERROR: {e}")
                yield state(status=f"**Google Drive Auth Error:** {e}")
                return

        # -- Step 3: Raw backup --
        log("Generating raw backup Excel...")
        yield state(status="**Generating raw backup...**")
        raw_path = generate_raw_backup(rows, report_name, output_dir)
        logger.info(f"Raw backup generated: {raw_path}")
        log(f"Raw backup saved: {os.path.basename(raw_path)}")

        # Initialize last_run
        save_last_run(cfg.LAST_RUN_PATH, {
            "report_name": report_name,
            "created_at": datetime.now().isoformat(),
            "files": [],
        })

        if not dry_run:
            log("Uploading raw backup to Google Drive...")
            yield state(status="**Uploading raw backup...**")
            try:
                raw_file_id, _ = upload_file(service, raw_path, cfg.GDRIVE_RAW_REPORT_FOLDER_ID)
                add_file_entry(cfg.LAST_RUN_PATH, raw_file_id, None, None, "raw_backup")
                logger.info(f"Raw backup uploaded: {raw_file_id}")
                log("Raw backup uploaded.")
            except Exception as e:
                logger.error(f"Raw backup upload failed: {e}")
                log(f"RAW BACKUP UPLOAD ERROR: {e}")
                yield state(status=f"**Upload Error:** Failed to upload raw backup: {e}")
                return

        # -- Step 4: Split by store --
        log("Splitting data by store...")
        mapping = load_mapping(cfg.STORE_MAPPING_PATH)
        by_store = filter_by_store(rows)
        total_stores = len(by_store)
        log(f"Found {total_stores} stores in data.")
        yield state(status=f"**Processing {total_stores} stores...**")

        # -- Step 5 & 6: Per-store reports --
        store_results = []
        errors = []
        new_stores = []

        for idx, (store_id, store_rows) in enumerate(by_store.items()):
            store_name = store_rows[0]["RegisterName"]
            log(f"[{idx+1}/{total_stores}] Processing: {store_name}")
            yield state(status=f"**Processing store {idx+1}/{total_stores}:** {store_name}")

            # Check mapping
            folder_id = get_folder_id(mapping, store_id)
            if folder_id is None:
                new_stores.append(store_name)
                logger.info(f"New store detected: {store_name} (ID: {store_id})")
                log(f"  New store detected! Creating Drive folder...")
                if not dry_run:
                    try:
                        folder_id = create_folder(service, store_name, cfg.GDRIVE_REPORTS_FOLDER_ID)
                        add_store(mapping, cfg.STORE_MAPPING_PATH, store_id, store_name, store_name, folder_id)
                        log(f"  Folder created for {store_name}")
                    except Exception as e:
                        errors.append(f"{store_name}: Failed to create folder — {e}")
                        logger.error(f"Folder creation failed for {store_name}: {e}")
                        log(f"  ERROR creating folder: {e}")
                        continue

            # Generate Excel
            try:
                report_path = generate_store_report(store_rows, report_name, store_name, output_dir)
                log(f"  Excel generated: {os.path.basename(report_path)}")
            except Exception as e:
                errors.append(f"{store_name}: Failed to generate Excel — {e}")
                logger.error(f"Excel generation failed for {store_name}: {e}")
                log(f"  ERROR generating Excel: {e}")
                continue

            # Upload
            report_url = ""
            if not dry_run and folder_id:
                try:
                    file_id, report_url = upload_file(service, report_path, folder_id)
                    add_file_entry(cfg.LAST_RUN_PATH, file_id, store_id, store_name, "report")
                    logger.info(f"Uploaded report for {store_name}: {file_id}")
                    log(f"  Uploaded to Drive.")
                except Exception as e:
                    errors.append(f"{store_name}: Upload failed — {e}")
                    logger.error(f"Upload failed for {store_name}: {e}")
                    log(f"  ERROR uploading: {e}")
                    continue

            store_results.append({"store_id": store_id, "store_name": store_name, "report_url": report_url})

        # -- Step 7: Summary --
        log("Generating summary report...")
        yield state(status="**Generating summary...**")
        summary_path = generate_summary(store_results, report_name, output_dir)

        if not dry_run:
            log("Uploading summary to Google Drive...")
            try:
                summary_id, summary_url = upload_file(service, summary_path, cfg.GDRIVE_SUMMARY_FOLDER_ID)
                add_file_entry(cfg.LAST_RUN_PATH, summary_id, None, None, "summary")
                logger.info(f"Summary uploaded: {summary_id}")
                log("Summary uploaded.")
            except Exception as e:
                errors.append(f"Summary upload failed: {e}")
                logger.error(f"Summary upload failed: {e}")
                log(f"SUMMARY UPLOAD ERROR: {e}")

        # -- Done --
        succeeded = len(store_results)
        failed = len(errors)

        result_lines = [f"**Processed:** {succeeded + failed} stores | **Succeeded:** {succeeded} | **Failed:** {failed}"]
        if dry_run:
            result_lines.insert(0, "**DRY RUN** — No files were uploaded to Google Drive.\n")
            result_lines.append(f"\nLocal files generated in: `{output_dir}`")
        if new_stores:
            result_lines.append(f"\n**New stores detected:** {', '.join(new_stores)}")

        table_header = "| Store Name | Report URL |\n|---|---|\n"
        table_rows = "\n".join(f"| {r['store_name']} | {r['report_url'] or '(dry run)'} |" for r in store_results)
        results_table = table_header + table_rows

        error_text = ""
        if errors:
            error_text = "**Errors:**\n" + "\n".join(f"- {e}" for e in errors)

        log(f"Done! {succeeded} succeeded, {failed} failed.")
        logger.info(f"Report generation complete: {succeeded} succeeded, {failed} failed")
        yield state(status="\n".join(result_lines), results=results_table, errors=error_text)

    except Exception as e:
        logger.error(f"Unexpected error: {e}\n{traceback.format_exc()}")
        log(f"UNEXPECTED ERROR: {e}")
        log(traceback.format_exc())
        yield state(status=f"**Unexpected Error:** {e}\n\nCheck the log panel and log file for details.")


def open_log_folder():
    cfg = _get_config()
    log_dir = os.path.dirname(cfg.LOG_PATH)
    if platform.system() == "Darwin":
        subprocess.Popen(["open", log_dir])
    elif platform.system() == "Windows":
        os.startfile(log_dir)
    else:
        subprocess.Popen(["xdg-open", log_dir])
    return "Log folder opened."


def load_rollback_info():
    from data.last_run_manager import load_last_run
    cfg = _get_config()

    data = load_last_run(cfg.LAST_RUN_PATH)
    if data is None:
        return "No previous run found.", [], gr.update(interactive=False), gr.update(interactive=False)

    report_name = data.get("report_name", "Unknown")
    created_at = data.get("created_at", "Unknown")
    files = data.get("files", [])

    store_files = [f for f in files if f["type"] == "report"]
    raw_files = [f for f in files if f["type"] == "raw_backup"]
    summary_files = [f for f in files if f["type"] == "summary"]

    info = (
        f"**Report:** {report_name}\n"
        f"**Created:** {created_at}\n"
        f"**Files:** {len(store_files)} store reports, {len(raw_files)} raw backup, {len(summary_files)} summary"
    )
    store_choices = [f"{f['store_name']} (ID: {f['store_id']})" for f in store_files]
    return info, store_choices, gr.update(interactive=True), gr.update(interactive=bool(store_choices))


def rollback_all(confirm: bool):
    from drive.auth import get_drive_service
    from drive.delete import delete_files
    from data.last_run_manager import load_last_run, clear_last_run

    cfg = _get_config()
    logger = _get_logger()

    if not confirm:
        return "Please check the confirmation box before deleting."

    data = load_last_run(cfg.LAST_RUN_PATH)
    if data is None:
        return "No previous run to roll back."

    file_ids = [f["file_id"] for f in data.get("files", [])]

    try:
        service = get_drive_service()
    except Exception as e:
        return f"**Auth Error:** {e}"

    success_count, del_errors = delete_files(service, file_ids)
    clear_last_run(cfg.LAST_RUN_PATH)
    logger.info(f"Rollback all: deleted {success_count}/{len(file_ids)} files")

    result = f"**Deleted:** {success_count}/{len(file_ids)} files."
    if del_errors:
        result += "\n**Errors:**\n" + "\n".join(f"- {e}" for e in del_errors)
    return result


def rollback_specific(selected_stores: list[str]):
    from drive.auth import get_drive_service
    from drive.delete import delete_files
    from data.last_run_manager import load_last_run, remove_store_entries

    cfg = _get_config()
    logger = _get_logger()

    if not selected_stores:
        return "Please select at least one store."

    store_ids = []
    for s in selected_stores:
        id_part = s.split("(ID: ")[-1].rstrip(")")
        store_ids.append(int(id_part))

    data = load_last_run(cfg.LAST_RUN_PATH)
    if data is None:
        return "No previous run to roll back."

    file_ids = remove_store_entries(cfg.LAST_RUN_PATH, store_ids)

    try:
        service = get_drive_service()
    except Exception as e:
        return f"**Auth Error:** {e}"

    success_count, del_errors = delete_files(service, file_ids)
    logger.info(f"Rollback specific stores {store_ids}: deleted {success_count}/{len(file_ids)} files")

    result = f"**Deleted:** {success_count}/{len(file_ids)} files for selected stores."
    if del_errors:
        result += "\n**Errors:**\n" + "\n".join(f"- {e}" for e in del_errors)
    return result


# ---- UI Layout ----

current_year = datetime.now().year

with gr.Blocks(title="VAT Reports Generator") as app:
    gr.Markdown("# VAT Reports Generator")

    with gr.Tab("Generate Reports"):
        with gr.Row():
            with gr.Column(scale=1):
                report_name = gr.Textbox(label="Report Name", placeholder="e.g. Q1 - March 2026")
                months = gr.CheckboxGroup(choices=MONTH_NAMES, label="Months")
                year = gr.Number(label="Year", value=current_year, precision=0)
                is_quarterly = gr.Checkbox(label="Quarterly Report", value=False)
                dry_run = gr.Checkbox(label="Dry Run (no uploads)", value=False)
                generate_btn = gr.Button("Generate Reports", variant="primary")

            with gr.Column(scale=2):
                status_output = gr.Markdown(value="Ready. Fill in the form and click Generate.", label="Status")
                log_output = gr.Textbox(
                    label="Live Log",
                    lines=14,
                    max_lines=30,
                    interactive=False,
                    autoscroll=True,
                )
                results_table = gr.Markdown(label="Results")
                error_output = gr.Markdown(label="Errors")

        generate_btn.click(
            fn=generate_reports,
            inputs=[report_name, months, year, is_quarterly, dry_run],
            outputs=[status_output, log_output, results_table, error_output],
        )

    with gr.Tab("Rollback"):
        rollback_info = gr.Markdown("Loading...")
        refresh_btn = gr.Button("Refresh")

        with gr.Group():
            gr.Markdown("### Delete All Files")
            confirm_checkbox = gr.Checkbox(label="I confirm I want to delete all files from the last run")
            delete_all_btn = gr.Button("Delete All", variant="stop", interactive=False)
            delete_all_output = gr.Markdown()

        with gr.Group():
            gr.Markdown("### Delete Specific Stores")
            store_select = gr.CheckboxGroup(choices=[], label="Select stores to delete")
            delete_specific_btn = gr.Button("Delete Selected", variant="stop", interactive=False)
            delete_specific_output = gr.Markdown()

        def on_refresh():
            info, choices, all_btn_update, specific_btn_update = load_rollback_info()
            return info, gr.update(choices=choices), all_btn_update, specific_btn_update

        refresh_btn.click(fn=on_refresh, outputs=[rollback_info, store_select, delete_all_btn, delete_specific_btn])
        delete_all_btn.click(fn=rollback_all, inputs=[confirm_checkbox], outputs=[delete_all_output])
        delete_specific_btn.click(fn=rollback_specific, inputs=[store_select], outputs=[delete_specific_output])

    with gr.Row():
        log_btn = gr.Button("View Logs")
        log_status = gr.Textbox(label="", interactive=False, visible=False)
        log_btn.click(fn=open_log_folder, outputs=[log_status])

    app.load(fn=on_refresh, outputs=[rollback_info, store_select, delete_all_btn, delete_specific_btn])

if __name__ == "__main__":
    app.launch()
