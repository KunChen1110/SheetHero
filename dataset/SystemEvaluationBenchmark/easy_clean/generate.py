"""Generate easy clean system-evaluation cases.

The cases in this split are intentionally small, clean, and single-operation:
one input table, one straightforward transformation, and one output workbook.
"""

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

from openpyxl import Workbook


BASE = os.path.dirname(os.path.abspath(__file__))


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def write_workbook(path, sheet_name, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    wb.save(path)


def metadata(case_no, title, scenario, category, prompt, answer):
    case_name = f"Case{case_no:02d}"
    return {
        "task_id": f"Easy Clean Test {case_no}",
        "title": title,
        "scenario": scenario,
        "category": category,
        "spreadsheets": [f"{case_name}/tc{case_no:02d}_input01.csv"],
        "prompt": prompt,
        "answer": answer,
        "expected_output_file": [f"{case_name}/tc{case_no:02d}_output01.xlsx"],
        "feedback": "",
        "conversations": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
    }


def case01():
    case_no = 1
    d = os.path.join(BASE, "Case01")
    ensure_dir(d)
    rows = [
        ["OrderID", "Customer", "Status", "Amount_USD"],
        ["O1001", "Ava", "Paid", 120],
        ["O1002", "Ben", "Pending", 85],
        ["O1003", "Cara", "Paid", 64],
        ["O1004", "Dylan", "Cancelled", 43],
        ["O1005", "Eva", "Paid", 210],
        ["O1006", "Finn", "Pending", 99],
        ["O1007", "Gia", "Paid", 150],
        ["O1008", "Hugo", "Cancelled", 70],
    ]
    output = [rows[0]] + [row for row in rows[1:] if row[2] == "Paid"]
    write_csv(os.path.join(d, "tc01_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc01_output01.xlsx"), "Paid_Orders", output)
    return metadata(
        case_no,
        "Paid Orders Filter",
        "Retail / order tracking",
        "filter rows where Status equals Paid",
        "Filter the table to keep only rows where Status is Paid. Output the result as a new spreadsheet.",
        "Kept 4 paid orders: O1001, O1003, O1005, and O1007.",
    )


def case02():
    case_no = 2
    d = os.path.join(BASE, "Case02")
    ensure_dir(d)
    rows = [
        ["Product", "UnitsSold"],
        ["Notebook", 42],
        ["Pen", 135],
        ["Folder", 67],
        ["Marker", 89],
        ["Stapler", 24],
        ["Tape", 58],
        ["Envelope", 73],
    ]
    output = [rows[0]] + sorted(rows[1:], key=lambda row: row[1], reverse=True)
    write_csv(os.path.join(d, "tc02_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc02_output01.xlsx"), "Sorted_Products", output)
    return metadata(
        case_no,
        "Product Sales Sort",
        "Office supplies / sales ranking",
        "sort rows by UnitsSold descending",
        "Sort the table by UnitsSold from highest to lowest. Output the sorted table as a new spreadsheet.",
        "Sorted 7 products by UnitsSold descending; Pen is first with 135 units.",
    )


def case03():
    case_no = 3
    d = os.path.join(BASE, "Case03")
    ensure_dir(d)
    rows = [
        ["Item", "Quantity", "UnitPrice_USD"],
        ["Desk Lamp", 3, 28],
        ["Chair", 5, 75],
        ["Monitor", 2, 160],
        ["Keyboard", 4, 45],
        ["Mouse", 6, 22],
        ["Webcam", 2, 55],
    ]
    output = [["Item", "Quantity", "UnitPrice_USD", "LineTotal_USD"]]
    output += [row + [row[1] * row[2]] for row in rows[1:]]
    write_csv(os.path.join(d, "tc03_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc03_output01.xlsx"), "Line_Totals", output)
    return metadata(
        case_no,
        "Invoice Line Totals",
        "Purchasing / invoice calculation",
        "add calculated column LineTotal_USD = Quantity * UnitPrice_USD",
        "Add a LineTotal_USD column equal to Quantity multiplied by UnitPrice_USD. Output the result as a new spreadsheet.",
        "Added LineTotal_USD for 6 invoice items.",
    )


def case04():
    case_no = 4
    d = os.path.join(BASE, "Case04")
    ensure_dir(d)
    rows = [
        ["Region", "Revenue_USD"],
        ["North", 1200],
        ["South", 900],
        ["East", 1100],
        ["North", 800],
        ["West", 700],
        ["South", 650],
        ["East", 950],
        ["West", 500],
        ["North", 400],
    ]
    totals = defaultdict(int)
    for region, revenue in rows[1:]:
        totals[region] += revenue
    output = [["Region", "Total_Revenue_USD"]]
    output += [[region, totals[region]] for region in sorted(totals)]
    write_csv(os.path.join(d, "tc04_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc04_output01.xlsx"), "Revenue_By_Region", output)
    return metadata(
        case_no,
        "Revenue By Region",
        "Sales / regional summary",
        "group by Region and sum Revenue_USD",
        "Group the table by Region and calculate the total Revenue_USD for each region. Output the summary as a new spreadsheet.",
        "Calculated total revenue for 4 regions; North has the highest total at 2400.",
    )


def case05():
    case_no = 5
    d = os.path.join(BASE, "Case05")
    ensure_dir(d)
    rows = [
        ["Student", "Score"],
        ["Aisha", 84],
        ["Bruno", 71],
        ["Chen", 93],
        ["Dina", 66],
        ["Eli", 88],
        ["Farah", 79],
        ["Gabe", 91],
        ["Hana", 74],
    ]
    avg = round(sum(row[1] for row in rows[1:]) / (len(rows) - 1), 2)
    output = [["Average_Score"], [avg]]
    write_csv(os.path.join(d, "tc05_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc05_output01.xlsx"), "Average_Score", output)
    return metadata(
        case_no,
        "Class Average Score",
        "Education / score summary",
        "calculate the average of Score",
        "Calculate the average Score for the table. Output the result as a new spreadsheet.",
        f"Average Score is {avg}.",
    )


def case06():
    case_no = 6
    d = os.path.join(BASE, "Case06")
    ensure_dir(d)
    rows = [
        ["Email", "SignupDate"],
        ["ava@example.com", "2024-01-12"],
        ["ben@example.com", "2024-01-15"],
        ["ava@example.com", "2024-01-12"],
        ["cara@example.com", "2024-02-03"],
        ["dylan@example.com", "2024-02-10"],
        ["ben@example.com", "2024-01-15"],
        ["eva@example.com", "2024-03-05"],
    ]
    seen = set()
    output = [rows[0]]
    for row in rows[1:]:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            output.append(row)
    write_csv(os.path.join(d, "tc06_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc06_output01.xlsx"), "Unique_Signups", output)
    return metadata(
        case_no,
        "Unique Signup Rows",
        "Marketing / signup list cleanup",
        "remove exact duplicate rows",
        "Remove exact duplicate rows from the table. Output the unique rows as a new spreadsheet.",
        "Removed 2 duplicate rows and kept 5 unique signup rows.",
    )


def case07():
    case_no = 7
    d = os.path.join(BASE, "Case07")
    ensure_dir(d)
    rows = [
        ["TicketID", "Priority"],
        ["T001", "High"],
        ["T002", "Low"],
        ["T003", "Medium"],
        ["T004", "High"],
        ["T005", "Low"],
        ["T006", "High"],
        ["T007", "Medium"],
        ["T008", "Low"],
        ["T009", "Medium"],
    ]
    counts = Counter(row[1] for row in rows[1:])
    output = [["Priority", "Ticket_Count"]]
    output += [[priority, counts[priority]] for priority in ["High", "Medium", "Low"]]
    write_csv(os.path.join(d, "tc07_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc07_output01.xlsx"), "Tickets_By_Priority", output)
    return metadata(
        case_no,
        "Ticket Count By Priority",
        "Customer support / ticket summary",
        "count rows by Priority",
        "Count how many tickets there are for each Priority. Output the counts as a new spreadsheet.",
        "Counted 3 High, 3 Medium, and 3 Low priority tickets.",
    )


def case08():
    case_no = 8
    d = os.path.join(BASE, "Case08")
    ensure_dir(d)
    rows = [
        ["Name", "Department", "Location"],
        ["Ava", "Sales", "London"],
        ["Ben", "Finance", "Leeds"],
        ["Cara", "Sales", "Bristol"],
        ["Dylan", "IT", "London"],
        ["Eva", "HR", "Manchester"],
        ["Finn", "IT", "Leeds"],
    ]
    output = [["Name", "Department"]] + [[row[0], row[1]] for row in rows[1:]]
    write_csv(os.path.join(d, "tc08_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc08_output01.xlsx"), "Selected_Columns", output)
    return metadata(
        case_no,
        "Employee Column Selection",
        "HR / employee table",
        "select Name and Department columns",
        "Keep only the Name and Department columns. Output the result as a new spreadsheet.",
        "Kept the Name and Department columns for 6 employees.",
    )


def case09():
    case_no = 9
    d = os.path.join(BASE, "Case09")
    ensure_dir(d)
    rows = [
        ["Date", "Visitors"],
        ["2024-04-01", 120],
        ["2024-04-02", 135],
        ["2024-04-03", 128],
        ["2024-04-04", 160],
        ["2024-04-05", 155],
        ["2024-04-06", 180],
        ["2024-04-07", 172],
    ]
    output = [["Date", "Visitors", "DayName"]]
    for date_text, visitors in rows[1:]:
        day_name = datetime.strptime(date_text, "%Y-%m-%d").strftime("%A")
        output.append([date_text, visitors, day_name])
    write_csv(os.path.join(d, "tc09_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc09_output01.xlsx"), "Day_Names", output)
    return metadata(
        case_no,
        "Website Day Names",
        "Web analytics / daily traffic",
        "add DayName derived from Date",
        "Add a DayName column derived from the Date column. Output the result as a new spreadsheet.",
        "Added DayName for 7 daily visitor rows.",
    )


def case10():
    case_no = 10
    d = os.path.join(BASE, "Case10")
    ensure_dir(d)
    rows = [
        ["Employee", "HoursWorked", "HourlyRate_USD"],
        ["Ava", 38, 24],
        ["Ben", 42, 22],
        ["Cara", 35, 28],
        ["Dylan", 40, 25],
        ["Eva", 30, 30],
        ["Finn", 45, 20],
    ]
    output = [["Employee", "HoursWorked", "HourlyRate_USD", "Pay_USD"]]
    output += [row + [row[1] * row[2]] for row in rows[1:]]
    write_csv(os.path.join(d, "tc10_input01.csv"), rows)
    write_workbook(os.path.join(d, "tc10_output01.xlsx"), "Payroll", output)
    return metadata(
        case_no,
        "Simple Payroll Calculation",
        "Payroll / wages",
        "add calculated column Pay_USD = HoursWorked * HourlyRate_USD",
        "Add a Pay_USD column equal to HoursWorked multiplied by HourlyRate_USD. Output the result as a new spreadsheet.",
        "Added Pay_USD for 6 employees.",
    )


def main():
    cases = [
        case01(),
        case02(),
        case03(),
        case04(),
        case05(),
        case06(),
        case07(),
        case08(),
        case09(),
        case10(),
    ]
    with open(os.path.join(BASE, "dataset.json"), "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=4)
        f.write("\n")


if __name__ == "__main__":
    main()
