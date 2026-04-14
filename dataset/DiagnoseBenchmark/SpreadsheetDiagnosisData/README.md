# Spreadsheet Diagnosis Dataset

A benchmark dataset for evaluating automated spreadsheet data quality diagnosis. It contains two sub-datasets of varying table sizes, each with 10 cases. Every case includes realistic business data across 2–5 CSV tables, with intentionally planted data quality bugs.

## Bug Types

This dataset covers three categories of data quality bugs commonly found in real-world spreadsheets.

---

### 1. Missing

A required cell contains no value. The absence may be due to data entry omission, failed ETL pipelines, or export errors. Missing values silently break aggregations, joins, and downstream calculations.

**Characteristics**
- The cell is empty or contains a null/blank marker
- Other columns in the same row are intact, making the omission detectable by cross-referencing
- The correct value can often be inferred from adjacent rows or related columns

**Example**

| RecordID | Region  | Units_Sold | Discount_Pct | Sales_USD | Net_Sales_USD |
|----------|---------|-----------|--------------|-----------|---------------|
| 14       | West    | 377        | 13.8         | 17,147.65 | 14,781.27     |
| **15**   | Central | 447        | 1.1          | *(blank)* | 42,456.13     |
| 16       | North   | 312        | 8.5          | 23,840.00 | 21,813.60     |

Row 15 has `Units_Sold`, `Discount_Pct`, and `Net_Sales_USD` all populated, so `Sales_USD` can be recovered: `Net_Sales_USD ÷ (1 − Discount_Pct / 100) ≈ $42,927`.

---

### 2. Inconsistency

Values in the same column represent the same concept but use different formats, units, or spellings. Each individual value may look valid in isolation; the problem only becomes apparent when comparing rows.

**Common sub-types**
| Sub-type | Example |
|----------|---------|
| Label capitalisation | `"Satisfied"` vs `"satisfied"` vs `"SATISFIED"` |
| Date format | `"2024-03-15"` (ISO 8601) vs `"15/03/2024"` (DD/MM/YYYY) |
| Unit mismatch | Weight column mixing `kg` and `lbs` |
| Category alias | `"Technology"` vs `"Tech"` vs `"IT"` |

**Example — mixed date format**

| ApptID | Doctor     | Appointment_Date | Fee_USD |
|--------|------------|-----------------|---------|
| A001   | Dr. Adams  | 2024-02-10      | 150     |
| A002   | Dr. Brown  | **12/02/2024**  | 200     |
| A003   | Dr. Chen   | 2024-02-14      | 130     |
| A004   | Dr. Davis  | **17/02/2024**  | 90      |

Rows A002 and A004 use `DD/MM/YYYY` while the rest use `YYYY-MM-DD`. Sorting by `Appointment_Date` as a string will place these rows out of chronological order, and date arithmetic will silently produce wrong results.

---

### 3. Semantic Anomaly

A value is syntactically correct (the right data type, no missing marker) but is logically impossible or wildly implausible given the domain. These bugs are the hardest to detect with schema validation alone and require domain knowledge or range checks.

**Common causes**
- Decimal point shift: `18.7 °C` entered as `187 °C`
- Dropped digits: `$105,000` entered as `$1,050`
- Extra digits: `14 years` entered as `142 years`
- Sign error: positive yield `-3.4 t/ha`

**Example — impossible temperature**

| StationID | City   | Month | Avg_Temp_C | Avg_Humidity_Pct |
|-----------|--------|-------|-----------|-----------------|
| WS002     | London | 4     | 12.1      | 72              |
| WS002     | London | 7     | **224.0** | 68              |
| WS002     | London | 10    | 13.5      | 78              |

`224.0 °C` is above the boiling point of water and far outside any plausible outdoor temperature. The surrounding rows and real-world knowledge confirm the correct value is `22.4 °C` (decimal point dropped).

---

## `dataset_median` — Medium-Sized Tables

Each case has **3 tables** (200–300 cells each). Exactly **one table** contains a bug, which appears at **1–3 locations** within that table.

### Case 01 — Retail Chain Monthly Sales

| File | Size | Role |
|------|------|------|
| `table1.csv` | 25 × 10 | Monthly sales records by region and category |
| `table2.csv` | 5 × 8 | Region metadata (manager, stores, targets) |
| `table3.csv` | 5 × 6 | Product category benchmarks |

**Bug — `table1.csv`**
- **Type:** `missing`
- **Location:** `row=15, column=Sales_USD`
- **Detail:** `Sales_USD` is blank for RecordID 15 (Central region, Sports, 2023). The expected value is approximately $42,700, derivable from `Net_Sales_USD` ÷ (1 − `Discount_Pct` / 100).

---

### Case 02 — Global City Population Survey

| File | Size | Role |
|------|------|------|
| `table1.csv` | 25 × 10 | City-level census records |
| `table2.csv` | 20 × 8 | Country metadata including development status |
| `table3.csv` | 25 × 8 | Age group distribution per city |

**Bug — `table2.csv`**
- **Type:** `inconsistency`
- **Location:** `row=6, column=Development_Status`; `row=14, column=Development_Status`
- **Detail:** Most rows use Title Case (`"Developing"`, `"Developed"`), but row 6 (Mexico) has `"developing"` and row 14 (Russia) has `"DEVELOPING"`. GROUP BY on this column will produce three separate buckets for the same category.

---

### Case 03 — Weather Station Monitoring

| File | Size | Role |
|------|------|------|
| `table1.csv` | 30 × 10 | Daily sensor readings across 5 stations |
| `table2.csv` | 5 × 10 | Station metadata (location, calibration dates) |
| `table3.csv` | 20 × 8 | Monthly climate averages per station |

**Bug — `table3.csv`**
- **Type:** `semantic_anomaly`
- **Location:** `row=8, column=Avg_Temp_C`
- **Detail:** London's July average temperature is recorded as `224.0 °C`, which is physically impossible (water boils at 100 °C; London July average is 18–23 °C). The correct value is `22.4 °C` — a decimal point was dropped during entry.

---

### Case 04 — Corporate Quarterly Financials

| File | Size | Role |
|------|------|------|
| `table1.csv` | 20 × 10 | Quarterly revenue by business unit |
| `table2.csv` | 20 × 10 | Quarterly operating expenses |
| `table3.csv` | 5 × 8 | Business unit profiles |

**Bug — `table2.csv`**
- **Type:** `missing`
- **Location:** `row=9, column=Operating_Expenses_USD`
- **Detail:** `Operating_Expenses_USD` is blank for Professional Services, Q1 2021. Adjacent quarters suggest the expected value is approximately $3.2M–$4.8M. The missing value prevents EBITDA cross-validation and violates audit completeness requirements.

---

### Case 05 — Customer Satisfaction Survey

| File | Size | Role |
|------|------|------|
| `table1.csv` | 25 × 10 | Post-purchase survey responses |
| `table2.csv` | 25 × 8 | Customer demographic profiles |
| `table3.csv` | 10 × 8 | Product catalog |

**Bug — `table1.csv`**
- **Type:** `inconsistency`
- **Location:** `row=6`; `row=13`; `row=19` — all in `column=Satisfaction_Level`
- **Detail:** The standard encoding is Title Case. Row 6 has `"satisfied"` (all lower), row 13 has `"SATISFIED"` (all upper), and row 19 has `"Very satisfied"` (mixed). Filtering for `"Satisfied"` will silently exclude these three responses.

---

### Case 06 — Employee HR Records

| File | Size | Role |
|------|------|------|
| `table1.csv` | 25 × 10 | Employee directory |
| `table2.csv` | 10 × 8 | Department information |
| `table3.csv` | 7 × 6 | Salary bands by job level |

**Bug — `table3.csv`**
- **Type:** `semantic_anomaly`
- **Location:** `row=3, column=Min_Salary_USD`
- **Detail:** The Senior-level minimum salary is `$1,050`, which is implausibly low given that Mid-level minimum is `$72,000` and Senior maximum is `$158,000`. The correct value is `$105,000` — two trailing zeros were dropped during entry.

---

### Case 07 — E-commerce Product Catalog

| File | Size | Role |
|------|------|------|
| `table1.csv` | 25 × 8 | Product catalog with stock levels |
| `table2.csv` | 25 × 10 | Order records |
| `table3.csv` | 20 × 8 | Customer segments |

**Bug — `table1.csv`**
- **Type:** `missing`
- **Location:** `row=14, column=Stock_Qty`
- **Detail:** `Stock_Qty` is blank for ProductID `P014` (Denim Jeans, StyleCo). Without a stock quantity, the system cannot determine fulfilment availability and will suppress the product from the storefront.

---

### Case 08 — Hospital Patient Records

| File | Size | Role |
|------|------|------|
| `table1.csv` | 25 × 10 | Patient vitals at admission |
| `table2.csv` | 25 × 8 | Diagnosis records |
| `table3.csv` | 6 × 7 | Ward information |

**Bug — `table2.csv`**
- **Type:** `inconsistency`
- **Location:** `row=5, column=Severity`; `row=18, column=Severity`
- **Detail:** Row 5 (PAT3005, Osteoporosis) has `"mild"` and row 18 (PAT3018, Arthritis) has `"SEVERE"`. All other rows use Title Case (`"Mild"`, `"Moderate"`, `"Severe"`, `"Critical"`). Triage priority filters will silently miss these two patients.

---

### Case 09 — Real Estate Listings

| File | Size | Role |
|------|------|------|
| `table1.csv` | 25 × 10 | Property listings |
| `table2.csv` | 10 × 8 | Neighborhood statistics |
| `table3.csv` | 20 × 8 | Real estate agent profiles |

**Bug — `table3.csv`**
- **Type:** `semantic_anomaly`
- **Location:** `row=12, column=Years_Experience`
- **Detail:** Agent AGT212 (Rachel Green) has `Years_Experience = 142`, which is impossible for a living professional. The plausible maximum is ~45 years. The correct value is likely `14` — an extra digit `2` was appended during entry.

---

### Case 10 — Digital Marketing Campaign Performance

| File | Size | Role |
|------|------|------|
| `table1.csv` | 25 × 10 | Campaign records |
| `table2.csv` | 8 × 8 | Channel benchmark metrics |
| `table3.csv` | 20 × 8 | Market-level spend summary |

**Bug — `table2.csv`**
- **Type:** `inconsistency`
- **Location:** `row=3, column=Avg_CTR_Pct`; `row=7, column=Avg_CTR_Pct`
- **Detail:** Six of eight rows store click-through rate as a percentage value (e.g. `3.8` meaning 3.8 %), but row 3 (Display Ads) stores `0.004` and row 7 (Content Marketing) stores `0.055` — raw fractions that are 100× smaller. Correct values: `0.4` and `5.5`.

---

## `dataset_small` — Small Tables

Each case has **2 tables** (≤ 50 cells each). **Every table** contains a bug, and each bug appears at **2–3 locations** within its table. The two tables in a case may have different bug types.

### Case 01 — Coffee Shop Daily Sales

| File | Size | Role |
|------|------|------|
| `table1.csv` | 8 × 6 | Daily sales summary (Mon–Sat) |
| `table2.csv` | 6 × 5 | Daily payment method breakdown |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `missing` | `row=3`, `row=5`, `row=6` — `Revenue_USD` | Revenue is blank for Wednesday, Friday, and Saturday. Expected values (~$1,012 / $1,392 / $1,816) are derivable from `Customers × Avg_Order_USD`. |
| `table2.csv` | `inconsistency` | `row=2`, `row=4` — `Payment_Method_Primary` | Rows 2 and 4 have `"cash"` and `"CASH"` instead of the standard `"Cash"`. |

---

### Case 02 — School Exam Results

| File | Size | Role |
|------|------|------|
| `table1.csv` | 7 × 7 | Per-student scores in three subjects |
| `table2.csv` | 6 × 5 | Student demographic and grade records |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `semantic_anomaly` | `row=5`, `row=7` — `English_Score` | Scores of `149` and `174` exceed the maximum of 100. Correct values are likely `49` and `74` (a leading `1` was prepended in error). |
| `table2.csv` | `missing` | `row=2`, `row=4`, `row=5` — `Grade` | Grade is blank for students S002, S004, and S005. Expected: B, D, and B respectively. |

---

### Case 03 — Hospital Outpatient Appointments

| File | Size | Role |
|------|------|------|
| `table1.csv` | 8 × 6 | Appointment schedule |
| `table2.csv` | 6 × 5 | Patient vitals at appointment |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `inconsistency` | `row=2`, `row=4`, `row=6` — `Appointment_Date` | Three rows use `DD/MM/YYYY` (`"12/02/2024"`, `"17/02/2024"`, `"22/02/2024"`) while the other three use ISO `YYYY-MM-DD`. |
| `table2.csv` | `semantic_anomaly` | `row=3`, `row=5` — `Systolic_BP` | Values of `445` and `512` mmHg are medically impossible (fatal threshold ≈ 300 mmHg). Correct values are likely `145` and `152` — an extra digit was prepended. |

---

### Case 04 — Stock Portfolio Tracker

| File | Size | Role |
|------|------|------|
| `table1.csv` | 6 × 8 | Daily prices for 8 tickers |
| `table2.csv` | 5 × 6 | Company and sector reference |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `missing` | `row=2`, `row=4`, `row=6` — `Closing_Price` | Closing prices blank for MSFT, AMZN, and TSLA on 2024-01-15. Prevents daily P&L and NAV calculation. |
| `table2.csv` | `inconsistency` | `row=1`, `row=3`, `row=5` — `Sector` | AAPL has `"technology"` (lower), GOOGL has `"TECHNOLOGY"` (upper), and META has `"technology"` (lower), while MSFT correctly has `"Technology"`. |

---

### Case 05 — Hotel Room Bookings

| File | Size | Role |
|------|------|------|
| `table1.csv` | 7 × 7 | Booking records with room rates |
| `table2.csv` | 6 × 5 | Stay details with check-out dates |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `semantic_anomaly` | `row=3`, `row=6` — `Room_Rate_USD` | Suite rates of `$1.50` and `$2.25` per night are implausible (standard suite rate: $389–$459/night). Likely a decimal point error. |
| `table2.csv` | `missing` | `row=2`, `row=4` — `Check_Out_Date` | Check-out dates missing for bookings B002 and B004. Expected: `2024-04-13` and `2024-04-15` based on check-in date and nights. |

---

### Case 06 — Employee Attendance Log

| File | Size | Role |
|------|------|------|
| `table1.csv` | 8 × 6 | Daily attendance with clock-in/out |
| `table2.csv` | 6 × 5 | Weekly hours summary |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `inconsistency` | `row=2`, `row=4`, `row=6` — `Status` | Rows 2 and 6 have `"present"` (all lower) and row 4 has `"PRESENT"` (all upper). Standard is `"Present"`. Attendance rate counts will miss these employees. |
| `table2.csv` | `missing` | `row=2`, `row=4`, `row=5` — `Hours_Worked` | Hours blank for E02 (Bob Davis), E04 (David Lee), and E05 (Eva Wilson). Blocks weekly payroll calculation. |

---

### Case 07 — E-commerce Product Returns

| File | Size | Role |
|------|------|------|
| `table1.csv` | 6 × 8 | Individual return records |
| `table2.csv` | 5 × 6 | Weekly return summary by product |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `missing` | `row=3`, `row=5`, `row=7` — `Return_Reason` | Reason is blank for returns R003 (Headphones), R005 (USB-C Hub), and R007 (Tablet). Required for supplier chargebacks and defect tracking. |
| `table2.csv` | `semantic_anomaly` | `row=3`, `row=6` — `Return_Qty` | Headphones: `Return_Qty=312` vs `Units_Sold=85` (366 % return rate). Winter Jacket: `Return_Qty=178` vs `Units_Sold=55` (323 % return rate). Both physically impossible. |

---

### Case 08 — Customer Support Tickets

| File | Size | Role |
|------|------|------|
| `table1.csv` | 7 × 7 | Ticket records with priority levels |
| `table2.csv` | 6 × 5 | Resolution time and CSAT metrics |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `inconsistency` | `row=2`, `row=4`, `row=7` — `Priority` | Rows 2 and 7 have `"high"` (all lower) and row 4 has `"HIGH"` (all upper). Standard is `"High"`. SLA breach monitoring will miss these tickets. |
| `table2.csv` | `missing` | `row=2`, `row=4` — `Resolution_Time_hrs` | Resolution time blank for T002 and T004. Skews average handle time and SLA compliance metrics. |

---

### Case 09 — Agricultural Crop Yield

| File | Size | Role |
|------|------|------|
| `table1.csv` | 8 × 6 | Field-level yield records |
| `table2.csv` | 6 × 5 | Crop reference with expected yield ranges |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `semantic_anomaly` | `row=3`, `row=5` — `Yield_tonnes_per_ha` | F03 (Valley Farm Wheat) = `-3.4 t/ha`, F05 (Lakewood Farm Maize) = `-6.1 t/ha`. Yield cannot be negative; correct values are `3.4` and `6.1` (minus sign entered in error). |
| `table2.csv` | `inconsistency` | `row=1`, `row=4` — `Crop` | Row 1 has `"wheat"` (all lower) and row 4 has `"WHEAT"` (all upper). Standard is `"Wheat"`. JOIN with `table1.csv` on the `Crop` column will silently fail to match these rows. |

---

### Case 10 — Smart Meter Energy Consumption

| File | Size | Role |
|------|------|------|
| `table1.csv` | 6 × 8 | Daily meter readings for one meter |
| `table2.csv` | 5 × 6 | Monthly consumption summary by building |

**Bugs**
| Table | Type | Locations | Detail |
|-------|------|-----------|--------|
| `table1.csv` | `missing` | `row=3`, `row=5`, `row=7` — `kWh_Consumed` | Consumption blank for Jan 10, 12, and 14. Expected values (~144.3 / 142.3 / 143.1 kWh) are derivable from consecutive `Meter_Reading_kWh` differences. |
| `table2.csv` | `semantic_anomaly` | `row=3`, `row=6` — `Total_kWh` | Warehouse C = `-1,820.4 kWh` and Data Center F = `-9,240.6 kWh`. Energy consumption cannot be negative for a consuming facility; the sign is erroneous. |

---

## Directory Structure

```
.
├── dataset_median/          # Medium tables (200–300 cells), 1 bug per case
│   ├── case01/
│   │   ├── table1.csv
│   │   ├── table2.csv
│   │   ├── table3.csv
│   │   └── issue.json       # Single issue object
│   └── ...
├── dataset_small/           # Small tables (≤50 cells), 1 bug per table
│   ├── case01/
│   │   ├── table1.csv
│   │   ├── table2.csv
│   │   └── issue.json       # List of issue objects (one per table)
│   └── ...
├── generate_dataset.py      # Generator for dataset_median
└── generate_dataset_small.py  # Generator for dataset_small
```

### `issue.json` Schema

**dataset_median** — single object:
```json
{
  "issue_type": "missing | inconsistency | semantic_anomaly",
  "table": "tableN.csv",
  "location": "row=R,column=ColName",
  "description": "Human-readable explanation of the bug and expected correct value.",
  "business_context": "Why this bug matters in the real-world scenario."
}
```

**dataset_small** — array of objects (one per table with a bug):
```json
[
  {
    "table": "table1.csv",
    "issue_type": "missing | inconsistency | semantic_anomaly",
    "locations": ["row=R1,column=ColName", "row=R2,column=ColName"],
    "description": "...",
    "business_context": "..."
  }
]
```

> Row numbers are 1-indexed, counting data rows only (the header row is row 0 / not counted).
