# Dataset

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
None



## Test4
### Task scheduling table
### Spread Sheet
[spreadsheet8](Task3/internet_penetration.xlsx)

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














