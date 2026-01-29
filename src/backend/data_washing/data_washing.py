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
                    