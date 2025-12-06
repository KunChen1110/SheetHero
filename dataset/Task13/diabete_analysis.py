import pandas as pd

# ---- 读取 Number of Diabetics (input2.xlsx) ----
df_population = pd.read_excel("tc13_input02.xlsx", sheet_name=1, header=None, skiprows=4)
df_population = df_population[[1, 2]]  # 第二列 Region，第三列 Value
df_population.columns = ["Region", "Number of Diabetics (millions)"]
df_population["Number of Diabetics (millions)"] = pd.to_numeric(df_population["Number of Diabetics (millions)"], errors='coerce')

# ---- 读取 Expenditure (input3.xlsx) ----
df_expenditure = pd.read_excel("tc13_input03.xlsx", sheet_name=1, header=None, skiprows=4)
df_expenditure = df_expenditure[[1, 2]]  # 第二列 Region，第三列 Value
df_expenditure.columns = ["Region", "Expenditure (billion USD)"]
df_expenditure["Expenditure (billion USD)"] = pd.to_numeric(df_expenditure["Expenditure (billion USD)"], errors='coerce')

# ---- 按 Region 合并 ----
df = pd.merge(df_population, df_expenditure, on="Region", how="inner")

# ---- 计算 Share 和 Avg Expenditure ----
total_diabetics = df["Number of Diabetics (millions)"].sum()
df["Share of Global (%)"] = (df["Number of Diabetics (millions)"] / total_diabetics) * 100
df["Avg Expenditure per Person (USD)"] = (
    df["Expenditure (billion USD)"] * 1e9 / (df["Number of Diabetics (millions)"] * 1e6)
)

# ---- 输出 Excel ----
df.to_excel("output13.xlsx", index=False)

print("✅ Diabetes regional analysis saved to output13.xlsx")


