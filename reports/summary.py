import os
from openpyxl import Workbook

SUMMARY_COLUMNS = ["Store ID", "Store Name", "Report URL"]

def generate_summary(store_results: list[dict], report_name: str, output_dir: str) -> str:
    filename = f"{report_name} - VAT Summary Report.xlsx"
    path = os.path.join(output_dir, filename)
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(SUMMARY_COLUMNS)
    for result in store_results:
        ws.append([result["store_id"], result["store_name"], result["report_url"]])
    wb.save(path)
    return path
