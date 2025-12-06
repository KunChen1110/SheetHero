import pandas as pd
import matplotlib.pyplot as plt

# ---- Read the form ----
file_path = "tc03_input01.xlsx"
df = pd.read_excel(file_path, sheet_name=1, header=4, engine="openpyxl")
print(df.head(10))


# ---- clean the columns ----

df.rename(columns={"Unnamed: 1": "Year"}, inplace=True)
df = df.drop(columns=["Unnamed: 0", "Unnamed: 8"], errors="ignore")

# ---- convert year to int ----
df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
df = df.dropna(subset=["Year"]).astype({"Year": int})

# ---- filter year between 2020-2024 ----
df_2020_2024 = df[df["Year"].between(2020, 2024)].copy()

if df_2020_2024.empty:
    raise ValueError("❌ No data found from 2020 - 2024")

# ---- Calculate the average ----
avg_penetration = df_2020_2024.iloc[:, 1:].mean().reset_index()
avg_penetration.columns = ["Region", "Avg Penetration (2020–2024)"]

# ---- Calculate the growth rate ----
growth = (
    df_2020_2024[df_2020_2024["Year"] == 2024].iloc[:, 1:].values[0] -
    df_2020_2024[df_2020_2024["Year"] == 2021].iloc[:, 1:].values[0]
)
growth_df = pd.DataFrame({
    "Region": df_2020_2024.columns[1:],
    "Growth (2020–2024)": growth
})

# ---- Merge the result and sorting ----
result = pd.merge(avg_penetration, growth_df, on="Region")
result = result.sort_values(by="Growth (2020–2024)", ascending=False)

# ---- Print the output to excel ----
result.to_excel("output3.xlsx", index=False)
print("✅ 分析结果：")
print(result)

# ---- Paint the trending graph ----
df_2020_2024.set_index("Year", inplace=True)
df_2020_2024.plot(kind="line", marker="o", figsize=(8, 5))
plt.title("Internet Penetration Rate by Region (2020–2024)")
plt.xlabel("Year")
plt.ylabel("Penetration Rate (%)")
plt.legend(title="Region")
plt.grid(True)
plt.tight_layout()
plt.savefig("internet_trend.png")
plt.show()


