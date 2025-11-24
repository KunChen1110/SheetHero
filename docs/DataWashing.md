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
The system will check for any empty headers and ask user to either delete coloumn or add header
### Step 3
The system will check for any empty columns with a header, if empty will ask user if the coloumn should be deleted or if the user needs to fill it in.
### Step 4
The system will remove all duplicate data from each of the files provided, duplicate data will not cross over files. for example if 2 files has the same data they won't be touched.
### Step 5
The system will make all letters lowercase to reduce system complexity.
### Step 6
The System will go down each coloumn looking for formating issues.




