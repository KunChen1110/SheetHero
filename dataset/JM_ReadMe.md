# Dataset

## Test Catagories
Logic : How well the model can spot logical issues: E.G. Coffee isn't £0
Merge : How well the system can merge files
Generative : How well the system creates new file: Excel, Graphs, ...
Syntax : How well the system responds to syntax errors in the files: 'C80' =? 'C 80'
Mathmatical : How well the system handles mathmatical operations 
Multi-File : How well the system can use data coming from multiple files
Query : How well the system handles query confusion: If the system can't tell what its being asked to do
Knowlegde : How well the system has externel Knowlegde: externel from the input files


## Test 1

### Budget calculating

### Spreed Sheet

[spreadsheet1](Task1/input1.xlsx)
[spreadsheet2](Task1/input2.xlsx)

### Prompt
Here are two tables about my daily spending. Could you first merge the two forms together, then calculate the average daily spending, total spending in Novemeber? Also, indicate whcih day(s) I spend most in red. You need to output a new spreadsheet.

### Answer
#### Output File

[outputfile1](source/to/outputfile1.xlsx)

#### Feedback

LLM: Do you spend 0 pound for gift on Nov 4th and 0 pound for coffee on Nov 14th?

#### Testing
Merge, Logic

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

[outputfile2](source/to/outputfile2.xlsx)

#### Feedback
LLM : Are room number 'C80' and 'C 80' the same? 
Testing: Merge, Syntax

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

#### Testing
Generative, Mathmatical



## Test4
### Task scheduling table
### Spread Sheet
[spreadsheet9](Task4/task4_scheduling.xlsx)

### Prompt
Hello, here is a table containing tasks, their durations, priorities, and required resources. All machine starts at 8:00 am.
Your task is to schedule the tasks based on :
(1) higher priority tasks first
(2) no overlapping tasks on the same resource

Create a new Excel sheet showing the final schedule with columns:

| Task ID | Task Name | Priority | Resource | Start Time | End Time |
|---------|-----------|----------|----------|------------|----------|

Also answer the question
What's the duration of finishing all the tasks ?


### Answer


## Output file

### Feedback


### Testing
Generative, Logic 




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
|------|------|---------|-----|


### Answer


### Output file

### Feedback
### Testing 
Query, Generative, Logic, Multi-File

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


## Output file

### Feedback
### Testing
Logic, Mathmatical

## Test7

### Ice-cream sales vs temperature, rain, price
### SpreadSheet
[spreadsheet13](Task7/ice_cream.csv)
### Prompt
Create 3 grpahs to show how ice cream sales are affected by temperature, rain, and price respenctivly 


### Testing
Generative

## Test8
### Iris datasets
### SpeadSheet
[spreadsheet15](Task8/IRIS.csv)
### Prompt 
For each species give me the avg for each col

### Testing
Mathmatical, Query

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

### Feedback
Regarding the OCF/Net Income Ratio, a ratio greater than 1.0 indicates high-quality earnings, as the company is converting accounting profits into actual cash. The significant outlier in 2017 (5.40) is not due to exceptional operating performance, but rather the unusually low net income caused by a one-time tax expense of $5.56 billion. Excluding this anomaly, the ratio has been consistently healthy and stable, averaging around 1.2-1.3, which is a strong sign of earnings quality.

### Testing 
Mathmatical, Knowlegde



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


## Feedback
### Testing 
Mathmatical, Knowlegde, Multi-File 







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

### Testing 
Query, Generative, Knowlegde


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
Clarification of Methodology: The dashboard was generated by first consolidating the monthly P&L and Sales data. Key ratios like Gross Profit Margin and CAC were calculated for each month, then aggregated to Q1 totals (for profit values) or averages (for ratios) for a holistic view. The variance was calculated as Actual - Target.

### Testing
Mathmatical, Query
















