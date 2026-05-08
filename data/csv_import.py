import csv
from datetime import date, datetime


class CSVValidationError(ValueError):
    """Raised when an uploaded query-result CSV cannot be used safely."""


REPORT_COLUMNS = [
    "CreatedOn",
    "StoreId",
    "RegisterName",
    "0%",
    "6%",
    "12%",
    "21%",
    "Bancontact",
    "Cash",
    "Betalen met kaart",
    "UberEats",
    "TakeAway",
    "Deliveroo",
]

NUMERIC_COLUMNS = [
    "0%",
    "6%",
    "12%",
    "21%",
    "Bancontact",
    "Cash",
    "Betalen met kaart",
    "UberEats",
    "TakeAway",
    "Deliveroo",
]


def _parse_date(value: str, row_number: int) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value).date()
        except ValueError as exc:
            raise CSVValidationError(
                f"Row {row_number}: CreatedOn must be an ISO date, got '{value}'."
            ) from exc


def _parse_int(value: str, column: str, row_number: int) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise CSVValidationError(
            f"Row {row_number}: {column} must be an integer, got '{value}'."
        ) from exc


def _parse_float(value: str, column: str, row_number: int) -> float:
    if value == "":
        return 0.0
    try:
        return float(value)
    except ValueError as exc:
        raise CSVValidationError(
            f"Row {row_number}: {column} must be a number, got '{value}'."
        ) from exc


def parse_query_csv(path: str) -> list[dict]:
    """Read a VAT query-result CSV into the same row shape as database results."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [column for column in REPORT_COLUMNS if column not in fieldnames]
        if missing:
            raise CSVValidationError(
                "CSV is missing required column(s): " + ", ".join(missing)
            )

        rows = []
        for row_number, raw_row in enumerate(reader, start=2):
            normalized = {
                "CreatedOn": _parse_date(raw_row["CreatedOn"].strip(), row_number),
                "StoreId": _parse_int(raw_row["StoreId"].strip(), "StoreId", row_number),
                "RegisterName": raw_row["RegisterName"].strip(),
            }
            if not normalized["RegisterName"]:
                raise CSVValidationError(f"Row {row_number}: RegisterName cannot be empty.")

            for column in NUMERIC_COLUMNS:
                normalized[column] = _parse_float(raw_row[column].strip(), column, row_number)

            rows.append(normalized)

    if not rows:
        raise CSVValidationError("CSV contains no data rows.")
    return rows
