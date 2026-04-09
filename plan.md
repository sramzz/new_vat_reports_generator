
---

## Updated Approach: TDD Throughout

**Testing framework:** `pytest` + `pytest-mock` for mocking external services (Azure SQL, Google Drive API). Added to `pyproject.toml`.

**Principle:** For every module, the workflow is: write tests → run tests (all red) → implement → run tests (all green) → refactor → move to next module.

**What gets mocked:** The database connection, the Google Drive API, and file system operations for most tests. No real API calls in the test suite — those are covered by manual QA in Phase 5.

---

## Revised Project Structure

```
new_vat_reports_generator/
├── app.py
├── plan.md
├── config.py
├── pyproject.toml
├── uv.lock
├── db/
│   ├── __init__.py
│   └── query.py
├── drive/
│   ├── __init__.py
│   ├── auth.py
│   ├── upload.py
│   ├── delete.py
│   └── mapping.py
├── reports/
│   ├── __init__.py
│   ├── split.py
│   ├── excel.py
│   └── summary.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures: sample data, mock Drive service, mock DB
│   ├── test_db_query.py
│   ├── test_drive_auth.py
│   ├── test_drive_upload.py
│   ├── test_drive_delete.py
│   ├── test_drive_mapping.py
│   ├── test_report_split.py
│   ├── test_report_excel.py
│   ├── test_report_summary.py
│   └── test_integration.py    # End-to-end with all external services mocked
├── fixtures/
│   ├── sample_query_result.json       # Realistic sample data (~50 rows, 3 stores)
│   ├── sample_store_mapping.json      # Known mapping for test stores
│   └── sample_last_run.json           # Sample rollback state
├── data/
│   ├── store_mapping.json
│   └── last_run.json
├── scripts/
│   ├── setup.bat
│   ├── setup.sh
│   ├── run.bat
│   └── run.sh
├── .env
├── .gitignore
└── README.md
```

---

## Revised Phased Plan

### Phase 0 — Project Setup *(~0.5 day)*

*Unchanged from before, plus:*

| # | Task | Detail |
|---|------|--------|
| 0.1–0.5 | All previous Phase 0 tasks | Repo, config, scaffold, scripts, gitignore — same as before. |
| 0.6 | **Add test tooling** | Add `pytest`, `pytest-mock`, `pytest-cov` to `pyproject.toml` dev dependencies. Run `uv lock`. Create `tests/` directory and `conftest.py`. |
| 0.7 | **Build test fixtures** | Create `fixtures/sample_query_result.json`: a realistic dataset with ~50 rows across 3 known stores and 1 new store (not in the mapping). Create `fixtures/sample_store_mapping.json` with the 3 known stores. Create `fixtures/sample_last_run.json` with a sample run state. These fixtures are the foundation for all tests. |
| 0.8 | **Verify test runner** | Write one trivial passing test to confirm `uv run pytest` works on both Windows and Mac. Green light before proceeding. |

---

### Phase 1 — Database Layer *(~1 day)*

**Tests first:**

| # | Test file | Tests to write (all red initially) | |
|---|---|---|---|
| 1.1 | `test_db_query.py` | `test_query_returns_expected_columns` — mock `pyodbc.connect`, verify the result contains all 12 columns (`CreatedOn`, `storeId`, `RegisterName`, `0%`, `6%`, `12%`, `21%`, `Bancontact`, `Cash`, `Betalen met kaart`, `UberEats`, `TakeAway`, `Deliveroo`). |
| 1.2 | | `test_query_parameterizes_months_correctly` — given months `[1, 2, 3]` and year `2026`, verify the query is called with the correct parameters. |
| 1.3 | | `test_query_returns_list_of_dicts` — verify the return type and structure match expectations. |
| 1.4 | | `test_query_handles_empty_result` — mock an empty cursor, verify it returns an empty list and no exception. |
| 1.5 | | `test_query_handles_connection_failure` — mock a connection error, verify it returns a structured error message (not a raw exception). |
| 1.6 | | `test_query_handles_timeout` — mock a timeout after the configured limit, verify a clear error message. |
| 1.7 | | `test_query_handles_mfa_cancelled` — mock the Azure AD Interactive auth being cancelled, verify graceful error. |

**Then implement** `db/query.py` until all 7 tests pass.

---

### Phase 2 — Google Drive Layer *(~2 days)*

**Tests first:**

| # | Test file | Tests to write |
|---|---|---|
| 2.1 | `test_drive_auth.py` | `test_auth_creates_token_on_first_run` — mock the OAuth flow, verify `token.json` would be written. |
| 2.2 | | `test_auth_reuses_existing_token` — mock a valid existing token, verify no browser popup is triggered. |
| 2.3 | | `test_auth_refreshes_expired_token` — mock an expired token with valid refresh token, verify silent refresh. |
| 2.4 | `test_drive_upload.py` | `test_upload_file_returns_id_and_link` — mock Drive API `files.create`, verify it returns `(file_id, web_view_link)`. |
| 2.5 | | `test_upload_file_sends_correct_parent_folder` — verify the parent folder ID is passed correctly to the API. |
| 2.6 | | `test_upload_file_sends_correct_filename` — verify the filename matches the naming convention. |
| 2.7 | | `test_upload_file_handles_api_error` — mock a Drive API error, verify a structured error is returned, not a crash. |
| 2.8 | | `test_create_folder_returns_folder_id` — mock folder creation, verify the returned ID. |
| 2.9 | | `test_create_folder_sets_correct_parent` — verify the new folder is created inside the "Reports" folder. |
| 2.10 | `test_drive_delete.py` | `test_delete_files_removes_all_by_id` — mock Drive API, pass 5 file IDs, verify all 5 delete calls are made. |
| 2.11 | | `test_delete_files_returns_success_count` — verify the count matches. |
| 2.12 | | `test_delete_files_handles_partial_failure` — mock 1 out of 5 failing, verify it continues and reports 4 successes + 1 error. |
| 2.13 | | `test_delete_files_handles_newly_created_folders` — verify that entries with `type: "folder"` in `last_run.json` are also deleted. |
| 2.14 | `test_drive_mapping.py` | `test_get_folder_id_returns_id_for_known_store` — load sample mapping, query a known store, verify correct ID. |
| 2.15 | | `test_get_folder_id_returns_none_for_unknown_store` — query an unknown store, verify `None`. |
| 2.16 | | `test_add_store_persists_to_file` — add a new store, reload the file, verify it's there. |
| 2.17 | | `test_get_all_stores_returns_full_mapping` — verify it returns the complete dict. |

**Then implement** `drive/auth.py`, `drive/upload.py`, `drive/delete.py`, `drive/mapping.py` until all 17 tests pass.

---

### Phase 3 — Report Processing Logic *(~2 days)*

**Tests first:**

| # | Test file | Tests to write |
|---|---|---|
| 3.1 | `test_report_split.py` | `test_split_groups_by_store` — given the sample fixture with 3 stores, verify 3 groups are returned with correct row counts. |
| 3.2 | | `test_split_groups_by_store_and_month` — given multi-month data, verify each store's data is further keyed by month. |
| 3.3 | | `test_split_preserves_all_rows` — sum of rows across all groups equals total input rows. |
| 3.4 | | `test_split_handles_single_store` — one store in input, verify one group. |
| 3.5 | | `test_split_handles_empty_input` — empty list in, empty dict out, no crash. |
| 3.6 | `test_report_excel.py` | `test_monthly_report_has_one_sheet` — generate for 1 month, verify the .xlsx has exactly 1 sheet. |
| 3.7 | | `test_monthly_report_sheet_has_correct_columns` — verify all 12 columns are present. |
| 3.8 | | `test_monthly_report_rows_sorted_ascending` — verify `CreatedOn` is ascending. |
| 3.9 | | `test_quarterly_report_has_three_sheets` — generate for 3 months, verify 3 sheets. |
| 3.10 | | `test_quarterly_report_sheets_named_by_month` — verify sheet names match (e.g., "January 2026"). |
| 3.11 | | `test_quarterly_report_each_sheet_has_correct_month_data` — verify no data leaks between sheets. |
| 3.12 | | `test_file_naming_convention` — verify output filename matches `"{report_name} - VAT Accounting Report - {store_name}.xlsx"`. |
| 3.13 | | `test_excel_file_is_valid` — open the generated file with `openpyxl`, verify it doesn't throw. |
| 3.14 | `test_report_summary.py` | `test_summary_has_two_columns` — verify "Store Name" and "Report URL" columns. |
| 3.15 | | `test_summary_has_one_row_per_store` — given 3 stores, verify 3 rows. |
| 3.16 | | `test_summary_urls_are_populated` — verify no empty URL cells. |
| 3.17 | | `test_summary_file_is_valid_xlsx` — open with `openpyxl`, no errors. |

**Then implement** `reports/split.py`, `reports/excel.py`, `reports/summary.py` until all 17 tests pass.

---

### Phase 3.5 — Integration Tests *(~0.5 day)*

| # | Test file | Tests to write |
|---|---|---|
| 3.18 | `test_integration.py` | `test_full_monthly_flow` — mock DB (returns sample data) and mock Drive (records all API calls). Run the full pipeline for 1 month. Verify: raw backup upload was called once, correct number of per-store uploads, summary upload was called once, `last_run.json` was written with all file IDs, no errors returned. |
| 3.19 | | `test_full_quarterly_flow` — same as above but for 3 months. Verify each store file has 3 sheets. |
| 3.20 | | `test_new_store_detection_flow` — sample data includes a store not in the mapping. Verify: folder creation was called, mapping was updated, the new store's report was uploaded to the new folder. |
| 3.21 | | `test_partial_upload_failure_flow` — mock Drive to fail on one specific store. Verify: all other stores succeed, the failed store is reported in the error list, `last_run.json` only contains the files that were actually created. |
| 3.22 | | `test_rollback_flow` — populate `last_run.json` with 5 file IDs, call delete. Verify all 5 delete calls were made and `last_run.json` is cleared. |
| 3.23 | | `test_rollback_specific_stores` — populate `last_run.json` with 5 files across 3 stores. Delete only 1 store's files. Verify only that store's files were deleted, others remain in `last_run.json`. |
| 3.24 | | `test_dry_run_creates_no_drive_files` — run the full pipeline with dry run flag. Verify zero Drive API calls, but local Excel files are generated and store count is correct. |

**All 7 integration tests green before moving to the UI.**

---

### Phase 4 — Gradio UI *(~1.5 days)*

The UI layer is thin — it calls the already-tested modules. Testing here is lighter and focused on wiring, not logic.

| # | Task | Detail |
|---|------|--------|
| 4.1 | **Input form** | Text field for report name prefix. Multi-select checkboxes for months. Year selector (defaults to current year). "Monthly" vs "Quarterly" toggle. "Dry run" checkbox. "Generate Reports" button. |
| 4.2 | **Input validation tests** | `test_rejects_empty_report_name`, `test_rejects_no_months_selected`, `test_quarterly_requires_multiple_months` — simple validation tests, written before the UI wiring. |
| 4.3 | **Progress feedback** | Status text during DB query. Progress bar incrementing per store. Use Gradio's yield-based generator pattern. |
| 4.4 | **Results display** | Store Name + Report URL table. Total processed / succeeded / failed counts. Link to summary file. Info message listing any new stores detected. |
| 4.5 | **Error display** | Red warning section for failed store uploads. Partial success is communicated clearly. |
| 4.6 | **Rollback tab** | Reads `last_run.json` on tab load. Displays run metadata. "Delete all" button with confirmation. "Delete specific stores" multi-select + button. Success/failure feedback after deletion. |
| 4.7 | **Validation tests green** | Verify all input validation tests pass before moving on. |

---

### Phase 5 — Testing & Hardening *(~1 day)*

*Unchanged from before:*

| # | Task | Detail |
|---|------|--------|
| 5.1 | **Dry-run mode** | Full flow without touching Drive. Validate output locally. |
| 5.2 | **Manual QA — monthly** | Real data, 1 month. Verify file names, folder placement, summary URLs, row counts. |
| 5.3 | **Manual QA — quarterly** | Real data, 3 months. Verify sheet structure and naming. |
| 5.4 | **Edge cases** | Empty result set, single store, new store, Drive API error mid-run, duplicate run for the same month, rollback after partial failure. |
| 5.5 | **Logging** | `run.log` with timestamps, user, report name, months, row counts, success/failure details. Gitignored. |
| 5.6 | **Cross-platform validation** | Full flow on Windows and Mac. Verify setup script, launcher, MFA popup, OAuth popup. |
| 5.7 | **Test coverage check** | Run `uv run pytest --cov`. Target: 90%+ coverage on `db/`, `drive/`, `reports/`. UI layer excluded from coverage target. |

---

### Phase 6 — Documentation & Handoff *(~0.5 day)*

*Unchanged from before:*

| # | Task | Detail |
|---|------|--------|
| 6.1 | **README — setup guide** | Windows and Mac sections with screenshots. Python install, `uv` install, `setup.bat`/`setup.sh`, `credentials.json` placement. |
| 6.2 | **README — usage guide** | Launching, Azure AD popup, Google consent, filling the form, understanding results, using rollback. |
| 6.3 | **README — maintenance** | `store_mapping.json`, SQL query updates, dependency updates, token expiry. |
| 6.4 | **README — troubleshooting** | Office IP errors, MFA timeout, Drive permission errors, long query times. |
| 6.5 | **README — running tests** | `uv run pytest` to run the full suite. `uv run pytest --cov` for coverage. Explain fixture data. |

---

## Revised Timeline

| Phase | Description | Effort |
|---|---|---|
| 0 | Project setup + test tooling + fixtures | 0.5 day |
| 1 | DB layer (7 tests → implement → green) | 1 day |
| 2 | Drive layer (17 tests → implement → green) | 2 days |
| 3 | Report logic (17 tests → implement → green) | 2 days |
| 3.5 | Integration tests (7 tests → green) | 0.5 day |
| 4 | Gradio UI + validation tests | 1.5 days |
| 5 | Hardening, manual QA, coverage check | 1 day |
| 6 | Documentation and handoff | 0.5 day |
| **Total** | | **~9 working days** |

