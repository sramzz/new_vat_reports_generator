from datetime import date
import csv

import pytest

from data.csv_import import CSVValidationError, parse_query_csv
from reports.split import filter_rows_by_store_ids


EXAMPLE_CSV = "Examples_Reports/ Q1 VAT Raw Report 2026 _ BC BE.csv"


def test_parse_query_csv_accepts_example_with_store_id():
    rows = parse_query_csv(EXAMPLE_CSV)

    assert rows
    assert rows[0]["StoreId"] == 266
    assert rows[0]["RegisterName"] == "Belchicken A12 Drive"
    assert rows[0]["CreatedOn"] == date(2026, 4, 1)
    assert rows[0]["6%"] == 1173.7


def test_parse_query_csv_requires_store_id(tmp_path):
    path = tmp_path / "raw.csv"
    path.write_text(
        "CreatedOn,RegisterName,0%,6%,12%,21%,Bancontact,Cash,Betalen met kaart,UberEats,TakeAway,Deliveroo\n"
        "2026-04-01,Store A,0,1,0,0,0,1,0,0,0,0\n",
        encoding="utf-8",
    )

    with pytest.raises(CSVValidationError, match="StoreId"):
        parse_query_csv(str(path))


def test_parse_query_csv_rejects_invalid_dates(tmp_path):
    path = tmp_path / "raw.csv"
    path.write_text(
        "CreatedOn,StoreId,RegisterName,0%,6%,12%,21%,Bancontact,Cash,Betalen met kaart,UberEats,TakeAway,Deliveroo\n"
        "not-a-date,217,Store A,0,1,0,0,0,1,0,0,0,0\n",
        encoding="utf-8",
    )

    with pytest.raises(CSVValidationError, match="CreatedOn"):
        parse_query_csv(str(path))


def test_parse_query_csv_rejects_invalid_numbers(tmp_path):
    path = tmp_path / "raw.csv"
    path.write_text(
        "CreatedOn,StoreId,RegisterName,0%,6%,12%,21%,Bancontact,Cash,Betalen met kaart,UberEats,TakeAway,Deliveroo\n"
        "2026-04-01,217,Store A,0,not-a-number,0,0,0,1,0,0,0,0\n",
        encoding="utf-8",
    )

    with pytest.raises(CSVValidationError, match="6%"):
        parse_query_csv(str(path))


def test_filter_rows_by_store_ids_keeps_only_selected_stores():
    rows = [
        {"StoreId": 217, "RegisterName": "Store A"},
        {"StoreId": 218, "RegisterName": "Store B"},
        {"StoreId": 219, "RegisterName": "Store C"},
    ]

    result = filter_rows_by_store_ids(rows, [217, "219"])

    assert [row["StoreId"] for row in result] == [217, 219]
