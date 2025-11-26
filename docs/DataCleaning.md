# Data cleaning Research
## Probelms to solve
The first step is to outline the problems this sub-system is to fix.
1. Missing Data
2. Inconsistant Data
3. Duplicate Data

## Problems Description
### Missing Data
This is where a cell or up to a column or row has no data inputed
### Inconsistant Data
This is where a column has inconsistant formating of its data
### Duplicate Data
This is where a row is repeted on the same file
### Multi-Value Columns
This is where in a single coloumn multiple values are stored which should be seperated
### Multiple Datasets On The Same Sheet
This would need to be seperated onto differant sheets per dataset

## Research For Other Systems
### Ultimate Suite for Microsoft Excel from Ablebits
this is an excel add-on which can find and solve many of the issues.such as, Merge, Compare differances, remove duplicate data. However, as this is an add-on for excel, i dont think it can be automated which is fine for small scale but not for large as it would have to manually done for all files which would take an expenational amount of time. but it is free. It also goes outside of the scope of this sub-system, which could cause misunderstanding with other sub-systems.
### CleanMyExcel.io
Can't find any issues as it does exactly what we need it to do. The only issue is that i can't see how it deals with missing dat and also don't have access to the source code.

## Conclusion
For a fully comprohensive and robust data cleaning system, it would require a lot of time and manpower to create. This would be the the detrimant to the main system and its goals. It would be possible to create a simplier system which wouldn't be harmful the the main system, however this would require more input and work from the user to use. for example problems, 2,4,5 would be flaged to the use to either ignore, or fix manually. This would be a working system, However for large datasets it could become time consuming for the user.

# Data Cleaning Proposal
## Introduction
This system will automatically fix issues that require little to no user input. This will mainly cover issues 1,2,3. For any other issues the system will flag the potential problem to the user and request their input. either for the user to manually fix the issue, or if it isn't an issue to ignore it. The system will also be case insenstive, so all letters will be lower case.
## Sub-System Overview
I would create a 'Rules' file, this file would be able to save simple comands from the user. for examples, if the user said room codes are 'C80' instead of 'C 80'. The user will then be able to appply this file to other excel files, this is to save time, as for large datasets many of the same issues will reoccour. The 'Rules' file will be either another excel sheet or and most likely a CSV file.
## Rules File Layout
| File Number | Problems Header | Solution |
| ----------- | --------------- | -------- |
| 1           | Room Number     | Insert Function |
| ... | ... | ... |
### Functions
1. Remove White Space
2. Return Location To User( Will also be known as Flag to user )
More to be added during testing, if a function has not be made, the standard will be to return location to user, this is so no errors should occour
## Main Functions
1. LowerCase
2. RmDuplicate
## Operation
### Step 1
The system will remove all empty rows
### Step 2
The system will check for any empty headers and ask user to either delete coloumn or add header only if coloumn contains data 
### Step 3
The system will check for any empty columns with a header, if empty will ask user if the coloumn should be deleted or if the user needs to fill it in.
### Step 4
The system will make all letters lowercase to reduce system complexity.
### Step 5
The system will remove all duplicate data from each of the files provided, duplicate data will not cross over files. for example if 2 files has the same data they won't be touched.
### Step 6
The System will go down each coloumn looking for formating issues.
## Design 
### Input 
| Needs | Optional |
| ---- | ---- |
| Excel File | Rules File |
| | Return Location | 
### Output 
Excel File and Rules File(Return Loaction)

# Dev Log
## Creating Test Table
After creating a test table which includes all the problems that this system will solve, i noticed that a few of the steps need to be rearranged, as otherwise they will not work 
### Problems Included
1. Empty Rows
2. Empty Coloumns
3. Empty Headers 
4. Empty Cells 
5. Duplicate Data 
6. Formating Errors
### Rearranged Steps
#### Step 1
The system will remove all empty rows
#### Step 2 
Remove empty coloumns
#### Step 3
The system will make all letters lowercase to reduce system complexity.
#### Step 4
The system will go through the file and ask the user to input missing data, or if the user wants to delete the row or the column 
#### Step 5
The System will go down each coloumn looking for formating issues.
#### Step 6
The system will remove all duplicate data from each of the files provided, duplicate data will not cross over files. for example if 2 files has the same data they won't be touched.
## Libaries
### openpyxl
For operating on the excel file
## Functions
### init 
have 2 parameters needed, the excel files path and the rules file path. ruleactive lets the system know if it needs to check the rule file for solutions. if at any point ruleactive becomes true a rules file will be made and used until the processes is finished. When called it uses a function main().
### main 
this function will run the data cleaning operation, so the main system will only have to call the class and then it will clean the excel by itself with no other input from the rest of the system. This was done to increase the isolation of this sub-system and to reduce any integration errors.
### RmEmptyRows
My current code is this:
def main(self):
        workbook = load_workbook(filename="src/backend/examples/test_table_data_washing (copy).xlsx")
        for sheet in workbook: 
            self.RmEmptyRow(sheet)
        workbook.save(filename="src/backend/examples/test_table_data_washing (copy).xlsx")

    def RmEmptyRow(self,sheet): 
        index = 1
        for row in sheet.rows:
            empty = False
            for cell in row:
                if(cell.value == None):
                    empty = True 
            if(empty):
                sheet.delete_rows(index)
            empty = False
            print(index)
            index += 1
what i have found after running it is that it will continously delete rows, will have to find reason.
The solution was to swap the Trues and Falses and check for not None.
### RmEmptyCols 
Reused the code for empty rows, but changed for columns
### EmptyData
Had to make the system save the files after removing the empty rows and columns, otherwise the user when asked to fill in data via the system, they may want to check the location to confirm they action, the file is not updated in real-time so by saving it the user can see the changed file.
My current code is :
def EmptyData(self,sheet):
        for row in sheet.rows:
            for cell in row:
                if(cell.value == None):
                    inp = input("At location " + cell.coordinate + " on sheet "+sheet.title+" from file " + self.excel + " is missing data do you wish to add data or remove row or column \n to remove row type RmRow "
                    "\n to remove column type RmCol \n to add data type your data \n Type here: ")
                    if(inp == "RmRow"):
                        sheet.delete_rows(cell.row)
                    elif(inp == "RmCol"):
                        sheet.delete_cols(cell.column)
                    else:
                        sheet[cell.coordinate] = inp
however when the user deletes a column or row, it gets deleted but the system does not update the demensions of the new table. The solution is to just save the table after each deletion. Thats why i have made the excel path a global.I also have to pass through the workbook to be able to save. An issue arises that even when saved the demsions don't update as they are saved early on when the for loops are first created. One solution would use recurrsio n however the worry would be that for large datasets the recussion would be to large and cause errors from stackoverflow.Another solution would be to have 2 lists which check if that column or row has been deletd, if so move on the next location.
Used solution 2.
def EmptyData(self,workbook,sheet):
        EmRow = []
        EmCol = []
        for row in sheet.rows:
            for cell in row:
                if(cell.value == None):
                    if( (not (cell.row in EmRow)) and (not (cell.column in EmCol))):
                        inp = input("At location " + cell.coordinate + " on sheet "+sheet.title+" from file " + self.excel + " is missing data do you wish to add data or remove row or column \n to remove row type RmRow "
                        "\n to remove column type RmCol \n to add data type your data \n Type here: ")
                        if(inp == "RmRow"):
                            EmRow.append(cell.row)
                            sheet.delete_rows(cell.row)
                            workbook.save(filename="src/backend/examples/test_table_data_washing (copy).xlsx")
                        elif(inp == "RmCol"):
                            EmCol.append(cell.column)
                            sheet.delete_cols(cell.column)
                            workbook.save(filename="src/backend/examples/test_table_data_washing (copy).xlsx")
                        else:
                            sheet[cell.coordinate] = inp
### LowerCase
Go through all cells and if they are a string remove any leading whitespace and lowercase it
### Format
This will be hard, as i can try and use string comparsens to make a standard format for each column, but due to the amount of differant possible formats it would be hard to code without any bugs. can just check to see if the column has the same type but this will miss issues, such as 'C80' == 'C 80'. Can ask the user for the format, for example for the room numbers the user would input 'X1_1' this would signfy that it starts with a letter and has a number, if they put 'X3_1' this would represent that the format is 3 letters followed by a number. so for 'C80' the format would be 'X1_2'. Other types would be '.','/','\','#',':','(',')',' ','-','|'. After looking at a larger dataset i believe that my solution would be to time consuming and cumbersome to use as the user will be filling out the format for every column. the only way to do this to any standard for many types of datasets would be to use a ai model trained to spot these issues, at the same time the model could be trained to spot errounous errors. if we were going for this, i will make another document to create a plan. another option is for the main system to spot these errors, but then i believe we may be over loading the main system, as for every query made by the user the system will have to check for duplicates due to formating errors. the errouns data could be left to the main system, as it would be more in line with the rest of its responsablities.
## Conclusion
The system works, apart from the formating issues. this causes issues with duplicates. as it dosen't see 'C80','C 80', and '80c' as the same when they could be. other problems is when asking the user to fill in missing data for every sheet the user will have to close the excel file and reload it to see changes when asked to fill data, as the system dosen't remove all empty rows for all sheets at the same time for example.
My code is this:

from openpyxl import *

class datawashing: 

    def __init__(self,excel):
        self.excel = excel
        self.main()
        

    def main(self):
        workbook = load_workbook(filename=self.excel)
        for sheet in workbook: 
            self.RmEmptyRow(sheet)
            self.RmEmptyCols(sheet)
            self.LowerCase(sheet)
            self.RmDupli(sheet)
            workbook.save(filename=self.excel)
            self.EmptyData(workbook,sheet)
            workbook.save(filename=self.excel)

    def RmEmptyRow(self,sheet): 
        index = 1
        for row in sheet.rows:
            empty = True
            for cell in row:
                if(cell.value != None):
                    empty = False 
            if(empty):
                sheet.delete_rows(index)
            index += 1    
        
    def RmEmptyCols(self,sheet):
        index = 1
        for col in sheet.columns:
            empty = True
            for cell in col:
                if(cell.value != None):
                    empty = False 
            if(empty):
                sheet.delete_cols(index)
            index += 1
    

    def EmptyData(self,workbook,sheet):
        EmRow = []
        EmCol = []
        for row in sheet.rows:
            for cell in row:
                if(cell.value == None):
                    if( (not (cell.row in EmRow)) and (not (cell.column in EmCol))):
                        inp = input("At location " + cell.coordinate + " on sheet "+sheet.title+" from file " + self.excel + " is missing data do you wish to add data or remove row or column \n to remove row type RmRow "
                        "\n to remove column type RmCol \n to add data type your data \n Type here: ")
                        if(inp == "RmRow"):
                            EmRow.append(cell.row)
                            sheet.delete_rows(cell.row)
                            workbook.save(filename=self.excel)
                        elif(inp == "RmCol"):
                            EmCol.append(cell.column)
                            sheet.delete_cols(cell.column)
                            workbook.save(filename=self.excel)
                        else:
                            sheet[cell.coordinate] = inp

    def LowerCase(self,sheet):
        for row in sheet.rows:
            for cell in row: 
                if(type(cell.value) == str):
                    sheet[cell.coordinate] = cell.value.lstrip()
                    sheet[cell.coordinate] = cell.value.lower()

    

    def RmDupli(self,sheet):
        rows = []
        index = 1
        for row in sheet.rows:
            if(row in rows):
                sheet.delete_rows(index)
            else:
                rows.append(row)
            index += 1


I have removed rule,as it would only be applicable to formating issues, and as discussed above haven't done that in this document. The system can be optimised more as it goes through the entire dataset multiple times, which could be condensed. for a working prototype i think this system is sufficant. changes can be made in the future.


