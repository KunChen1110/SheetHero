"""
dataset_small: 10 cases, small tables (≤50 cells each).
Rules:
  - Every table has exactly ONE bug type (missing / inconsistency / semantic_anomaly)
  - That bug appears in MULTIPLE locations (2–4 times) within the table
  - Different tables in the same case may have different bug types
  - issue.json is a list, one entry per table
"""

import json, csv, random
from pathlib import Path

BASE = Path("/home/scygl3/Spreadsheet-diagnosis-data/dataset_small")
BASE.mkdir(parents=True, exist_ok=True)

def write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)

def save_issue(path, issues):
    with open(path, "w") as f:
        json.dump(issues, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 01 — Coffee Shop Daily Sales
# table1 (6×8=48): MISSING — Revenue_USD missing in 3 rows
# table2 (5×6=30): INCONSISTENCY — Payment_Method: "Cash"/"cash"/"CASH"
# ─────────────────────────────────────────────────────────────────────────────
def gen_case01():
    d = BASE / "case01"; d.mkdir(exist_ok=True)

    # table1 — Daily Sales  6 rows × 8 cols = 48 cells
    h1 = ["Date","Weekday","Staff_Count","Customers","Avg_Order_USD","Revenue_USD","Discount_USD","Net_Revenue_USD"]
    r1 = [
        ["2024-03-04","Monday",   3, 87, 8.50, 739.50,  22.10, 717.40],
        ["2024-03-05","Tuesday",  3, 94, 8.75, 822.50,  18.60, 803.90],
        ["2024-03-06","Wednesday",4,110, 9.20,    "",   25.30,    "" ],  # BUG: Revenue & Net missing
        ["2024-03-07","Thursday", 4,102, 8.90, 907.80,  21.80, 886.00],
        ["2024-03-08","Friday",   5,145, 9.60,    "",   34.50,    "" ],  # BUG
        ["2024-03-09","Saturday", 5,178,10.20,    "",   41.20,    "" ],  # BUG (Revenue_USD)
    ]
    # Only Revenue_USD (col index 5) is the tracked bug column
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Payment Methods  5 rows × 6 cols = 30 cells
    h2 = ["Date","Cash","Credit_Card","Mobile_Pay","Gift_Card","Payment_Method_Primary"]
    r2 = [
        ["2024-03-04", 120.00, 380.50, 198.50,  40.50, "Credit Card"],
        ["2024-03-05",  95.00, 420.30, 245.80,  61.40, "cash"       ],  # BUG
        ["2024-03-06", 145.50, 480.20, 280.30,  86.50, "Credit Card"],
        ["2024-03-07", 110.00, 460.80, 272.10,  64.90, "CASH"       ],  # BUG
        ["2024-03-08", 198.00, 520.60, 330.40, 108.00, "Credit Card"],
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "missing",
            "locations": ["row=3,column=Revenue_USD","row=5,column=Revenue_USD","row=6,column=Revenue_USD"],
            "description": "Revenue_USD is missing for Wed/Fri/Sat. Expected values: ~$1012 (110×9.20), ~$1392 (145×9.60), ~$1816 (178×10.20).",
            "business_context": "Coffee shop daily sales. Missing revenue prevents weekly P&L calculation and staff scheduling optimisation."
        },
        {
            "table": "table2.csv",
            "issue_type": "inconsistency",
            "locations": ["row=2,column=Payment_Method_Primary","row=4,column=Payment_Method_Primary"],
            "description": "Payment_Method_Primary uses mixed capitalisation: rows 2 and 4 have 'cash' and 'CASH' instead of standard 'Cash'. GROUP BY will split Cash into three buckets.",
            "business_context": "Payment mix reporting. Inconsistent labels corrupt daily payment channel analysis."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 02 — School Exam Results
# table1 (7×7=49): SEMANTIC ANOMALY — Score > 100 in 2 rows
# table2 (5×6=30): MISSING — Grade missing in 3 rows
# ─────────────────────────────────────────────────────────────────────────────
def gen_case02():
    d = BASE / "case02"; d.mkdir(exist_ok=True)

    # table1 — Exam Scores  7 rows × 7 cols = 49 cells
    h1 = ["StudentID","Name","Math_Score","English_Score","Science_Score","Avg_Score","Pass_Fail"]
    r1 = [
        ["S001","Alice Chen",     88, 92,  85, 88.3,"Pass"],
        ["S002","Bob Martinez",   76, 81,  79, 78.7,"Pass"],
        ["S003","Carol White",    91, 88,  93, 90.7,"Pass"],
        ["S004","David Kim",      62, 70,  68, 66.7,"Pass"],
        ["S005","Eva Johnson",    55, 149, 61, 88.3,"Pass"],  # BUG: English=149
        ["S006","Frank Brown",    83, 87,  90, 86.7,"Pass"],
        ["S007","Grace Lee",      78, 174, 80, 110.7,"Pass"], # BUG: English=174
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Student Info  5 rows × 6 cols = 30 cells
    h2 = ["StudentID","Age","Gender","Class","Teacher","Grade"]
    r2 = [
        ["S001",15,"Female","10A","Ms. Thompson","A"],
        ["S002",16,"Male",  "10A","Ms. Thompson","" ],  # BUG
        ["S003",15,"Female","10B","Mr. Davis",   "A+"],
        ["S004",16,"Male",  "10B","Mr. Davis",   ""  ],  # BUG
        ["S005",15,"Female","10A","Ms. Thompson","" ],  # BUG
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "semantic_anomaly",
            "locations": ["row=5,column=English_Score","row=7,column=English_Score"],
            "description": "English_Score values of 149 and 174 exceed the maximum possible score of 100. Correct values are likely 49 and 74 (leading '1' prepended by error).",
            "business_context": "School grade management. Impossible scores corrupt class ranking, GPA calculation, and pass/fail determination."
        },
        {
            "table": "table2.csv",
            "issue_type": "missing",
            "locations": ["row=2,column=Grade","row=4,column=Grade","row=5,column=Grade"],
            "description": "Grade is missing for students S002, S004, and S005. Expected grades based on Avg_Score: S002→B, S004→D, S005→B.",
            "business_context": "Student transcript system. Missing grades block report card generation and scholarship eligibility checks."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 03 — Hospital Outpatient Appointments
# table1 (6×8=48): INCONSISTENCY — Appointment_Date mixes YYYY-MM-DD and DD/MM/YYYY
# table2 (5×6=30): SEMANTIC ANOMALY — Systolic_BP impossibly high in 2 rows
# ─────────────────────────────────────────────────────────────────────────────
def gen_case03():
    d = BASE / "case03"; d.mkdir(exist_ok=True)

    # table1 — Appointments  6 rows × 8 cols = 48 cells
    h1 = ["ApptID","PatientID","Doctor","Department","Appointment_Date","Duration_min","Status","Fee_USD"]
    r1 = [
        ["A001","P101","Dr. Adams",  "Cardiology",  "2024-02-10", 30,"Completed", 150],
        ["A002","P102","Dr. Brown",  "Neurology",   "12/02/2024", 45,"Completed", 200],  # BUG
        ["A003","P103","Dr. Chen",   "Orthopedics", "2024-02-14", 30,"Completed", 130],
        ["A004","P104","Dr. Davis",  "General",     "17/02/2024", 20,"Completed",  90],  # BUG
        ["A005","P105","Dr. Evans",  "Cardiology",  "2024-02-19", 30,"Completed", 150],
        ["A006","P106","Dr. Foster", "Oncology",    "22/02/2024", 60,"Completed", 350],  # BUG
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Patient Vitals at Appointment  5 rows × 6 cols = 30 cells
    h2 = ["PatientID","Age","Weight_kg","Height_cm","Systolic_BP","Diastolic_BP"]
    r2 = [
        ["P101", 52, 78.5, 172, 128,  82],
        ["P102", 38, 65.0, 168, 118,  75],
        ["P103", 67, 82.0, 175, 445,  88],  # BUG: 445 impossible
        ["P104", 29, 58.5, 162, 108,  68],
        ["P105", 71, 89.0, 170, 512,  95],  # BUG: 512 impossible
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "inconsistency",
            "locations": ["row=2,column=Appointment_Date","row=4,column=Appointment_Date","row=6,column=Appointment_Date"],
            "description": "Appointment_Date mixes ISO format YYYY-MM-DD (rows 1,3,5) and DD/MM/YYYY (rows 2,4,6: '12/02/2024','17/02/2024','22/02/2024'). All should be standardised to YYYY-MM-DD.",
            "business_context": "Hospital scheduling system. Mixed date formats corrupt appointment timeline sorting and patient recall reminders."
        },
        {
            "table": "table2.csv",
            "issue_type": "semantic_anomaly",
            "locations": ["row=3,column=Systolic_BP","row=5,column=Systolic_BP"],
            "description": "Systolic_BP values of 445 and 512 mmHg are medically impossible (fatal above ~300 mmHg; normal range 90–180). Likely correct values: 145 and 152 — extra digit prepended.",
            "business_context": "EHR vital signs. Impossible BP values would trigger false emergency alerts and corrupt hypertension risk models."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 04 — Stock Portfolio Tracker
# table1 (8×6=48): MISSING — Closing_Price missing in 3 rows
# table2 (6×5=30): INCONSISTENCY — Sector names mixed case
# ─────────────────────────────────────────────────────────────────────────────
def gen_case04():
    d = BASE / "case04"; d.mkdir(exist_ok=True)

    # table1 — Daily Stock Prices  8 rows × 6 cols = 48 cells
    h1 = ["Date","Ticker","Opening_Price","Closing_Price","Volume","Daily_Change_Pct"]
    r1 = [
        ["2024-01-15","AAPL",  185.20, 187.50, 52_340_000,  1.24],
        ["2024-01-15","MSFT",  375.10,       "", 28_120_000, "" ],  # BUG
        ["2024-01-15","GOOGL", 140.30, 142.10, 19_840_000,  1.28],
        ["2024-01-15","AMZN",  153.40,       "", 31_560_000, "" ],  # BUG
        ["2024-01-15","META",  390.20, 395.80, 14_230_000,  1.43],
        ["2024-01-15","TSLA",  215.60,       "", 88_740_000, "" ],  # BUG
        ["2024-01-15","NVDA",  495.30, 502.40, 42_180_000,  1.43],
        ["2024-01-15","JPM",   170.40, 171.80, 11_920_000,  0.82],
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Stock Sectors  6 rows × 5 cols = 30 cells
    h2 = ["Ticker","Company","Sector","Market_Cap_B","Country"]
    r2 = [
        ["AAPL",  "Apple Inc.",           "technology",      2900, "USA"],  # BUG
        ["MSFT",  "Microsoft Corp.",      "Technology",      2800, "USA"],
        ["GOOGL", "Alphabet Inc.",        "TECHNOLOGY",      1700, "USA"],  # BUG
        ["AMZN",  "Amazon.com Inc.",      "Consumer Discretionary", 1600, "USA"],
        ["META",  "Meta Platforms",       "technology",      1100, "USA"],  # BUG
        ["TSLA",  "Tesla Inc.",           "Consumer Discretionary",  600, "USA"],
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "missing",
            "locations": ["row=2,column=Closing_Price","row=4,column=Closing_Price","row=6,column=Closing_Price"],
            "description": "Closing_Price missing for MSFT, AMZN, and TSLA on 2024-01-15. Expected: MSFT≈$378.20, AMZN≈$155.90, TSLA≈$218.40 (estimated from opening price and sector trend).",
            "business_context": "Portfolio tracker. Missing closing prices prevent daily P&L calculation and end-of-day NAV reporting."
        },
        {
            "table": "table2.csv",
            "issue_type": "inconsistency",
            "locations": ["row=1,column=Sector","row=3,column=Sector","row=5,column=Sector"],
            "description": "Sector for AAPL→'technology' (all lower), GOOGL→'TECHNOLOGY' (all upper), META→'technology' (all lower). Standard is Title Case 'Technology'. Sector-level aggregation will split the same group into 3 buckets.",
            "business_context": "Portfolio sector allocation dashboard. Inconsistent sector labels corrupt sector weight calculations and benchmark comparisons."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 05 — Hotel Room Bookings
# table1 (7×7=49): SEMANTIC ANOMALY — Room_Rate_USD absurdly low in 2 rows
# table2 (5×6=30): MISSING — Check_Out_Date missing in 2 rows
# ─────────────────────────────────────────────────────────────────────────────
def gen_case05():
    d = BASE / "case05"; d.mkdir(exist_ok=True)

    # table1 — Bookings  7 rows × 7 cols = 49 cells
    h1 = ["BookingID","Guest_Name","Room_Type","Check_In","Nights","Room_Rate_USD","Total_USD"]
    r1 = [
        ["B001","James Wilson",   "Standard",  "2024-04-10", 3,  189.00,  567.00],
        ["B002","Maria Garcia",   "Deluxe",    "2024-04-11", 2,  259.00,  518.00],
        ["B003","David Chen",     "Suite",     "2024-04-12", 4,    1.50, 6.00   ],  # BUG: $1.50/night
        ["B004","Sarah Williams", "Standard",  "2024-04-13", 2,  189.00,  378.00],
        ["B005","Robert Kim",     "Deluxe",    "2024-04-14", 3,  259.00,  777.00],
        ["B006","Emily Brown",    "Suite",     "2024-04-15", 5,    2.25,  11.25  ],  # BUG: $2.25/night
        ["B007","Michael Lee",    "Standard",  "2024-04-16", 1,  189.00,  189.00],
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Stay Details  5 rows × 6 cols = 30 cells
    h2 = ["BookingID","Room_Number","Floor","Check_Out_Date","Breakfast_Included","Parking"]
    r2 = [
        ["B001", 205, 2, "2024-04-13", True,  False],
        ["B002", 312, 3, "",           True,  True ],  # BUG
        ["B003", 501, 5, "2024-04-16", False, True ],
        ["B004", 118, 1, "",           False, False],  # BUG
        ["B005", 310, 3, "2024-04-17", True,  False],
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "semantic_anomaly",
            "locations": ["row=3,column=Room_Rate_USD","row=6,column=Room_Rate_USD"],
            "description": "Suite room rate is $1.50/night (B003) and $2.25/night (B006), implausibly low for a hotel suite (standard suite rate: $389–$459/night). Likely a decimal point error: $1.50→$150 or $389, $2.25→$225 or $459.",
            "business_context": "Hotel PMS. Absurd room rates would cause massive revenue leakage if bookings were confirmed at these prices."
        },
        {
            "table": "table2.csv",
            "issue_type": "missing",
            "locations": ["row=2,column=Check_Out_Date","row=4,column=Check_Out_Date"],
            "description": "Check_Out_Date missing for bookings B002 and B004. Expected: B002 → 2024-04-13 (2 nights from 04-11), B004 → 2024-04-15 (2 nights from 04-13).",
            "business_context": "Hotel room availability calendar. Missing check-out dates prevent room turnover scheduling and double-booking prevention."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 06 — Employee Attendance Log
# table1 (6×8=48): INCONSISTENCY — Status uses mixed case "Present"/"present"/"PRESENT"
# table2 (5×6=30): MISSING — Hours_Worked missing in 3 rows
# ─────────────────────────────────────────────────────────────────────────────
def gen_case06():
    d = BASE / "case06"; d.mkdir(exist_ok=True)

    # table1 — Attendance  6 rows × 8 cols = 48 cells
    h1 = ["Date","EmployeeID","Name","Department","Status","Clock_In","Clock_Out","Overtime_hrs"]
    r1 = [
        ["2024-03-11","E01","Alice Brown",  "Engineering","Present", "09:02","18:15",0.0],
        ["2024-03-11","E02","Bob Davis",    "Marketing",  "present", "08:55","17:30",0.0],  # BUG
        ["2024-03-11","E03","Carol Smith",  "Finance",    "Absent",  "",     "",     0.0],
        ["2024-03-11","E04","David Lee",    "Engineering","PRESENT", "09:10","19:45",1.5],  # BUG
        ["2024-03-11","E05","Eva Wilson",   "Marketing",  "Present", "08:45","17:20",0.0],
        ["2024-03-11","E06","Frank Taylor", "Finance",    "present", "09:00","18:00",0.0],  # BUG
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Work Hours Summary  5 rows × 6 cols = 30 cells
    h2 = ["EmployeeID","Name","Week_Start","Hours_Worked","Leave_Days","Overtime_Total"]
    r2 = [
        ["E01","Alice Brown",  "2024-03-11", 42.5, 0, 2.5],
        ["E02","Bob Davis",    "2024-03-11",   "" , 0, 0.0],  # BUG
        ["E03","Carol Smith",  "2024-03-11", 0.0,  1, 0.0],
        ["E04","David Lee",    "2024-03-11",   "" , 0, 1.5],  # BUG
        ["E05","Eva Wilson",   "2024-03-11",   "" , 0, 0.0],  # BUG
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "inconsistency",
            "locations": ["row=2,column=Status","row=4,column=Status","row=6,column=Status"],
            "description": "Status uses mixed capitalisation: rows 2 and 6 have 'present' (all lower), row 4 has 'PRESENT' (all upper). Standard is Title Case 'Present'/'Absent'. Attendance rate calculation will miss these three employees.",
            "business_context": "HR attendance system. Inconsistent labels cause attendance rate reports to under-count present employees."
        },
        {
            "table": "table2.csv",
            "issue_type": "missing",
            "locations": ["row=2,column=Hours_Worked","row=4,column=Hours_Worked","row=5,column=Hours_Worked"],
            "description": "Hours_Worked missing for E02 (Bob Davis), E04 (David Lee), and E05 (Eva Wilson). Expected: E02≈40h, E04≈41.5h (includes 1.5h overtime), E05≈40.5h.",
            "business_context": "Payroll system. Missing hours block salary calculation for the week."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 07 — E-commerce Product Returns
# table1 (8×6=48): MISSING — Return_Reason missing in 3 rows
# table2 (6×5=30): SEMANTIC ANOMALY — Return_Qty > Units_Sold in 2 rows
# ─────────────────────────────────────────────────────────────────────────────
def gen_case07():
    d = BASE / "case07"; d.mkdir(exist_ok=True)

    # table1 — Return Records  8 rows × 6 cols = 48 cells
    h1 = ["ReturnID","OrderID","Product","Return_Date","Return_Reason","Refund_USD"]
    r1 = [
        ["R001","ORD1021","Laptop",        "2024-02-01","Defective",         899.00],
        ["R002","ORD1035","Running Shoes",  "2024-02-03","Wrong Size",         89.99],
        ["R003","ORD1042","Headphones",     "2024-02-05","",                  149.00],  # BUG
        ["R004","ORD1058","Smartwatch",     "2024-02-07","Changed Mind",      299.00],
        ["R005","ORD1063","USB-C Hub",      "2024-02-09","",                   49.99],  # BUG
        ["R006","ORD1071","Winter Jacket",  "2024-02-11","Defective",         189.99],
        ["R007","ORD1088","Tablet",         "2024-02-13","",                  649.00],  # BUG
        ["R008","ORD1092","Wireless Mouse", "2024-02-15","Damaged in Transit", 49.99],
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Weekly Return Summary by Product  6 rows × 5 cols = 30 cells
    h2 = ["Product","Units_Sold","Return_Qty","Return_Rate_Pct","Avg_Refund_USD"]
    r2 = [
        ["Laptop",        48,   3,  6.25,  899.00],
        ["Running Shoes",120,   8,  6.67,   89.99],
        ["Headphones",    85, 312,  366.0, 149.00],  # BUG: 312 > 85
        ["Smartwatch",    62,   4,  6.45,  299.00],
        ["USB-C Hub",    200,  11,  5.50,   49.99],
        ["Winter Jacket", 55, 178, 323.6,  189.99],  # BUG: 178 > 55
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "missing",
            "locations": ["row=3,column=Return_Reason","row=5,column=Return_Reason","row=7,column=Return_Reason"],
            "description": "Return_Reason is missing for returns R003 (Headphones), R005 (USB-C Hub), and R007 (Tablet). Reason is mandatory for quality control tracking and supplier chargebacks.",
            "business_context": "E-commerce returns management. Missing reasons prevent defect rate reporting and supplier accountability claims."
        },
        {
            "table": "table2.csv",
            "issue_type": "semantic_anomaly",
            "locations": ["row=3,column=Return_Qty","row=6,column=Return_Qty"],
            "description": "Return_Qty exceeds Units_Sold: Headphones has Return_Qty=312 but only 85 units sold (Return_Rate=366%); Winter Jacket has Return_Qty=178 but only 55 sold (Return_Rate=323%). Likely correct: 3 and 7 respectively — digits were repeated or shifted.",
            "business_context": "Weekly returns analytics. Return quantities exceeding sales volume are physically impossible and would corrupt inventory reconciliation."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 08 — Customer Support Tickets
# table1 (7×7=49): INCONSISTENCY — Priority mixed "High"/"high"/"HIGH"
# table2 (5×6=30): MISSING — Resolution_Time_hrs missing in 2 rows
# ─────────────────────────────────────────────────────────────────────────────
def gen_case08():
    d = BASE / "case08"; d.mkdir(exist_ok=True)

    # table1 — Tickets  7 rows × 7 cols = 49 cells
    h1 = ["TicketID","CustomerID","Category","Created_Date","Priority","Status","Agent"]
    r1 = [
        ["T001","C201","Billing",        "2024-03-01","High",   "Resolved","Alice"],
        ["T002","C202","Technical",      "2024-03-02","high",   "Resolved","Bob"  ],  # BUG
        ["T003","C203","Shipping",       "2024-03-03","Medium", "Resolved","Alice"],
        ["T004","C204","Account Access", "2024-03-04","HIGH",   "Open",    "Carol"],  # BUG
        ["T005","C205","Billing",        "2024-03-05","Low",    "Resolved","Bob"  ],
        ["T006","C206","Technical",      "2024-03-06","High",   "Resolved","Carol"],
        ["T007","C207","Refund",         "2024-03-07","high",   "Pending", "Alice"],  # BUG
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Resolution Metrics  5 rows × 6 cols = 30 cells
    h2 = ["TicketID","Agent","First_Response_hrs","Resolution_Time_hrs","CSAT_Score","Escalated"]
    r2 = [
        ["T001","Alice",  0.5,  4.2, 4.8, False],
        ["T002","Bob",    1.2,   "" , 3.9, False],  # BUG
        ["T003","Alice",  0.8,  2.1, 5.0, False],
        ["T004","Carol",  2.5,   "" , "",  True ],  # BUG (also CSAT missing but we track Resolution_Time)
        ["T005","Bob",    0.3,  1.5, 4.5, False],
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "inconsistency",
            "locations": ["row=2,column=Priority","row=4,column=Priority","row=7,column=Priority"],
            "description": "Priority uses mixed capitalisation: rows 2 and 7 have 'high' (all lower), row 4 has 'HIGH' (all upper). Standard is Title Case 'High'/'Medium'/'Low'. SLA breach monitoring will miss high-priority tickets with wrong case.",
            "business_context": "Support ticket SLA system. Inconsistent priority labels cause high-priority tickets to be excluded from escalation triggers."
        },
        {
            "table": "table2.csv",
            "issue_type": "missing",
            "locations": ["row=2,column=Resolution_Time_hrs","row=4,column=Resolution_Time_hrs"],
            "description": "Resolution_Time_hrs missing for tickets T002 and T004. T002 (Resolved) should have a value; T004 (Open) may be legitimately blank but is required for SLA tracking. Expected T002≈6–8h based on ticket complexity.",
            "business_context": "Customer support KPI dashboard. Missing resolution times skew average handle time and SLA compliance metrics."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 09 — Agricultural Crop Yield
# table1 (6×8=48): SEMANTIC ANOMALY — Yield_tonnes_per_ha negative in 2 rows
# table2 (5×6=30): INCONSISTENCY — Crop names mixed "Wheat"/"wheat"/"WHEAT"
# ─────────────────────────────────────────────────────────────────────────────
def gen_case09():
    d = BASE / "case09"; d.mkdir(exist_ok=True)

    # table1 — Field Yield Records  6 rows × 8 cols = 48 cells
    h1 = ["FieldID","Farm","Crop","Season","Area_ha","Yield_tonnes_per_ha","Rainfall_mm","Fertiliser_kg_per_ha"]
    r1 = [
        ["F01","Greenfield Farm", "Wheat",  "2023 Spring", 120,  5.8, 380, 220],
        ["F02","Sunridge Farm",   "Maize",  "2023 Spring",  85,  8.2, 420, 310],
        ["F03","Valley Farm",     "Wheat",  "2023 Spring", 200, -3.4, 340, 190],  # BUG: negative
        ["F04","Hillside Farm",   "Barley", "2023 Spring",  60,  4.9, 360, 200],
        ["F05","Lakewood Farm",   "Maize",  "2023 Spring",  95, -6.1, 410, 290],  # BUG: negative
        ["F06","Riverside Farm",  "Barley", "2023 Spring",  75,  4.2, 350, 185],
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Crop Reference  5 rows × 6 cols = 30 cells
    h2 = ["Crop","Variety","Min_Yield","Max_Yield","Growing_Days","Region"]
    r2 = [
        ["wheat",   "Winter Wheat",  3.5,  8.5, 240, "Temperate"],  # BUG
        ["Maize",   "Dent Corn",     5.0, 12.0, 120, "Temperate"],
        ["Barley",  "Spring Barley", 3.0,  6.5, 100, "Temperate"],
        ["WHEAT",   "Spring Wheat",  3.0,  7.0, 110, "Temperate"],  # BUG
        ["Soybean", "Roundup Ready", 2.5,  4.0, 130, "Temperate"],
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "semantic_anomaly",
            "locations": ["row=3,column=Yield_tonnes_per_ha","row=5,column=Yield_tonnes_per_ha"],
            "description": "Yield_tonnes_per_ha is negative: F03 (Valley Farm Wheat) = -3.4 t/ha, F05 (Lakewood Farm Maize) = -6.1 t/ha. Yield cannot be negative; correct values are likely 3.4 and 6.1 (minus sign entered in error).",
            "business_context": "Agricultural performance monitoring. Negative yield values corrupt farm subsidy calculations and regional food security forecasts."
        },
        {
            "table": "table2.csv",
            "issue_type": "inconsistency",
            "locations": ["row=1,column=Crop","row=4,column=Crop"],
            "description": "Crop name uses inconsistent capitalisation: row 1 has 'wheat' (all lower), row 4 has 'WHEAT' (all upper). Standard is Title Case 'Wheat'. JOIN operations between table1 and table2 on the Crop column will fail to match these rows.",
            "business_context": "Crop yield reference lookup. Inconsistent crop names break the join between field data and crop benchmarks, preventing yield gap analysis."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
# CASE 10 — Smart Meter Energy Consumption
# table1 (8×6=48): MISSING — kWh_Consumed missing in 3 rows
# table2 (6×5=30): SEMANTIC ANOMALY — kWh values negative in 2 rows
# ─────────────────────────────────────────────────────────────────────────────
def gen_case10():
    d = BASE / "case10"; d.mkdir(exist_ok=True)

    # table1 — Daily Meter Readings  8 rows × 6 cols = 48 cells
    h1 = ["Date","MeterID","Building","Meter_Reading_kWh","kWh_Consumed","Cost_USD"]
    r1 = [
        ["2024-01-08","M01","Office Block A",  15820.4, 142.3, 21.35],
        ["2024-01-09","M01","Office Block A",  15964.2, 143.8, 21.57],
        ["2024-01-10","M01","Office Block A",  16108.5,    "" , ""   ],  # BUG
        ["2024-01-11","M01","Office Block A",  16251.7, 143.2, 21.48],
        ["2024-01-12","M01","Office Block A",  16394.0,    "" , ""   ],  # BUG
        ["2024-01-13","M01","Office Block A",  16537.8, 143.8, 21.57],
        ["2024-01-14","M01","Office Block A",  16680.9,    "" , ""   ],  # BUG
        ["2024-01-15","M01","Office Block A",  16822.5, 141.6, 21.24],
    ]
    write_csv(d/"table1.csv", h1, r1)

    # table2 — Monthly Building Summary  6 rows × 5 cols = 30 cells
    h2 = ["Building","Month","Total_kWh","Avg_Daily_kWh","Monthly_Cost_USD"]
    r2 = [
        ["Office Block A",  "2024-01",  4280.5, 138.1,   642.08],
        ["Office Block B",  "2024-01",  3950.2, 127.4,   592.53],
        ["Warehouse C",     "2024-01", -1820.4, -58.7,  -273.06],  # BUG: negative total
        ["Retail Unit D",   "2024-01",  2140.8,  69.1,   321.12],
        ["Parking Garage E","2024-01",   890.3,  28.7,   133.55],
        ["Data Center F",   "2024-01", -9240.6,-298.1, -1386.09],  # BUG: negative total
    ]
    write_csv(d/"table2.csv", h2, r2)

    save_issue(d/"issue.json", [
        {
            "table": "table1.csv",
            "issue_type": "missing",
            "locations": ["row=3,column=kWh_Consumed","row=5,column=kWh_Consumed","row=7,column=kWh_Consumed"],
            "description": "kWh_Consumed missing for Jan 10, 12, 14. Expected values can be derived from consecutive Meter_Reading_kWh differences: Jan10≈144.3, Jan12≈142.3, Jan14≈143.1 kWh.",
            "business_context": "Smart meter billing system. Missing daily consumption values prevent monthly invoice generation and peak demand analysis."
        },
        {
            "table": "table2.csv",
            "issue_type": "semantic_anomaly",
            "locations": ["row=3,column=Total_kWh","row=6,column=Total_kWh"],
            "description": "Monthly Total_kWh is negative: Warehouse C = -1820.4 kWh, Data Center F = -9240.6 kWh. Energy consumption cannot be negative for a consuming facility. Likely a sign error during data entry; correct values: 1820.4 and 9240.6.",
            "business_context": "Building energy management. Negative consumption corrupts carbon footprint reporting, cost allocation, and utility benchmarking."
        }
    ])

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    random.seed(42)
    gen_case01(); gen_case02(); gen_case03(); gen_case04(); gen_case05()
    gen_case06(); gen_case07(); gen_case08(); gen_case09(); gen_case10()
    print("Done!\n")
    for i in range(1,11):
        p = BASE / f"case{i:02d}"
        issues = json.load(open(p/"issue.json"))
        print(f"case{i:02d}:")
        for iss in issues:
            cells = 0
            with open(p/iss["table"]) as f:
                rows = list(csv.reader(f))
            cols = len(rows[0]); rws = len(rows)-1
            cells = cols * rws
            print(f"  {iss['table']:<12} {cols}col×{rws}row={cells}cells  bug={iss['issue_type']:<20} locations={len(iss['locations'])}")
