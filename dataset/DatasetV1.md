# Dataset

## Dataset Overview
This dataset tests whether the agent can reason with spreadsheets and generate outputs in different real-world tasks. Each user case includes several input spreadsheets and one or more output spreadsheets. The tasks cover fields including business analysis, algorithm problem, and machine learning. To make the data diverse and realistic, the spreadsheets are collected from public sources like Kaggle, Statista, and GitHub.



## Test 1

### Budget calculating

### Spreed Sheet

[spreadsheet1](Task1/input1.xlsx)
[spreadsheet2](Task1/input2.xlsx)

### Prompt
Here are two tables about my daily spending. Could you first merge the two forms together, then calculate the average daily spending, total spending in Novemeber? Also, indicate whcih day(s) I spend most in red. You need to output a new spreadsheet.

### Answer

#### Output

[outputfile1](Task1/output1.xlsx)

#### Feedback

LLM: Do you spend 0 pound for gift on Nov 4th and 0 pound for coffee on Nov 14th?

---

## Test 2

### Meeting schdeuling

### Spreed Sheet

[spreadsheet3](Task2/academic_roles.xlsx)
[spreadsheet4](Task2/academics_list.xlsx)
[spreadsheet5](Task2/student_assignments.xlsx)
[spreadsheet6](Task2/tutor_availability.xlsx)
[spreadsheet7](Task2/tutor_meetings.xlsx)
### Prompt
Hello, I here are tables about students and their tutors. You task is to output a new form listing each tutor’s name, the time and location of their tutor meeting, as well as the students attending the meeting.
### Answer

#### Output File

[outputfile2](Task2/output2.xlsx)

#### Feedback
LLM : Are room number 'C80' and 'C 80' the same? 

---

## Test 3
### Internet Penetration Rate Analysis (visualization)

### Spread Sheet
[spreadsheet8](Task3/internet_penetration.xlsx)

### Prompt
Here is the form detailing the internet_penetration rate from 2009 to 2024. Could you calculates the average Internet Penetration rate for each region over the years 2020–2024 ? Identifies the region with the fastest growth rate and sort the region by growth rate. Also, provide a line chart, use different color to represent region, vertical is year (from 2020 to 2024), horizontal represents penetration rate 
### Answer


#### Output file
[outputfile3](Task3/output3.xlsx)

#### Feedback
I find that the data in 2020 is missing.

---

## Test4
### Task scheduling table
### Spread Sheet
[spreadsheet9](Task4/task4_scheduling.xlsx)

### Prompt
Hello, here is a table containing tasks, their durations, priorities. Here is also a table about task dependencies (which task needs to be finished before other tasks). All machine starts at 8:00 am.
Your task is to schedule the tasks based on task dependency.

Create a new Excel sheet showing the final schedule with columns:

| Task ID | Task Name | Priority | Start Time | End Time |
|---------|-----------|----------|-----------|----------|

Also answer the question
What's the duration of finishing all the tasks ?


### Answer
The duration of finishing all tasks is 10 hour.

## Output file
[outputfile4](Task4/output1.xlsx)


### Feedback
Can I assume that there is no time between switching from one task to another? 


---


## Test5
### Indian Smartphone shipment and market share
### Spread Sheet
[spreadsheet10](Task5/smartphone_shipment.xlsx)
[spreadsheet11](Task5/market_share.xlsx)

### Prompt
Here are two forms, one is the number of unit smartphones in india from 2012 to 2025, the other is 
the marketshare of 2017 to 2025 in india. You task is two find the overlap between 2 timelines, then compute the estimation of number of smartphones of each brand in india. That is market_share * shipment.
Output a form in the following format :

| Time | Vivo (Unit shipment) | SamSung | ... |  
|------|----------------------|---------|-----|


### Answer
None

### Output file
[output5](Task5/output5.xlsx)
### Feedback
Is market_share * shipment a good estimation?

---


## Test6
### Titanic survivor dataset analysis
### Spread Sheet
[spreadsheet12](Task6/Titanic-Dataset.xlsx)

### Prompt
Your task is to calculate the correlation coefficient between survivor and other factors (sex, age, ...) given the titantic dataset.
Pearson correlation coefficient :
r_xy = cov(X, Y) / (σ_X * σ_Y)
Output an excel with format
| Sex | Age | Fare | Carbin | Emabarked | 
|-----|-----|------|--------|-----------|


### Answer
None
### Output
[output6](Task6/output6.xlsx)
### Feedback
I found missing values — how would you like me to handle them? Can I treat them as NULL?

---


## Test7

### Ice-cream sales vs temperature, rain, price
### SpreadSheet
[spreadsheet13](Task7/ice_cream.csv)

### Prompt
Assume a linear relationship between ice-cream sales and the factors — temperature, price, and number of tourists. Fit a linear regression model to estimate the weight (coefficient) of each factor in predicting sales. Output the learned weights to an Excel file.

### Answer
None

### Output
[output7](Task7/output7.xlsx)
### Feedback
In this case, I treat rains as 1 and not rains as 0.

---


## Test8
### Iris datasets
### SpeadSheet
[spreadsheet15](Task8/IRIS.csv)

### Prompt
Calculate the correlation matrix for all numeric columns in the Iris dataset separately for species Iris-setosa.
Output a 4×4 table with both rows and columns as:
|Sepal_Length | Sepal_Width | Petal_Length | Petal_Width |
|-------------|-------------|--------------|-------------|
Round all correlation values to two decimals, and label each table clearly with the species name.

### Output
[outputfile8](Task8/output1.xlsx)
### Answer
None

### Feedback
Would you like me to include species names as table titles, or as part of the header row?

---

## Test9
### Business Analysis of Coca cola company
### SpreadSheet
[spreadsheet16](Task9/Cola.xlsx)

### Prompt
Evaluate cash flow efficiency of coca cola company from 2009 to 2018 by calculating:

* Operating Cash Flow to Net Income

* Free Cash Flow (Operating Cash Flow minus Capital Expenditures)

### Output
[output9](Task9/output1.xlsx)


### Answer
None

### Feedback
Should I exclude the 2017 one-time tax expense when calculating the OCF/Net Income ratio?
Do you want the OCF/Net Income ratio averaged across all years or shown year by year?

---



## Test10
### Cycle detection in graphs
### SpreadSheet
[spreadsheet17](Task10/graph_1.csv)
[spreadsheet18](Task10/graph_2.csv)
[spreadsheet19](Task10/graph_3.csv)
[spreadsheet20](Task10/graph_4.csv)
[spreadsheet21](Task10/graph_5.csv)



### Prompt
Given 5 excel representing the adjacent list of the directed graph , could you tell which graph contains a cycle and which graph not? Output an excel, containing columns in the format
| Graph ID| Contains Cycle (True / False)|
|---------|------------------------------|

### Answer
None

### Output
[output10](Task10/output10.xlsx)

### Feedback
None


---




## Test11
### Inventory Management problem
### Spreadsheet
[spreadsheet22](Task11/input.xlsx)


### Prompt
Based on the provided inventory data, calculate the Economic Order Quantity (EOQ), reorder point, number of orders per year, cycle time, and total annual cost. Also, perform a sensitivity analysis to show how total cost changes with different order quantities, and evaluate a scenario where annual demand increases by 20%. Provide the results in a structured table.

### Answer

### Output
[outputfile11](Task11/output1.xlsx)
[outputfile12](Task11/output2.xlsx)
[outputfile13](Task11/output3.xlsx)

### Feedback
Clarification on Assumptions: The EOQ model assumes constant demand, no stockouts, and fixed costs. The holding cost (H) is often derived as a percentage of the unit cost (e.g., 16.67% of $15 = $2.5). If these assumptions change, the results may need adjustment.

---


## Test12
### Multi-Source Financial Performance Dashboard
### Spreadsheet
[spreadsheet23](Task12/input1.xlsx)
[spreadsheet24](Task12/input2.xlsx)
[spreadsheet25](Task12/input3.xlsx)

### Prompt
Calculate the following metrics for each month and for the total quarter:
Gross Profit (Revenue - Cost of Goods Sold)

Net Profit (Gross Profit - Operating Expenses - Interest Paid)

Gross Profit Margin (Gross Profit / Revenue)

Net Profit Margin (Net Profit / Revenue)

Customer Acquisition Cost - CAC (Marketing Spend / New Customers)

Marketing Efficiency Ratio (Revenue / Marketing Spend)


### Output
[outputfile14](Task12/output1.xlsx)

### Answer
None
 
### Feedback
The dashboard was generated by first consolidating the monthly P&L and Sales data. Key ratios like Gross Profit Margin and CAC were calculated for each month, then aggregated to Q1 totals (for profit values) or averages (for ratios) for a holistic view. The variance was calculated as Actual - Target.

---

## Test13
### Global Diabetes Population Analysis
### Prompt
Given three spreadsheets showing:
* Diabetes prevalence among adults by country (2024)
* Number of diabetics worldwide by region (in millions, 2024)
* Diabetes-related health expenditure by region (in billion USD, 2024)

Calculate for each region:
* The share of global diabetic population (%)
* The average expenditure per diabetic (USD per person)

Output an Excel file containing:

| Region | Diabetics (millions) | Share of Global (%) | Expenditure (billion USD) | Avg Expenditure per Person (USD) |
|--------|----------------------|---------------------|---------------------------|----------------------------------|


### Output
[output15](Task13/output13.xlsx)

### Answer
None

### Feedback

---

## Test14
### Global Mobile Reviews Analysis
### Prompt
Given a dataset of smartphone reviews containing customer information, brand, model, and overall ratings, generate a table that shows, for each country and brand, the average rating and the number of reviews. The output should be an Excel file with columns: country, brand, avg_rating, num_reviews. Focus only on the average rating metric and provide a clean summary suitable for analysis.


### Output
[output16](Task14/output14.xlsx)

### Answer
None

### Feedback
Some reviews may have missing ratings. Should I exclude them or treat them as zero?"

---

## Test15
### Brazilian E-Commerce Public Dataset Analysis

---
## Test 16

### Employee Performance & Salary Correlation

### Spread Sheet

[spreadsheet26](Task16/Employe_Performance_dataset.csv)

### Prompt

Here is a dataset containing employee details such as monthly income, years of experience, and performance rating. Please calculate the Pearson correlation between performance rating and monthly income, compute the average income for each rating level, and create a scatter plot of years of experience versus monthly income. Output the results in a new Excel file.

### Answer

#### Output File

[outputfile16](Task16/output16.xlsx)

### Feedback

LLM: Should the scatter plot include a trendline?

---

## Test 17

### Store Feature Analysis

### Spread Sheet

[spreadsheet27](Task17/stores.csv)
[spreadsheet28](Task17/features.csv)

### Prompt

Here are two tables about weekly store information. Please merge them by store, then calculate the average temperature, fuel price, consumer price index, and unemployment rate for each store type. Also compare holiday and non-holiday weeks by computing the average values for each numeric feature. Output a summary Excel file.

### Answer

#### Output File

[outputfile17](Task17/output17.xlsx)

### Feedback

LLM: Should holiday and non-holiday averages also be grouped by store type?

---

## Test 18

### University Course Enrollment Analysis

### Spread Sheet

[spreadsheet29](Task18/ISU Enrollment.csv)

### Prompt

Here is a dataset showing enrollment by college, department, and year. Please calculate the total enrollment for each department, determine year-over-year growth, identify departments with more than ten percent growth, and create a line chart showing enrollment trends for each college. Output the results in a new Excel file.

### Answer

#### Output File

[outputfile18](Task18/output18.xlsx)

### Feedback

LLM: Should growth be calculated only for the most recent year?

---

## Test 19

### Global Carbon Emissions Comparison

### Spread Sheet

[spreadsheet30](Task19/Carbon_%28CO2%29_Emissions_by_Country.csv)

### Prompt

This dataset lists annual carbon dioxide emissions by country. Please group countries by continent, calculate the total emissions per continent for each year, compute the percentage change from 2000 to 2022, and create a bar chart ranking continents by emissions in 2022. Output a new Excel file.

### Answer

#### Output File

[outputfile19](Task19/output19.xlsx)

### Feedback

LLM: Should countries without a continent be grouped under “Unknown”?

---

## Test 20

### Hospital Resource Utilization Analysis

### Spread Sheet

[spreadsheet31](Task20/staff.csv)
[spreadsheet32](Task20/staff_schedule.csv)
[spreadsheet33](Task20/services_weekly.csv)
[spreadsheet34](Task20/patients.csv)

### Prompt

Here are four hospital tables containing staff, schedules, services, and patient information. Please compute staff utilisation, service utilisation, and patient load for each department. Identify departments with utilisation above ninety percent and highlight these values in red. Output all results to a new Excel file.

### Answer

#### Output File

[outputfile20](Task20/output20.xlsx)

### Feedback

LLM: Should the highlighting apply only to the utilisation value or the entire row?

## Task 21
### Input
Inp1
### Prompt
Check for missing data in the file
### Output
Missing data on line 3 col B
### Testing
Missing Data

## Task 22
### Input
Inp1
Inp2
### Prompt
Fill any missing data in file one using info from file 2
### Output
Out1
### Testing
Fill missing data from one file using another file

## Task 23
### Input
Inp1
Inp2
### Prompt 
Merge the files
### Output
Out1
### Testing
How well the system can merge 2 files

## Task 24
### Input
Inp1
Inp2
Inp3
### Prompt
Merge the files
### Output
Out1
### Testing
How well the system can merge 3 files

## Task 25
### Input
Inp1
Inp2
Inp3
Inp4
### Prompt
Merge the files
### Output
Out1
### Testing
How well the system can merge 4 files

## Task 26
### Input
Inp1
### Prompt 
check for an errors
### Output
Should Room be C 80 or C80 or c80
### Testing
Syntax differancve for same col



