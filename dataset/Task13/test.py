import pandas as pd

xlsx_pop = "input3.xlsx"
df_population = pd.read_excel(xlsx_pop, sheet_name=1, header=5)
print(df_population.columns.tolist())