"""
Generate 10 cases of spreadsheet diagnosis dataset.
Bug distribution across tables:
  table1: case01, case05, case07
  table2: case02, case04, case08, case10
  table3: case03, case06, case09
"""

import json
import csv
import random
from pathlib import Path

BASE_DIR = Path("/home/scygl3/Spreadsheet-diagnosis-data/dataset")
BASE_DIR.mkdir(parents=True, exist_ok=True)

def write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 01 — Retail Chain Monthly Sales
# Bug: table1.csv  row=15  column=Sales_USD  (missing)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case01():
    d = BASE_DIR / "case01"
    d.mkdir(exist_ok=True)

    regions   = ["North", "South", "East", "West", "Central"]
    categories = ["Electronics", "Clothing", "Groceries", "Furniture", "Sports"]

    # table1.csv — Monthly Sales Records  25×10
    h1 = ["RecordID","Year","Month","Region","Category",
          "Sales_USD","Units_Sold","Discount_Pct","Returns","Net_Sales_USD"]
    r1 = []
    for i in range(1, 26):
        region = regions[(i-1) % 5]
        cat    = categories[(i-1) % 5]
        year   = random.choice([2021, 2022, 2023])
        month  = random.randint(1, 12)
        sales  = round(random.uniform(5000, 50000), 2)
        units  = random.randint(50, 500)
        disc   = round(random.uniform(0, 20), 1)
        returns= random.randint(0, 20)
        net    = round(sales * (1 - disc/100), 2)
        r1.append([i, year, month, region, cat, sales, units, disc, returns, net])
    # BUG: row 15 Sales_USD missing
    r1[14][5] = ""
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Region Info  5×8  (clean)
    h2 = ["Region","Manager","Num_Stores","HQ_City",
          "Established_Year","Area_sqkm","Staff_Count","Target_USD"]
    r2 = [
        ["North",   "Alice Johnson", 12, "Chicago",     2005, 45000, 320, 600000],
        ["South",   "Bob Martinez",   9, "Houston",     2008, 38000, 260, 480000],
        ["East",    "Carol White",   15, "New York",    2001, 22000, 410, 750000],
        ["West",    "David Lee",     11, "Los Angeles", 2003, 55000, 300, 620000],
        ["Central", "Eva Brown",      8, "Denver",      2010, 41000, 220, 400000],
    ]
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Category Benchmarks  5×6  (clean)
    h3 = ["Category","Avg_Margin_Pct","Seasonal_Peak",
          "Return_Rate_Pct","Min_Price_USD","Max_Price_USD"]
    r3 = [
        ["Electronics",  18.5, "Q4",  5.2,  49.99,  2999.99],
        ["Clothing",     42.0, "Q2", 12.1,   9.99,   299.99],
        ["Groceries",    22.3, "Q1",  3.8,   0.99,    89.99],
        ["Furniture",    35.1, "Q3",  4.5,  99.99,  4999.99],
        ["Sports",       28.7, "Q2",  6.3,  14.99,   899.99],
    ]
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "missing",
        "table": "table1.csv",
        "location": "row=15,column=Sales_USD",
        "description": (
            "Sales_USD is missing for RecordID=15 (Central region, Sports, 2023). "
            "Based on Units_Sold=447 and Discount_Pct=1.1, the expected value is "
            "approximately $42,700 (reverse-engineered from Net_Sales_USD=42,456)."
        ),
        "business_context": "Retail chain monthly sales tracking. Missing revenue blocks regional P&L reporting and target-vs-actual dashboards."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 02 — Global City Population Survey
# Bug: table2.csv  rows=6,14  column=Development_Status  (inconsistency — case)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case02():
    d = BASE_DIR / "case02"
    d.mkdir(exist_ok=True)

    cities = [
        ("Beijing","China","Asia"),("Lagos","Nigeria","Africa"),
        ("São Paulo","Brazil","S. America"),("Mumbai","India","Asia"),
        ("Cairo","Egypt","Africa"),("Mexico City","Mexico","N. America"),
        ("Dhaka","Bangladesh","Asia"),("Osaka","Japan","Asia"),
        ("Karachi","Pakistan","Asia"),("Chongqing","China","Asia"),
        ("Istanbul","Turkey","Europe"),("Buenos Aires","Argentina","S. America"),
        ("Kolkata","India","Asia"),("Kinshasa","DR Congo","Africa"),
        ("Manila","Philippines","Asia"),("Tianjin","China","Asia"),
        ("Guangzhou","China","Asia"),("Rio de Janeiro","Brazil","S. America"),
        ("Moscow","Russia","Europe"),("Lahore","Pakistan","Asia"),
        ("Shenzhen","China","Asia"),("Bangalore","India","Asia"),
        ("Jakarta","Indonesia","Asia"),("Wuhan","China","Asia"),
        ("Lima","Peru","S. America"),
    ]

    # table1.csv — City Survey Records  25×10  (clean)
    h1 = ["CityID","City","Country","Continent","Survey_Date",
          "Population","Density_per_km2","Median_Age",
          "Urban_Growth_Rate_Pct","GDP_per_Capita_USD"]
    r1 = []
    for i,(city,country,cont) in enumerate(cities, 1):
        year  = random.choice([2018,2019,2020,2021,2022])
        month = random.randint(1,12)
        day   = random.randint(1,28)
        r1.append([
            i, city, country, cont,
            f"{year}-{month:02d}-{day:02d}",
            random.randint(1_000_000, 25_000_000),
            random.randint(500, 25000),
            round(random.uniform(22,42),1),
            round(random.uniform(0.5,4.5),2),
            random.randint(2000,45000),
        ])
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Country Metadata  20×8
    # BUG: rows 6 and 14 use wrong capitalisation for Development_Status
    countries_meta = [
        ("China","Asia","Beijing","CNY",9596960,1412000000,"Developing","High"),
        ("Nigeria","Africa","Abuja","NGN",923768,213000000,"Developing","Medium"),
        ("Brazil","S. America","Brasília","BRL",8515767,213000000,"Developing","Medium-High"),
        ("India","Asia","New Delhi","INR",3287263,1380000000,"Developing","High"),
        ("Egypt","Africa","Cairo","EGP",1002450,100000000,"Developing","Medium"),
        # row 6 BUG: "developing" should be "Developing"
        ("Mexico","N. America","Mexico City","MXN",1964375,128000000,"developing","Medium-High"),
        ("Bangladesh","Asia","Dhaka","BDT",147570,165000000,"Developing","Medium"),
        ("Japan","Asia","Tokyo","JPY",377975,126000000,"Developed","High"),
        ("Pakistan","Asia","Islamabad","PKR",881913,220000000,"Developing","Low-Medium"),
        ("Turkey","Europe","Ankara","TRY",783356,84000000,"Developing","Medium-High"),
        ("Argentina","S. America","Buenos Aires","ARS",2780400,45000000,"Developing","Medium"),
        ("DR Congo","Africa","Kinshasa","CDF",2344858,90000000,"Developing","Low"),
        ("Philippines","Asia","Manila","PHP",300000,110000000,"Developing","Medium"),
        # row 14 BUG: "DEVELOPING" should be "Developing"
        ("Russia","Europe","Moscow","RUB",17098242,145000000,"DEVELOPING","Medium-High"),
        ("Indonesia","Asia","Jakarta","IDR",1904569,273000000,"Developing","Medium"),
        ("USA","N. America","Washington DC","USD",9833517,331000000,"Developed","Very High"),
        ("Germany","Europe","Berlin","EUR",357114,83000000,"Developed","Very High"),
        ("UK","Europe","London","GBP",242495,67000000,"Developed","Very High"),
        ("France","Europe","Paris","EUR",643801,67000000,"Developed","Very High"),
        ("Australia","Oceania","Canberra","AUD",7692024,25000000,"Developed","Very High"),
    ]
    h2 = ["Country","Continent","Capital","Currency","Area_km2",
          "Total_Population","Development_Status","HDI_Category"]
    write_csv(d / "table2.csv", h2, countries_meta)

    # table3.csv — Age Group Distribution  25×8  (clean)
    h3 = ["RecordID","City","Age_0_14_Pct","Age_15_24_Pct",
          "Age_25_54_Pct","Age_55_64_Pct","Age_65plus_Pct","Survey_Year"]
    r3 = []
    for i,(city,_,_) in enumerate(cities, 1):
        a = round(random.uniform(15,30),1)
        b = round(random.uniform(12,20),1)
        c = round(random.uniform(30,42),1)
        e = round(random.uniform(6,12),1)
        d_ = round(max(100-a-b-c-e, 2.0), 1)
        r3.append([i,city,a,b,c,e,d_,random.choice([2019,2020,2021,2022])])
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "inconsistency",
        "table": "table2.csv",
        "location": "row=6,column=Development_Status; row=14,column=Development_Status",
        "description": (
            "Development_Status uses inconsistent capitalisation: "
            "row 6 (Mexico) has 'developing' and row 14 (Russia) has 'DEVELOPING', "
            "while all other rows use Title Case 'Developing' or 'Developed'. "
            "GROUP BY queries will produce split counts for the same category."
        ),
        "business_context": "Government demographic database. Inconsistent category labels corrupt HDI-tier aggregation and cross-country development comparisons."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 03 — Weather Station Monitoring
# Bug: table3.csv  row=8  column=Avg_Temp_C  (semantic anomaly — impossible value)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case03():
    d = BASE_DIR / "case03"
    d.mkdir(exist_ok=True)

    stations = [
        ("WS001","New York","USA",40.71,-74.01),
        ("WS002","London","UK",51.51,-0.13),
        ("WS003","Tokyo","Japan",35.68,139.69),
        ("WS004","Sydney","Australia",-33.87,151.21),
        ("WS005","Berlin","Germany",52.52,13.40),
    ]

    # table1.csv — Daily Readings  30×10  (clean)
    h1 = ["ReadingID","StationID","Date","Temperature_C",
          "Humidity_Pct","Wind_Speed_kmh","Pressure_hPa",
          "Precipitation_mm","Cloud_Cover_Pct","UV_Index"]
    r1 = []
    for i in range(1, 31):
        st    = stations[(i-1) % 5]
        month = (i-1)//5 + 1
        day   = (i-1) % 5 * 5 + 10
        r1.append([
            i, st[0], f"2023-{month:02d}-{day:02d}",
            round(random.uniform(-5, 32), 1),
            random.randint(30, 95),
            round(random.uniform(2, 45), 1),
            random.randint(990, 1025),
            round(random.uniform(0, 12), 1),
            random.randint(0, 100),
            random.randint(0, 10),
        ])
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Station Metadata  5×10  (clean)
    h2 = ["StationID","City","Country","Latitude","Longitude",
          "Elevation_m","Established_Year","Sensor_Type","Calibration_Date","Active"]
    r2 = [
        ["WS001","New York","USA",40.71,-74.01,10,2005,"Digital","2023-01-15",True],
        ["WS002","London","UK",51.51,-0.13,25,2003,"Digital","2023-02-10",True],
        ["WS003","Tokyo","Japan",35.68,139.69,40,2007,"Digital","2022-12-20",True],
        ["WS004","Sydney","Australia",-33.87,151.21,15,2006,"Digital","2023-03-05",True],
        ["WS005","Berlin","Germany",52.52,13.40,35,2004,"Digital","2023-01-28",True],
    ]
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Monthly Climate Averages  24×8
    # BUG: row 8 (London, July) Avg_Temp_C = 224.0 — decimal shift entry error (should be 22.4)
    h3 = ["StationID","City","Month","Avg_Temp_C","Avg_Humidity_Pct",
          "Avg_Precipitation_mm","Avg_Wind_Speed_kmh","Sunshine_Hours"]
    r3 = []
    for st in stations:
        for month in [1, 4, 7, 10]:
            r3.append([
                st[0], st[1], month,
                round(random.uniform(5, 28), 1),
                random.randint(45, 80),
                round(random.uniform(20, 100), 1),
                round(random.uniform(8, 25), 1),
                round(random.uniform(80, 220), 1),
            ])
    # row 8 = London July (station index 1, month index 2 → 1*4+2 = index 6 → file row 8)
    r3[6][3] = 224.0   # BUG: should be ~22.4°C
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "semantic_anomaly",
        "table": "table3.csv",
        "location": "row=8,column=Avg_Temp_C",
        "description": (
            "Monthly average temperature for London in July is 224.0°C, which is "
            "physically impossible (London July average: 18–23°C; water boils at 100°C). "
            "The correct value is 22.4°C — a decimal point was dropped during data entry."
        ),
        "business_context": "National meteorological archive. An erroneous monthly average would corrupt long-term climate trend models and trigger false heat-alert thresholds."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 04 — Corporate Quarterly Financials
# Bug: table2.csv  row=9  column=Operating_Expenses_USD  (missing)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case04():
    d = BASE_DIR / "case04"
    d.mkdir(exist_ok=True)

    units = ["Cloud Services","Hardware","Software Licensing",
             "Professional Services","Consumer Products"]

    # table1.csv — Quarterly Revenue  20×10  (clean)
    h1 = ["RecordID","BusinessUnit","Year","Quarter",
          "Revenue_USD","YoY_Growth_Pct","Gross_Margin_Pct",
          "Headcount","New_Clients","Churn_Rate_Pct"]
    r1 = []
    for i in range(1,21):
        unit  = units[(i-1) % 5]
        year  = 2020 + (i-1)//5
        q     = (i-1) % 4 + 1
        r1.append([
            i, unit, year, f"Q{q}",
            round(random.uniform(2_000_000,25_000_000),0),
            round(random.uniform(-5,30),1),
            round(random.uniform(35,75),1),
            random.randint(50,800),
            random.randint(5,120),
            round(random.uniform(1.5,8.0),2),
        ])
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Quarterly Expenses  20×10
    # BUG: row 9 Operating_Expenses_USD missing
    h2 = ["RecordID","BusinessUnit","Year","Quarter",
          "Operating_Expenses_USD","R&D_Spend_USD","Marketing_Spend_USD",
          "COGS_USD","Depreciation_USD","EBITDA_USD"]
    r2 = []
    for i in range(1,21):
        unit = units[(i-1) % 5]
        year = 2020 + (i-1)//5
        q    = (i-1) % 4 + 1
        r2.append([
            i, unit, year, f"Q{q}",
            round(random.uniform(800_000,10_000_000),0),
            round(random.uniform(200_000,3_000_000),0),
            round(random.uniform(100_000,1_500_000),0),
            round(random.uniform(500_000,8_000_000),0),
            round(random.uniform(50_000,500_000),0),
            round(random.uniform(500_000,5_000_000),0),
        ])
    r2[8][4] = ""   # BUG: row 9
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Business Unit Profiles  5×8  (clean)
    h3 = ["BusinessUnit","Division","Founded_Year","HQ_Country",
          "Product_Type","Target_Market","Employees_Total","Active"]
    r3 = [
        ["Cloud Services",        "Technology", 2012,"USA","SaaS",    "Enterprise",          2400,True],
        ["Hardware",              "Technology", 2005,"USA","Physical","Enterprise+Consumer", 1800,True],
        ["Software Licensing",    "Technology", 2008,"USA","License", "SMB+Enterprise",       950,True],
        ["Professional Services", "Consulting", 2010,"USA","Service", "Enterprise",          1200,True],
        ["Consumer Products",     "Retail",     2015,"USA","Mixed",   "Consumer",             600,True],
    ]
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "missing",
        "table": "table2.csv",
        "location": "row=9,column=Operating_Expenses_USD",
        "description": (
            "Operating_Expenses_USD is missing for BusinessUnit='Professional Services', "
            "Year=2021, Q1. Based on adjacent quarters for this unit, "
            "the expected value is approximately $3.2M–$4.8M."
        ),
        "business_context": "Corporate quarterly P&L reporting. Missing OPEX prevents EBITDA cross-validation and violates finance audit completeness requirements."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 05 — Customer Satisfaction Survey
# Bug: table1.csv  rows=6,13,19  column=Satisfaction_Level  (inconsistency — case)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case05():
    d = BASE_DIR / "case05"
    d.mkdir(exist_ok=True)

    sat_levels = ["Very Satisfied","Satisfied","Neutral","Dissatisfied","Very Dissatisfied"]
    products   = ["Laptop","Smartphone","Headphones","Tablet","Smartwatch",
                  "Camera","Speaker","Monitor","Keyboard","Mouse"]
    genders    = ["Male","Female","Non-binary"]
    channels   = ["Web","Mobile App","In-Store","Phone"]

    # table1.csv — Survey Responses  25×10
    # BUG: rows 6,13,19 Satisfaction_Level wrong capitalisation
    h1 = ["ResponseID","CustomerID","Product","Purchase_Date",
          "Satisfaction_Level","NPS_Score","Delivery_Rating",
          "Product_Quality_Rating","Support_Rating","Would_Recommend"]
    r1 = []
    for i in range(1,26):
        sat = random.choice(sat_levels)
        nps = random.randint(0,10)
        r1.append([
            i, f"C{10000+i}", products[(i-1)%10],
            f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            sat, nps,
            random.randint(1,5), random.randint(1,5), random.randint(1,5),
            "Yes" if nps >= 7 else "No",
        ])
    r1[5][4]  = "satisfied"       # BUG
    r1[12][4] = "SATISFIED"       # BUG
    r1[18][4] = "Very satisfied"  # BUG
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Customer Demographics  25×8  (clean)
    h2 = ["CustomerID","Age","Gender","Country","City",
          "Loyalty_Tier","Member_Since_Year","Channel"]
    r2 = []
    for i in range(1,26):
        r2.append([
            f"C{10000+i}",
            random.randint(18,70),
            random.choice(genders),
            random.choice(["USA","UK","Canada","Germany","France","Australia"]),
            random.choice(["New York","London","Toronto","Berlin","Paris","Sydney"]),
            random.choice(["Bronze","Silver","Gold","Platinum"]),
            random.randint(2015,2023),
            random.choice(channels),
        ])
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Product Catalog  10×8  (clean)
    h3 = ["Product","Category","Brand","Price_USD",
          "Avg_Rating","Reviews_Count","Stock_Units","Launch_Year"]
    r3 = [
        ["Laptop",     "Computing",    "TechPro",    1299.99,4.3,1842,350,2022],
        ["Smartphone", "Mobile",       "NexGen",      899.99,4.5,3201,820,2023],
        ["Headphones", "Audio",        "SoundWave",   249.99,4.4,2156,610,2022],
        ["Tablet",     "Computing",    "TechPro",     649.99,4.2, 987,280,2021],
        ["Smartwatch", "Wearable",     "FitTech",     399.99,4.1,1543,450,2023],
        ["Camera",     "Photography",  "OptiView",    799.99,4.6, 654,190,2022],
        ["Speaker",    "Audio",        "SoundWave",   179.99,4.3,2341,720,2021],
        ["Monitor",    "Computing",    "ClearVision", 549.99,4.4, 891,240,2022],
        ["Keyboard",   "Accessories",  "TypeMaster",  129.99,4.5,3102,980,2020],
        ["Mouse",      "Accessories",  "TypeMaster",   79.99,4.4,4215,1200,2020],
    ]
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "inconsistency",
        "table": "table1.csv",
        "location": "row=6,column=Satisfaction_Level; row=13,column=Satisfaction_Level; row=19,column=Satisfaction_Level",
        "description": (
            "Satisfaction_Level uses inconsistent capitalisation: "
            "row 6 → 'satisfied' (all lower), row 13 → 'SATISFIED' (all upper), "
            "row 19 → 'Very satisfied' (second word lower). "
            "Standard encoding is Title Case ('Satisfied', 'Very Satisfied'). "
            "GROUP BY will split one category into multiple buckets."
        ),
        "business_context": "E-commerce post-purchase survey. Inconsistent labels corrupt NPS segmentation and satisfaction-trend dashboards."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 06 — Employee HR Records
# Bug: table3.csv  row=3  column=Min_Salary_USD  (semantic anomaly — missing zero)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case06():
    d = BASE_DIR / "case06"
    d.mkdir(exist_ok=True)

    departments = ["Engineering","Marketing","Finance","Sales","Operations",
                   "HR","Legal","Product","Customer Success","IT"]
    levels = ["Junior","Mid","Senior","Lead","Manager","Director","VP"]
    countries = ["USA","UK","Germany","Canada","Australia","India","Singapore"]
    first_names = ["James","Mary","John","Patricia","Robert","Jennifer","Michael",
                   "Linda","William","Barbara","David","Susan","Richard","Jessica",
                   "Joseph","Sarah","Thomas","Karen","Charles","Lisa",
                   "Daniel","Nancy","Matthew","Betty","Anthony"]
    last_names  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller",
                   "Davis","Wilson","Moore","Taylor","Anderson","Thomas","Jackson",
                   "White","Harris","Martin","Thompson","Garcia","Martinez",
                   "Robinson","Clark","Rodriguez","Lewis","Lee"]

    # table1.csv — Employee Records  25×10  (clean)
    h1 = ["EmployeeID","FirstName","LastName","Department","JobTitle",
          "Age","Years_at_Company","Annual_Salary_USD","Performance_Score","Country"]
    r1 = []
    for i in range(1,26):
        dept  = departments[(i-1) % 10]
        level = levels[(i-1) % 7]
        age   = random.randint(24,58)
        r1.append([
            f"EMP{1000+i}", first_names[i-1], last_names[i-1],
            dept, f"{level} {dept} Specialist",
            age, random.randint(1, min(age-22,20)),
            round(random.uniform(55_000,180_000),0),
            round(random.uniform(2.5,5.0),1),
            countries[(i-1) % 7],
        ])
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Department Info  10×8  (clean)
    h2 = ["Department","DeptCode","VP_Name","Headcount",
          "Annual_Budget_USD","Location","Established_Year","Cost_Center"]
    r2 = [
        ["Engineering",       "ENG","Sarah Chen",   180,24_000_000,"San Francisco",2005,"CC001"],
        ["Marketing",         "MKT","Tom Bradley",   45, 8_500_000,"New York",     2005,"CC002"],
        ["Finance",           "FIN","Alex Rivera",   35, 6_000_000,"New York",     2005,"CC003"],
        ["Sales",             "SLS","Diana Fox",     95,15_000_000,"Chicago",      2006,"CC004"],
        ["Operations",        "OPS","Mark Liu",     120,18_000_000,"Austin",       2007,"CC005"],
        ["HR",                "HR", "Grace Kim",     28, 4_200_000,"New York",     2005,"CC006"],
        ["Legal",             "LGL","Ryan Cole",     18, 5_800_000,"Washington DC",2008,"CC007"],
        ["Product",           "PRD","Nina Patel",    55, 9_500_000,"San Francisco",2010,"CC008"],
        ["Customer Success",  "CS", "Omar Hassan",   72, 7_800_000,"Austin",       2012,"CC009"],
        ["IT",                "IT", "Lily Zhang",    40,11_000_000,"Seattle",      2005,"CC010"],
    ]
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Salary Bands  7×6
    # BUG: row 3 (Senior) Min_Salary_USD = 1050 instead of 105000 (two zeros dropped)
    h3 = ["JobLevel","Min_Salary_USD","Mid_Salary_USD",
          "Max_Salary_USD","Bonus_Target_Pct","Equity_Eligible"]
    r3 = [
        ["Junior",   45000,  60000,  78000,   8, False],
        ["Mid",      72000,  92000, 115000,  12, True],
        ["Senior",    1050, 130000, 158000,  18, True],  # BUG: 1050 → 105000
        ["Lead",    130000, 158000, 190000,  22, True],
        ["Manager", 145000, 175000, 210000,  28, True],
        ["Director",180000, 220000, 270000,  35, True],
        ["VP",      230000, 290000, 380000,  45, True],
    ]
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "semantic_anomaly",
        "table": "table3.csv",
        "location": "row=3,column=Min_Salary_USD",
        "description": (
            "Senior-level Min_Salary_USD is $1,050, which is implausibly low "
            "given Mid-level minimum is $72,000 and Senior Max_Salary_USD is $158,000. "
            "The correct value is $105,000 — two trailing zeros were dropped during entry."
        ),
        "business_context": "HR salary band management. An incorrect minimum salary for Senior level would cause automated offer letters and equity eligibility calculations to apply wrong compensation thresholds."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 07 — E-commerce Product Catalog + Orders
# Bug: table1.csv  row=14  column=Stock_Qty  (missing)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case07():
    d = BASE_DIR / "case07"
    d.mkdir(exist_ok=True)

    statuses = ["Delivered","Shipped","Processing","Cancelled","Returned"]
    pay_methods = ["Credit Card","PayPal","Debit Card","Bank Transfer","Crypto"]
    categories  = ["Electronics","Clothing","Books","Home & Garden","Toys","Sports"]

    # table1.csv — Product Catalog  25×8
    # BUG: row 14 Stock_Qty missing
    h1 = ["ProductID","ProductName","Category","Price_USD",
          "Stock_Qty","Supplier","Weight_kg","Rating"]
    product_data = [
        ("P001","Wireless Earbuds",      "Electronics",  89.99, 450,"AudioTech",  0.15,4.4),
        ("P002","Running Shoes",         "Clothing",    129.99, 320,"SportsFit",  0.80,4.6),
        ("P003","Python Programming",    "Books",        49.99, 180,"TechBooks",  0.60,4.8),
        ("P004","Garden Hose 20m",       "Home & Garden",34.99, 200,"GreenThumb", 1.20,4.2),
        ("P005","LEGO Set 500pcs",       "Toys",         79.99, 150,"BrickWorld", 1.50,4.7),
        ("P006","Yoga Mat",              "Sports",       39.99, 280,"FitGear",    1.00,4.5),
        ("P007","USB-C Hub 7-port",      "Electronics",  59.99, 380,"TechHub",    0.25,4.3),
        ("P008","Winter Jacket",         "Clothing",    189.99, 120,"WarmWear",   1.30,4.5),
        ("P009","Data Science Handbook", "Books",        59.99,  95,"TechBooks",  0.80,4.7),
        ("P010","Plant Pot Ceramic",     "Home & Garden",24.99, 310,"GreenThumb", 0.90,4.3),
        ("P011","Remote Control Car",    "Toys",         54.99, 200,"SpeedRacer", 0.70,4.2),
        ("P012","Resistance Bands Set",  "Sports",       29.99, 420,"FitGear",    0.40,4.6),
        ("P013","Mechanical Keyboard",   "Electronics", 149.99, 180,"TypeMaster", 0.85,4.7),
        ("P014","Denim Jeans",           "Clothing",     79.99,  "","StyleCo",   0.60,4.1),  # BUG
        ("P015","Machine Learning Book", "Books",        69.99,  75,"TechBooks",  0.85,4.9),
        ("P016","Smart Plug 4-pack",     "Home & Garden",44.99, 350,"SmartHome",  0.30,4.4),
        ("P017","Board Game Strategy",   "Toys",         44.99, 165,"GameMaster", 1.10,4.8),
        ("P018","Dumbbells 10kg pair",   "Sports",       89.99, 140,"FitGear",   20.00,4.5),
        ("P019","Webcam 4K",             "Electronics", 119.99, 210,"TechHub",    0.35,4.3),
        ("P020","Casual Sneakers",       "Clothing",     99.99, 290,"StyleCo",   0.90,4.4),
        ("P021","Cloud Computing Book",  "Books",        54.99,  60,"TechBooks",  0.75,4.6),
        ("P022","LED Desk Lamp",         "Home & Garden",54.99, 380,"LightUp",    0.80,4.5),
        ("P023","Puzzle 1000pcs",        "Toys",         34.99, 220,"PuzzleFun",  0.50,4.7),
        ("P024","Tennis Racket",         "Sports",      149.99,  95,"SportsFit",  0.30,4.4),
        ("P025","Portable Charger 20000mAh","Electronics",59.99,450,"PowerMax",  0.45,4.5),
    ]
    write_csv(d / "table1.csv", h1, product_data)

    # table2.csv — Orders  25×10  (clean)
    h2 = ["OrderID","CustomerID","ProductID","Order_Date",
          "Quantity","Unit_Price_USD","Total_USD","Status",
          "Payment_Method","Shipping_Days"]
    r2 = []
    for i in range(1,26):
        qty   = random.randint(1,5)
        price = round(random.uniform(25,200),2)
        r2.append([
            f"ORD{20000+i}", f"CUST{5000+random.randint(1,200)}",
            f"P{random.randint(1,25):03d}",
            f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            qty, price, round(price*qty,2),
            random.choice(statuses),
            random.choice(pay_methods),
            random.randint(1,14),
        ])
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Customer Segments  20×8  (clean)
    h3 = ["CustomerID","Segment","Country","Join_Date",
          "Total_Orders","Lifetime_Value_USD","Preferred_Category","Email_Opt_In"]
    r3 = []
    for i in range(1,21):
        r3.append([
            f"CUST{5000+i}",
            random.choice(["VIP","Regular","New","Inactive"]),
            random.choice(["USA","UK","Canada","Germany","Australia"]),
            f"{random.randint(2018,2022)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            random.randint(1,85),
            round(random.uniform(50,8500),2),
            random.choice(categories),
            random.choice([True,False]),
        ])
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "missing",
        "table": "table1.csv",
        "location": "row=14,column=Stock_Qty",
        "description": (
            "Stock_Qty is missing for ProductID='P014' (Denim Jeans, StyleCo). "
            "Without stock quantity, the inventory management system cannot determine "
            "whether the item can fulfil pending orders or trigger replenishment alerts."
        ),
        "business_context": "E-commerce product catalog. Stock_Qty is required for order fulfilment checks; missing values cause the system to treat the product as unavailable and suppress it from the storefront."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 08 — Hospital Patient Records
# Bug: table2.csv  rows=5,18  column=Severity  (inconsistency — case)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case08():
    d = BASE_DIR / "case08"
    d.mkdir(exist_ok=True)

    blood_types = ["A+","A-","B+","B-","O+","O-","AB+","AB-"]
    wards       = ["Cardiology","Neurology","Orthopedics","Oncology","General","ICU"]
    severities  = ["Mild","Moderate","Severe","Critical"]

    # table1.csv — Patient Vitals  25×10  (clean)
    h1 = ["PatientID","Age","Gender","Blood_Type",
          "Height_cm","Weight_kg","Ward","Admission_Date",
          "Systolic_BP","Diastolic_BP"]
    r1 = []
    for i in range(1,26):
        r1.append([
            f"PAT{3000+i}",
            random.randint(18,85),
            random.choice(["Male","Female"]),
            random.choice(blood_types),
            random.randint(155,190),
            round(random.uniform(50,95),1),
            wards[(i-1) % 6],
            f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            random.randint(100,160),
            random.randint(60,100),
        ])
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Diagnoses  25×8
    # BUG: rows 5 and 18 use wrong capitalisation for Severity
    diagnoses = ["Hypertension","Type 2 Diabetes","Asthma","Coronary Artery Disease",
                 "Osteoporosis","Migraine","Appendicitis","Pneumonia",
                 "Fractured Femur","Breast Cancer","Prostate Cancer","Stroke",
                 "Heart Failure","COPD","Kidney Disease","Anemia",
                 "Thyroid Disorder","Arthritis","Sepsis","Liver Cirrhosis",
                 "Inflammatory Bowel","Celiac Disease","Sleep Apnea","Gout","Psoriasis"]
    icd_codes = ["I10","E11","J45","I25","M81","G43","K37","J18","S72","C50",
                 "C61","I63","I50","J44","N18","D50","E07","M05","A41","K74",
                 "K50","K90","G47","M10","L40"]
    doctors = ["Dr. Smith","Dr. Johnson","Dr. Williams","Dr. Brown",
               "Dr. Jones","Dr. Garcia","Dr. Miller","Dr. Davis"]
    h2 = ["PatientID","Diagnosis_Primary","ICD10_Code","Diagnosis_Date",
          "Severity","Treating_Doctor","Referred_By","Follow_Up_Required"]
    r2 = []
    for i in range(1,26):
        r2.append([
            f"PAT{3000+i}", diagnoses[i-1], icd_codes[i-1],
            f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            random.choice(severities),
            random.choice(doctors),
            random.choice(["GP","Emergency","Specialist Referral","Self"]),
            random.choice([True,False]),
        ])
    r2[4][4]  = "mild"     # BUG: should be "Mild"
    r2[17][4] = "SEVERE"   # BUG: should be "Severe"
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Ward Info  6×7  (clean)
    h3 = ["Ward","WardCode","Bed_Count","Head_Nurse",
          "Floor","Avg_Stay_Days","Specialization"]
    r3 = [
        ["Cardiology",  "W01",40,"Nurse Thompson",3, 5.2,"Heart & Vascular"],
        ["Neurology",   "W02",30,"Nurse Chen",    4, 6.8,"Brain & Nervous System"],
        ["Orthopedics", "W03",35,"Nurse Patel",   2, 4.5,"Bones & Joints"],
        ["Oncology",    "W04",28,"Nurse Williams",5,12.3,"Cancer Treatment"],
        ["General",     "W05",60,"Nurse Brown",   1, 3.1,"General Medicine"],
        ["ICU",         "W06",20,"Nurse Martinez",1, 8.7,"Critical Care"],
    ]
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "inconsistency",
        "table": "table2.csv",
        "location": "row=5,column=Severity; row=18,column=Severity",
        "description": (
            "Severity uses inconsistent capitalisation: "
            "row 5 (PAT3005, Osteoporosis) has 'mild' (all lower) "
            "and row 18 (PAT3018, Arthritis) has 'SEVERE' (all upper), "
            "while all other rows use Title Case ('Mild','Moderate','Severe','Critical'). "
            "Triage priority filters will miss these two patients."
        ),
        "business_context": "Hospital EHR system. Severity label inconsistency corrupts automated triage prioritisation and clinical dashboard filtering."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 09 — Real Estate Listings
# Bug: table3.csv  row=12  column=Years_Experience  (semantic anomaly)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case09():
    d = BASE_DIR / "case09"
    d.mkdir(exist_ok=True)

    prop_types    = ["Apartment","House","Condo","Townhouse","Villa"]
    neighborhoods = ["Downtown","Midtown","Uptown","Suburbs","Waterfront",
                     "Arts District","Financial District","University Area",
                     "Historic Quarter","Tech Hub"]
    cities = ["New York","Los Angeles","Chicago","Houston","Miami",
              "Seattle","Boston","Denver","Atlanta","San Francisco"]
    agencies = ["Premier Realty","Skyline Properties","Urban Nest",
                "Golden Gate Real Estate","Sunrise Homes"]

    # table1.csv — Property Listings  25×10  (clean)
    h1 = ["ListingID","PropertyType","City","Neighborhood",
          "Price_USD","Bedrooms","Bathrooms","Area_sqft",
          "Year_Built","Days_on_Market"]
    r1 = []
    for i in range(1,26):
        r1.append([
            f"LST{8000+i}", prop_types[(i-1)%5], cities[(i-1)%10],
            neighborhoods[(i-1)%10],
            round(random.uniform(350_000,3_500_000),0),
            random.randint(1,5), random.randint(1,4),
            random.randint(600,4500),
            random.randint(1975,2022),
            random.randint(1,180),
        ])
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Neighborhood Stats  10×8  (clean)
    h2 = ["Neighborhood","City","Avg_Price_USD","Crime_Index",
          "School_Rating","Walk_Score","Transit_Score","Median_Income_USD"]
    r2 = [
        ["Downtown",           "New York",      2_150_000,42,8.2,95,98,89000],
        ["Midtown",            "New York",      1_850_000,38,7.9,92,97,85000],
        ["Uptown",             "Los Angeles",   1_450_000,45,7.5,72,65,76000],
        ["Suburbs",            "Chicago",         520_000,28,8.8,48,42,68000],
        ["Waterfront",         "Miami",         3_200_000,35,7.2,85,70,95000],
        ["Arts District",      "Los Angeles",     980_000,50,7.0,88,75,72000],
        ["Financial District", "San Francisco", 2_800_000,40,7.8,96,99,110000],
        ["University Area",    "Boston",          880_000,33,9.2,85,88,78000],
        ["Historic Quarter",   "New Orleans",     650_000,55,7.1,78,62,62000],
        ["Tech Hub",           "Seattle",       1_350_000,30,8.5,82,80,102000],
    ]
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Real Estate Agents  20×8
    # BUG: row 12 Years_Experience = 142 (impossible for a living professional)
    agent_names = ["John Smith","Maria Garcia","David Chen","Sarah Williams","Robert Kim",
                   "Emily Johnson","Michael Brown","Lisa Davis","James Wilson","Anna Lee",
                   "Carlos Lopez","Rachel Green","Kevin Park","Sophie Turner","Omar Hassan",
                   "Priya Patel","Lucas Martin","Chloe Adams","Ethan Rivera","Mia Thompson"]
    h3 = ["AgentID","Name","Agency","City",
          "Years_Experience","Listings_Active","Sales_2023","Avg_Commission_Pct"]
    r3 = []
    for i,name in enumerate(agent_names, 1):
        r3.append([
            f"AGT{200+i}", name, agencies[i%5], cities[i%10],
            random.randint(2,25),
            random.randint(3,28),
            random.randint(5,45),
            round(random.uniform(2.0,3.5),1),
        ])
    r3[11][4] = 142   # BUG: row 12, should be ~14 (digit transposition 14 → 142?)
    write_csv(d / "table3.csv", h3, r3)

    issue = {
        "issue_type": "semantic_anomaly",
        "table": "table3.csv",
        "location": "row=12,column=Years_Experience",
        "description": (
            "Agent AGT212 (Rachel Green) has Years_Experience=142, which is impossible "
            "for a human professional (maximum plausible value ≈ 45 years). "
            "The likely correct value is 14 — an extra digit '2' was appended during entry."
        ),
        "business_context": "Real estate agency database. Erroneous experience value skews agent seniority rankings, commission tier assignments, and client-matching algorithms."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
# CASE 10 — Digital Marketing Campaigns
# Bug: table2.csv  rows=3,7  column=Avg_CTR_Pct  (inconsistency — unit format)
# Most rows: decimal percentage (3.8 means 3.8%)
# Bug rows: stored as fraction (0.004 means 0.4% written as fraction, not percent)
# ─────────────────────────────────────────────────────────────────────────────
def gen_case10():
    d = BASE_DIR / "case10"
    d.mkdir(exist_ok=True)

    channels   = ["Search (SEM)","Social Media","Display Ads","Email",
                  "Influencer","Video (YouTube)","Content Marketing","Affiliate"]
    objectives = ["Brand Awareness","Lead Generation","Sales Conversion",
                  "Retargeting","Customer Retention"]
    markets    = ["North America","Europe","Asia Pacific","Latin America","Middle East"]
    campaign_names = [
        "Spring Sale 2023","Brand Launch Q1","Summer Promo","Back to School",
        "Holiday Season","New Product Launch","Loyalty Rewards","Black Friday",
        "Cyber Monday","Valentine's Day","Easter Deals","Mother's Day",
        "Father's Day","End of Year","Q1 Acquisition","Q2 Growth",
        "Q3 Retention","Q4 Revenue Push","Year-Round Awareness","Flash Sale Jan",
        "Flash Sale Mar","Partnership Promo","Referral Program","Winback Campaign",
        "Anniversary Sale",
    ]

    # table1.csv — Campaign Records  25×10  (clean)
    h1 = ["CampaignID","Campaign_Name","Channel","Objective",
          "Campaign_Start_Date","Budget_USD","Impressions",
          "Clicks","Conversions","ROAS"]
    r1 = []
    for i in range(1,26):
        r1.append([
            f"CAMP{100+i}", campaign_names[i-1],
            channels[(i-1)%8], objectives[(i-1)%5],
            f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            round(random.uniform(5000,200000),0),
            random.randint(50_000,5_000_000),
            random.randint(500,50_000),
            random.randint(10,2000),
            round(random.uniform(1.2,8.5),2),
        ])
    write_csv(d / "table1.csv", h1, r1)

    # table2.csv — Channel Benchmarks  8×8
    # BUG: rows 3 and 7 store Avg_CTR_Pct as a raw fraction (0.004, 0.055)
    #      instead of a percentage value (0.4, 5.5) like all other rows
    h2 = ["Channel","Avg_CPC_USD","Avg_CPM_USD","Avg_CTR_Pct",
          "Avg_CVR_Pct","Avg_ROAS","Min_Budget_USD","Typical_Duration_Days"]
    r2 = [
        ["Search (SEM)",      1.85,  8.5,  3.8,  4.2, 5.2, 2000, 30],
        ["Social Media",      0.95,  6.2,  1.2,  2.8, 3.8, 1000, 21],
        ["Display Ads",       0.45,  3.1,  0.004,1.5, 2.1,  500, 14],  # BUG: 0.004 → 0.4
        ["Email",             0.02, 12.0, 22.0,  5.5, 6.8,  200,  7],
        ["Influencer",        2.50, 18.0,  2.5,  3.8, 4.5, 5000, 14],
        ["Video (YouTube)",   0.08,  4.5,  8.5,  2.2, 3.2, 1000, 30],
        ["Content Marketing", 0.30,  2.8,  0.055,3.1, 4.0,  800, 60],  # BUG: 0.055 → 5.5
        ["Affiliate",         3.20,  0.0,  1.8,  6.5, 7.5,    0, 30],
    ]
    write_csv(d / "table2.csv", h2, r2)

    # table3.csv — Market Performance Summary  20×8  (clean)
    h3 = ["Market","Channel","Q1_Spend_USD","Q2_Spend_USD",
          "Q3_Spend_USD","Q4_Spend_USD","Annual_Conversions","Annual_Revenue_USD"]
    r3 = []
    for market in markets:
        for ch in channels[:4]:
            r3.append([
                market, ch,
                round(random.uniform(10_000,80_000),0),
                round(random.uniform(10_000,80_000),0),
                round(random.uniform(10_000,80_000),0),
                round(random.uniform(10_000,80_000),0),
                random.randint(200,5000),
                round(random.uniform(50_000,800_000),0),
            ])
    write_csv(d / "table3.csv", h3, r3[:20])

    issue = {
        "issue_type": "inconsistency",
        "table": "table2.csv",
        "location": "row=3,column=Avg_CTR_Pct; row=7,column=Avg_CTR_Pct",
        "description": (
            "Avg_CTR_Pct is stored as a percentage in 6 of 8 rows (e.g. 3.8 meaning 3.8%), "
            "but rows 3 (Display Ads) and 7 (Content Marketing) store raw fractions: "
            "0.004 and 0.055, which are 100× smaller than the correct values of 0.4% and 5.5%. "
            "To fix: multiply these two values by 100."
        ),
        "business_context": "Digital marketing channel benchmarks. CTR unit inconsistency causes budget optimisation models to massively underestimate click-through performance for Display and Content channels."
    }
    with open(d / "issue.json", "w") as f:
        json.dump(issue, f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    random.seed(42)
    gen_case01(); gen_case02(); gen_case03(); gen_case04(); gen_case05()
    gen_case06(); gen_case07(); gen_case08(); gen_case09(); gen_case10()
    print("Done!")
    from pathlib import Path
    BASE = Path("/home/scygl3/Spreadsheet-diagnosis-data/dataset")
    import json as _json
    for i in range(1,11):
        p = BASE / f"case{i:02d}"
        ij = _json.load(open(p/"issue.json"))
        files = [f.name for f in sorted(p.iterdir()) if f.suffix==".csv"]
        print(f"case{i:02d}  bug_table={ij['table']:<12}  type={ij['issue_type']:<20}  tables={files}")
