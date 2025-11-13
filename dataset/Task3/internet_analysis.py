import pandas as pd
import matplotlib.pyplot as plt

# ---- 读取表格 ----
file_path = "internet_penetration.xlsx"
df = pd.read_excel(file_path, sheet_name=1, header=4, engine="openpyxl")
print(df.head(10))
# ---- 清理列 ----
# 使用 Unnamed: 1 作为年份
df.rename(columns={"Unnamed: 1": "Year"}, inplace=True)

# 删除多余列
df = df.drop(columns=["Unnamed: 0", "Unnamed: 8"], errors="ignore")

# ---- 转换年份为整数 ----
df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
df = df.dropna(subset=["Year"]).astype({"Year": int})

# ---- 筛选 2020–2024 ----
df_2020_2024 = df[df["Year"].between(2020, 2024)].copy()

if df_2020_2024.empty:
    raise ValueError("❌ 没有找到 2020–2024 年的数据，请检查表格内容。")

# ---- 计算平均值 ----
avg_penetration = df_2020_2024.iloc[:, 1:].mean().reset_index()
avg_penetration.columns = ["Region", "Avg Penetration (2020–2024)"]

# ---- 计算增长率 ----
growth = (
    df_2020_2024[df_2020_2024["Year"] == 2024].iloc[:, 1:].values[0] -
    df_2020_2024[df_2020_2024["Year"] == 2021].iloc[:, 1:].values[0]
)
growth_df = pd.DataFrame({
    "Region": df_2020_2024.columns[1:],
    "Growth (2020–2024)": growth
})

# ---- 合并结果并排序 ----
result = pd.merge(avg_penetration, growth_df, on="Region")
result = result.sort_values(by="Growth (2020–2024)", ascending=False)

# ---- 输出结果 ----
result.to_excel("output3.xlsx", index=False)
print("✅ 分析结果：")
print(result)

# ---- 绘制趋势图 ----
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


