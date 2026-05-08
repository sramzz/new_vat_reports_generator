# Project Philosophy

## Goal

The VAT Reports Generator exists to reliably create Belchicken VAT reports from Azure SQL or an imported query-result CSV, generate the required Excel files, upload them to Google Drive, and keep rollback traceable when an upload needs to be undone.

The tool should stay practical for accounting staff and easy for a new developer to understand. A junior developer who has never seen the project should be able to follow a run from the UI inputs, through the logs, to the generated files and Drive uploads.

## Development Rules

- Use TDD for behavior changes. Write or update the test first, verify it fails for the right reason when practical, then implement the smallest change that makes it pass.
- Keep normal tests independent from real Azure SQL and Google Drive. Mock external services in regular unit and integration tests.
- Use live tests only when explicitly needed. Live tests must stay marked with `live` and should be run intentionally, for example with `uv run pytest tests/db_auth -m live -v -s`.
- Prefer small, focused changes over broad rewrites. Make the next useful improvement without hiding unrelated cleanup inside it.
- Keep the project easy to modify. A change in one workflow should not require a developer to understand every module.
- Keep user behavior stable unless the change explicitly requires otherwise. This is an operations tool, so surprise changes cost real time.

## Logging Rules

Log every meaningful step in the workflow so a maintainer can reconstruct what happened after the run:

- Report inputs: report name, selected months, year, mode, source, and selected stores.
- Authentication path: which configured auth method is being used, without exposing secrets.
- Database progress: connection attempt, query start, row count, column count, elapsed time, timeout, permission failures, and connection close.
- CSV import progress: source filename, validation failures, and row count.
- Report generation: raw backup, per-store processing, generated file names, new store detection, and summary generation.
- Drive actions: authentication, folder creation, successful uploads, partial upload failures, and summary upload.
- Rollback actions: selected rollback mode, target file counts, deleted file counts, and deletion errors.
- Unexpected errors: include enough context and stack trace information to debug the failure.

Never log raw credentials, tokens, client secrets, or unmasked connection passwords. If a value is needed for debugging, mask it before logging.

## Architecture Rules

Keep module boundaries simple and predictable:

- `app.py` owns the Gradio UI and workflow orchestration.
- `db/` owns SQL template handling, authentication choice, database connections, and query execution.
- `drive/` owns Google Drive authentication, folder mapping, uploads, folder creation, and deletes.
- `reports/` owns report splitting, Excel generation, raw backup files, and summary files.
- `data/` owns local state such as store mapping, store cache, CSV import, and last-run rollback tracking.
- `logging_config.py` owns log file setup and retention.

Business behavior should remain testable without real Azure SQL or Google Drive. Keep file-format details and external side effects behind focused helpers so tests can patch those helpers cleanly.

When adding a feature, make the flow traceable:

1. The UI should make the user action clear.
2. The code path should have one obvious orchestration point.
3. The logs should explain each important state transition.
4. The tests should cover the behavior without requiring live credentials.
5. The README should change only when user-facing setup, usage, or troubleshooting changes.
