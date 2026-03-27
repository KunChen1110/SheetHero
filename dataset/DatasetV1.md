# Dataset

## Dataset Overview

This dataset tests whether the agent can reason with spreadsheets and generate outputs in different real-world tasks. Each user case includes several input spreadsheets and one or more output spreadsheets. The tasks cover fields including business analysis, algorithm problem, and machine learning. To make the data diverse and realistic, the spreadsheets are collected from public sources like Kaggle, Statista, and GitHub.

## Test 1

### Budget calculating

### Scenario

Business / personal finance analysis

### Category

merge daily spending tables; compute total and average spending; highlight maximum spending

### SpreedSheet

[spreadsheet1](Task01/tc01_input01.xlsx)
[spreadsheet2](Task01/tc01_input02.xlsx)

### Prompt

Here are two tables showing my daily spending. First merge the two tables into a single table, then calculate the average daily spending and the total spending in November. Also highlight in red the day or days on which I spend the most. Finally, output the results as a new spreadsheet.

### Answer

Total spendings: £2023.75
Average daily spendings: £72.28

#### Output

[outputfile1](Task01/tc01_output01.xlsx)

#### Feedback

LLM: Do you spend 0 pound for gift on Nov 4th and 0 pound for coffee on Nov 14th?

---

## Test 2

### Meeting schdeuling

### Scenario

Operations management / scheduling

### Category

join student and tutor tables; build consolidated meeting schedule

### SpreedSheet

[spreadsheet3](Task02/tc02_input01.csv)
[spreadsheet4](Task02/tc02_input02.csv)
[spreadsheet5](Task02/tc02_input03.csv)
[spreadsheet6](Task02/tc02_input04.csv)
[spreadsheet7](Task02/tc02_input05.csv)

### Prompt

Here are several tables about students and their tutors. Your task is to produce a new table that lists, for each tutor, the tutor’s name, the meeting time and location, and the students attending that meeting. Output the result as a new spreadsheet.

### Answer

#### Output File

[outputfile2](Task2/tc02_output01.xlsx)

#### Feedback

LLM : Are room number 'C80' and 'C 80' the same?

---

## Test 3

### Internet Penetration Rate Analysis (visualization)

### Scenario

Statistical analysis and data visualization

### Category

clean multi-row headers; compute regional averages and growth; generate line chart

### SpreadSheet

[spreadsheet8](Task03/tc03_input01.xlsx)

### Prompt

[INSTRUCTION FOR ANALYST:
The Data sheet has a messy multi-row header. When you read it via inspector / inspector_multi:

1. Do NOT assume that data[0] is the header row.
2. First, find the FIRST row whose first cell is a year (e.g., 2009, 2010, …).
3. Use the row ABOVE that as the header row for regions (Africa, Arab States, etc.), and IGNORE any trailing "in %" or extra notes columns.
4. When building a DataFrame, always enforce that:
   len(columns) == len(row)
   If the header row is longer, slice it: columns = header[:len(row)].
5. Only after normalizing the header and data rows to equal length, create the DataFrame once and reuse it.

Follow these rules strictly to avoid “N columns passed, passed data had M columns” errors.
END OF INSTRUCTION]

Here is a table showing internet penetration rates from 2009 to 2024. Please calculate the average internet penetration rate for each region over the years 2020–2024. Identify the region with the fastest growth rate and sort the regions by growth rate. Also provide a line chart where each region is represented by a different color, the horizontal axis is year (2020 to 2024), and the vertical axis is penetration rate.

### Answer

#### Output file

[outputfile3](Task03/tc03_output01.xlsx)
[outputfile4](Task03/internet_trend.png)

#### Feedback

I find that the data in 2020 is missing.

---

## Test4

### Task scheduling table

### Scenario

Algorithmic scheduling problem

### Category

build task dependency graph; perform topological scheduling; compute total duration

### SpreadSheet

[spreadsheet9](Task04/tc04_input01.xlsx)
[spreadsheet10](Task04/tc04_input02.xlsx)

### Prompt

Here is a table containing tasks, their durations, and priorities, and another table describing task dependencies (which task needs to be finished before another). All machines start at 8:00 am.
Your task is to schedule the tasks based on these dependencies.

Create a new Excel sheet showing the final schedule with columns:

| Task ID | Task Name | Priority | Start Time | End Time |
| ------- | --------- | -------- | ---------- | -------- |

Also answer the question
What is the total duration required to finish all the tasks?

This is a scheduling-with-dependencies problem. You MUST:

1. Treat the dependency table as a DAG:
   - Missing/empty "Depends on" = ROOT task, do NOT drop these rows.
2. Build a topological order:
   - Every Task ID in the task table appears EXACTLY ONCE in the final schedule.
   - Print all Task IDs vs scheduled Task IDs and ensure the sets match.
3. Time:
   - Start at 08:00, add numeric durations sequentially.
   - Total duration = sum of all task durations when executed one after another.

### Answer

The duration of finishing all tasks is 10 hour.

### Output

[outputfile5](Task04/tc04_output01.xlsx)

### Feedback

Can I assume that there is no time between switching from one task to another?

---

## Test5

### Indian Smartphone shipment and market share

### Scenario

Business / market analysis

### Category

align time ranges; combine shipment and market share; compute estimated unit shipments per brand

### SpreadSheet

[spreadsheet11](Task05/tc05_input01.xlsx)
[spreadsheet12](Task05/tc05_input02.xlsx)

### Prompt

Here are two tables. One gives the number of smartphone units shipped in India from 2012 to 2025, and the other gives market share in India from 2017 to 2025. Your task is to find the overlapping time period between the two timelines, then estimate the number of smartphones for each brand in India as market_share \* shipment.
Output a table in the following format:

| Time | Vivo (Unit shipment) | SamSung | ... |
| ---- | -------------------- | ------- | --- |

### Answer

None

### Output file

[outputfile6](Task05/tc05_output01.xlsx)

### Feedback

Is market_share \* shipment a good estimation?

---

## Test6

### Titanic survivor dataset analysis

### Scenario

Machine learning / exploratory data analysis

### Category

compute correlation coefficients between survival and features; handle missing values; output summary table

### SpreadSheet

[spreadsheet13](Task06/tc06_input01.csv)

### Prompt

Your task is to calculate the correlation coefficient between survival and other factors (such as sex, age, etc.) using the Titanic dataset.
Pearson correlation coefficient:
r_xy = cov(X, Y) / (σ_X \* σ_Y)
Output an Excel file with the following columns:
| Sex | Age | Fare | Cabin | Embarked |
|-----|-----|------|--------|-----------|

### Answer

None

### Output

[outputfile7](Task06/tc6_output01.xlsx)

### Feedback

I found missing values — how would you like me to handle them? Can I treat them as NULL?

---

## Test7

### Ice-cream sales vs temperature, rain, price

### Scenario

Machine learning regression task

### Category

fit linear regression model; estimate feature coefficients; export learned weights

### SpreadSheet

[spreadsheet14](Task07/tc07_input01.csv)

### Prompt

Assume a linear relationship between ice-cream sales and three factors: temperature, price, and number of tourists. Fit a linear regression model to estimate the weight (coefficient) of each factor in predicting sales. Output the learned weights in an Excel file.

### Answer

None

### Output

[outputfile8](Task07/tc07_output01.xlsx)

### Feedback

In this case, I treat rains as 1 and not rains as 0.

---

## Test8

### Iris datasets

### Scenario

Machine learning / statistical analysis

### Category

filter by species; compute correlation matrix of numeric features; format correlation table

### SpeadSheet

[spreadsheet15](Task08/tc08_input01.csv)

### Prompt

Calculate the correlation matrix for all numeric columns in the Iris dataset, restricted to the species Iris-setosa.
Output a 4×4 table with both rows and columns as:
|Sepal_Length | Sepal_Width | Petal_Length | Petal_Width |
|-------------|-------------|--------------|-------------|
Round all correlation values to two decimal places, and label the table clearly with the species name.

### Output

[outputfile9](Task08/tc08_output01.xlsx)

### Answer

None

### Feedback

Would you like me to include species names as table titles, or as part of the header row?

---

## Test9

### Business Analysis of Coca cola company

### Scenario

Financial / business analysis

### Category

compute cash flow ratios; calculate free cash flow; summarize yearly and overall efficiency

### SpreadSheet

[spreadsheet16](Task09/tc09_input01.xlsx)

### Prompt

Evaluate the cash flow efficiency of Coca-Cola from 2009 to 2018 by calculating:

- Operating Cash Flow to Net Income

- Free Cash Flow (Operating Cash Flow minus Capital Expenditures)

### Output

[outputfile10](Task09/tc09_output01.xlsx)

### Answer

None

### Feedback

Should I exclude the 2017 one-time tax expense when calculating the OCF/Net Income ratio?
Do you want the OCF/Net Income ratio averaged across all years or shown year by year?

---

## Test10

### Cycle detection in graphs

### Scenario

Algorithm problem on graph structures

### Category

parse adjacency lists; detect cycles in directed graphs; flag graphs with cycles

### SpreadSheet

[spreadsheet17](Task10/tc10_input01.csv)
[spreadsheet18](Task10/tc10_input02.csv)
[spreadsheet19](Task10/tc10_input03.csv)
[spreadsheet20](Task10/tc10_input04.csv)
[spreadsheet21](Task10/tc10_input05.csv)

### Prompt

Given five Excel files representing the adjacency lists of directed graphs, determine which graphs contain a cycle and which do not. Output an Excel file with the following columns:
| Graph ID| Contains Cycle (True / False)|
|---------|------------------------------|

### Answer

None

### Output

[outputfile11](Task10/tc10_output01.xlsx)

### Feedback

None

---

## Test11

### Inventory Management problem

### Scenario

Operations research / inventory management

### Category

compute EOQ and related metrics; run sensitivity analysis; compare cost scenarios

### Spreadsheet

[spreadsheet22](Task11/tc11_input01.xlsx)

### Prompt

Here is an inventory dataset for a single product.
Based on this data, please:

Calculate the Economic Order Quantity (EOQ), reorder point, number of orders per year, cycle time, and total annual cost for the base scenario.
Perform a sensitivity analysis by varying the order quantity (for example 50%, 75%, 100%, 125%, and 150% of the EOQ) and compute the total annual cost for each case.
Evaluate a scenario where the annual demand increases by 20% and recompute EOQ, reorder point, number of orders per year, cycle time, and total annual cost.
Output the results in a new Excel file organized in clear tables. At minimum:

One table summarizing the base scenario metrics.
One table for the sensitivity analysis (order quantity vs total annual cost).
One table for the “demand +20%” scenario metrics.

### Answer

### Output

[outputfile12](Task11/tc11_output01.xlsx)
[outputfile13](Task11/tc11_output02.xlsx)
[outputfile14](Task11/tc11_output03.xlsx)

### Feedback

Clarification on Assumptions: The EOQ model assumes constant demand, no stockouts, and fixed costs. The holding cost (H) is often derived as a percentage of the unit cost (e.g., 16.67% of $15 = $2.5). If these assumptions change, the results may need adjustment.

---

## Test12

### Multi-Source Financial Performance Dashboard

### Scenario

Financial performance and marketing analytics

### Category

consolidate multi-sheet financial data; compute profit and margin metrics; calculate CAC and marketing efficiency

### Spreadsheet

[spreadsheet23](Task12/tc12_input01.xlsx)
[spreadsheet24](Task12/tc12_input02.xlsx)
[spreadsheet25](Task12/tc12_input03.xlsx)

### Prompt

Calculate the following metrics for each month and for the total quarter:
Gross Profit (Revenue - Cost of Goods Sold)

Net Profit (Gross Profit - Operating Expenses - Interest Paid)

Gross Profit Margin (Gross Profit / Revenue)

Net Profit Margin (Net Profit / Revenue)

Customer Acquisition Cost - CAC (Marketing Spend / New Customers)

Marketing Efficiency Ratio (Revenue / Marketing Spend)

### Output

[outputfile15](Task12/tc12_output01.xlsx)

### Answer

None

### Feedback

The dashboard was generated by first consolidating the monthly P&L and Sales data. Key ratios like Gross Profit Margin and CAC were calculated for each month, then aggregated to Q1 totals (for profit values) or averages (for ratios) for a holistic view. The variance was calculated as Actual - Target.

---

## Test13

### Global Diabetes Population Analysis

### Scenario

Public health and healthcare expenditure analysis

### Category

aggregate diabetic population by region; compute global share and average expenditure per person; build summary table

### Spreadsheet

[spreadsheet26](Task13/tc13_input01.xlsx)
[spreadsheet27](Task13/tc13_input02.xlsx)
[spreadsheet28](Task13/tc13_input03.xlsx)

### Prompt

Given three spreadsheets showing:

- Diabetes prevalence among adults by country (2024)
- Number of diabetics worldwide by region (in millions, 2024)
- Diabetes-related health expenditure by region (in billion USD, 2024)

For each region, calculate:

- The share of global diabetic population (%)
- The average expenditure per diabetic (USD per person)

Output an Excel file containing the following columns:

| Region | Diabetics (millions) | Share of Global (%) | Expenditure (billion USD) | Avg Expenditure per Person (USD) |
| ------ | -------------------- | ------------------- | ------------------------- | -------------------------------- |

### Output

[outputfile16](Task13/tc13_output01.xlsx)

### Answer

None

### Feedback

---

## Test14

### Global Mobile Reviews Analysis

### Scenario

Customer review and marketing analytics

### Category

group reviews by country and brand; compute average rating and review counts; summarize in table

### Spreadsheet

[spreadsheet29](Task14/tc14_input01.csv)

### Prompt

Given a dataset of smartphone reviews containing customer information, brand, model, and overall ratings, generate a table that shows, for each country and brand, the average rating and the number of reviews. The output should be an Excel file with columns: country, brand, avg_rating, num_reviews. Focus only on the average rating metric and provide a clear summary suitable for analysis.

### Output

[outputfile17](Task14/tc14_output01.xlsx)

### Answer

None

### Feedback

Some reviews may have missing ratings. Should I exclude them or treat them as zero?"

---

## Test15

### Brazilian E-Commerce Public Dataset Analysis

### Scenario

E-commerce data integration and analysis

### Category

merge multiple relational CSV tables; translate category names; report merged dataset size

### Spreadsheet

[spreadsheet30](Task15/tc15_input01.csv)
[spreadsheet31](Task15/tc15_input02.csv)
[spreadsheet32](Task15/tc15_input03.csv)
[spreadsheet33](Task15/tc15_input04.csv)
[spreadsheet34](Task15/tc15_input05.csv)
[spreadsheet35](Task15/tc15_input06.csv)
[spreadsheet36](Task15/tc15_input07.csv)
[spreadsheet37](Task15/tc15_input08.csv)

### Prompt

Here are eight CSV files from the Brazilian e-commerce dataset. Please merge them into a single table and translate the product category names into English. You must output the merged result as a new Excel file, and in your final answer also report the size of the merged dataset (number of rows and columns).

### Answer

rows : 118310, columns : 44

### Output file

[outputfile18](Task15/tc15_output01.xlsx)

### Feedback

None

---

## Test 16

### Employee Performance & Salary Correlation

### Scenario

HR analytics and compensation analysis

### Category

compute correlation between performance and income; aggregate average income by rating; create scatter plot

### Spread Sheet

[spreadsheet38](Task16/tc16_input01.xlsx)

### Prompt

Here is a dataset containing employee details such as monthly income, years of experience, and performance rating. Please calculate the Pearson correlation between performance rating and monthly income, compute the average income for each rating level, and create a scatter plot of years of experience versus monthly income. Output the results in a new Excel file.

### Answer

#### Output File

[outputfile19](Task16/tc16_output01.xlsx)

### Feedback

LLM: Should the scatter plot include a trendline?

---

## Test 17

### Store Feature Analysis

### Scenario

Retail store performance analysis

### Category

merge weekly store tables; compute average numeric features by store type; compare holiday vs non-holiday weeks

### Spread Sheet

[spreadsheet39](Task17/tc17_input01.xlsx)
[spreadsheet40](Task17/tc17_input02.xlsx)

### Prompt

Here are two tables containing weekly store information. Please merge them by store, then calculate the average temperature, fuel price, consumer price index, and unemployment rate for each store type. Also compare holiday and non-holiday weeks by computing the average values for each numeric feature. Output a summary Excel file.

### Answer

#### Output File

[outputfile20](Task17/tc17_output01.xlsx)

### Feedback

LLM: Should holiday and non-holiday averages also be grouped by store type?

---

## Test 18

### University Course Enrollment Analysis

### Scenario

Education enrollment analytics

### Category

aggregate enrollment by department; calculate year-over-year growth; identify high-growth departments; create trend line chart

### Spread Sheet

[spreadsheet41](Task18/tc18_input01.xlsx)

### Prompt

Here is a dataset showing total enrollment by year and semester. Please calculate the total enrollment for each year, determine year-over-year growth in total enrollment, identify years with more than ten percent growth, and create a line chart showing overall enrollment trends over time. Highlight the high‑growth years clearly in the Excel output. Output the results in a new Excel file.

### Answer

#### Output File

[outputfile21](Task18/tc18_output01.xlsx)

### Feedback

LLM: Should growth be calculated only for the most recent year?

---

## Test 19

### Global Carbon Emissions Comparison

### Scenario

Environmental and climate data analysis

### Category

group emissions by continent; compute yearly totals and percentage changes; build 2022 ranking bar chart

### Spread Sheet

[spreadsheet42](Task19/tc19_input01.xlsx)

### Prompt

This dataset lists annual carbon dioxide emissions by country. Please group countries by continent, calculate the total emissions per continent for each year, and compute the percentage change from 2000 to 2022.

If data for the year 2022 is missing, then instead use the latest available year (for example 2019) as the comparison endpoint, and clearly state this assumption in the output.

Create a bar chart ranking continents by emissions in 2022; if 2022 is not available, rank by the latest available year used in your calculation. Output the results in a new Excel file.

### Answer

#### Output File

[outputfile22](Task19/tc19_output01.xlsx)

### Feedback

LLM: Should countries without a continent be grouped under “Unknown”?

---

## Test 20

### Hospital Resource Utilization Analysis

### Scenario

Healthcare operations and resource planning

### Category

combine staff, schedule, service, and patient tables; compute utilization metrics; highlight overutilized departments

### Spread Sheet

[spreadsheet43](Task20/tc20_input01.xlsx)
[spreadsheet44](Task20/tc20_input02.xlsx)
[spreadsheet45](Task20/tc20_input03.xlsx)
[spreadsheet46](Task20/tc20_input04.xlsx)

### Prompt

Here are four hospital tables containing staff, schedules, services, and patient information. Please compute staff utilisation, service utilisation, and patient load for each department. Identify departments with utilisation above ninety percent and highlight these values in red. Output all results in a new Excel file.

### Answer

#### Output File

[outputfile23](Task20/tc20_output01.xlsx)

### Feedback

LLM: Should the highlighting apply only to the utilisation value or the entire row?

---

## Test 21

### Interviewee screening

### Scenario

HR candidate evaluation

### Category

aggregate candidate attributes from multiple files; compute weighted screening score; rank and filter candidates

### Spread Sheet

[spreadsheet47](Task21/tc21_input01.xlsx)
[spreadsheet48](Task21/tc21_input02.xlsx)
[spreadsheet49](Task21/tc21_input03.xlsx)
[spreadsheet50](Task21/tc21_input04.xlsx)
[spreadsheet51](Task21/tc21_input05.xlsx)
[spreadsheet52](Task21/tc21_input06.xlsx)
[spreadsheet53](Task21/tc21_input07.xlsx)
[spreadsheet54](Task21/tc21_input08.xlsx)
[spreadsheet55](Task21/tc21_input09.xlsx)
[spreadsheet56](Task21/tc21_input10.xlsx)
[spreadsheet57](Task21/tc21_input11.xlsx)
[spreadsheet58](Task21/tc21_input12.xlsx)
[spreadsheet59](Task21/tc21_input13.xlsx)
[spreadsheet60](Task21/tc21_input14.xlsx)
[spreadsheet61](Task21/tc21_input15.xlsx)
[spreadsheet62](Task21/tc21_input16.xlsx)
[spreadsheet63](Task21/tc21_input17.xlsx)
[spreadsheet64](Task21/tc21_input18.xlsx)
[spreadsheet65](Task21/tc21_input19.xlsx)
[spreadsheet66](Task21/tc21_input20.xlsx)

### Prompt

As an HR professional, I have received 20 spreadsheets containing candidate information. Your task is to rank the candidates based on the following score:
0.5 _ working experience + 0.3 _ number of skills + 0.2 \* personality score
Output a file that includes each candidate’s score, skills, and other attributes.

### Answer

None

### Output File

[outputfile24](Task21/tc21_output01.xlsx)

### Feedback

Some candidates did not fill in essential information. Should these fields be treated as null values? Additionally, a few candidates did not provide their names. In such cases, can we exclude them from the analysis?

---

## Test 22

### Missing Data (Simple)

### Scenario

Data quality checking

### Category

scan spreadsheet for missing cells; locate and report positions of missing values

### Spreadsheet

[spreadsheet67](Task22/tc22_input01.xlsx)

### Prompt

Check the file for missing data and identify where values are missing.

### Answer

Missing data on line 3 col 1

### Output

None

### Feedback

Can I help you fill the missing data with a default value?

---

## Test 23

### Fill Missing Data from Another File (Simple)

### Scenario

Data cleaning and imputation

### Category

align two files; fill missing values in primary file using secondary file; output completed table

### Spreadsheet

[spreadsheet68](Task23/tc23_input01.xlsx)
[spreadsheet69](Task23/tc23_input02.xlsx)

### Prompt

Fill any missing data in tc23_input01 using information from file tc23_input02, and output a file with complete data.

### Answer

None

### Output

[outputfile25](Task23/tc23_output01.xlsx)

### Feedback

If both files have a value, which file should take priority when filling the missing data?

---

## Test 24

### Merge Two Files (Simple)

### Scenario

Basic data integration

### Category

merge two spreadsheets; resolve overlaps or conflicts; output combined table

### Spreadsheet

[spreadsheet70](Task24/tc24_input01.xlsx)
[spreadsheet71](Task24/tc24_input02.xlsx)

### Prompt

Merge the two files into a single file.

### Answer

None

### Output

[outputfile26](Task24/tc24_output01.xlsx)

### Feedback

When merging the two files, how should I handle rows with conflicting data?

---

## Test 25

### Merge Three Files (Simple)

### Scenario

Basic data integration

### Category

merge three spreadsheets; handle duplicate records; produce unified dataset

### Spreadsheet

[spreadsheet72](Task25/tc25_input01.xlsx)
[spreadsheet73](Task25/tc25_input02.xlsx)
[spreadsheet74](Task25/tc25_input03.xlsx)

### Prompt

Merge the three files into a single file.

### Answer

None

### Output

[outputfile27](Task25/tc25_output01.xlsx)

### Feedback

When merging three files, how should I resolve conflicts between different versions of the same row?

---

## Test 26

### Merge Four Files (Simple)

### Scenario

Basic data integration

### Category

merge four spreadsheets; deduplicate or reconcile conflicting rows; output consolidated file

### Spreadsheet

[spreadsheet75](Task26/tc26_input01.xlsx)
[spreadsheet76](Task26/tc26_input02.xlsx)
[spreadsheet77](Task26/tc26_input03.xlsx)
[spreadsheet78](Task26/tc26_input04.xlsx)

### Prompt

Merge the four files into a single file.

### Answer

None

### Output

[outputfile28](Task26/tc26_output01.xlsx)

### Feedback

When merging four files, do you want duplicate rows removed if the same record appears in multiple files?

---

## Test 27

### Room Syntax Difference (Simple)

### Scenario

Data cleaning and standardization

### Category

detect inconsistent room identifiers; compare string formats; suggest standardized room notation

### Spreadsheet

[spreadsheet79](Task27/tc27_input01.xlsx)

### Prompt

Inspect the room identifiers in the spreadsheet and check for any inconsistencies in how the same room is written (for example: "C 80" vs "C80" vs "c80"). Do not modify the workbook. Instead, describe any inconsistencies you find in natural language, and, if appropriate, ask a clarifying question such as: "Should Room be C 80 or C80 or c80?"

### Answer

Should Room be C 80 or C80 or c80

### Feedback

Are "C 80", "C80", and "c80" all the same room, or should I treat them as different values?
