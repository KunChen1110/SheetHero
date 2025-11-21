import pandas as pd
from sklearn.linear_model import LinearRegression

# 读取数据
df = pd.read_csv("ice_cream.csv")

# 将“Did it rain on that day?”转成数值（Yes -> 1, No -> 0）
df["Did it rain on that day?"] = df["Did it rain on that day?"].map({"Yes": 1, "No": 0})

# 自变量（特征）
X = df[[
    "Temperature (F)",
    "Ice-cream Price ($)",
    "Number of Tourists (thousands)",
    "Did it rain on that day?"
]]

# 因变量（目标）
y = df["Ice Cream Sales ($,thousands)"]

# 建立线性回归模型
model = LinearRegression()
model.fit(X, y)

# 提取系数与截距
weights = model.coef_
intercept = model.intercept_

# 输出权重表
output_df = pd.DataFrame({
    "Feature": [
        "Temperature (F)",
        "Ice-cream Price ($)",
        "Number of Tourists (thousands)",
        "Did it rain on that day?",
        "Intercept"
    ],
    "Weight": list(weights) + [intercept]
})

# 保存结果为 Excel
output_df.to_excel("output7.xlsx", index=False)

print("✅ Regression weights saved to output7.xlsx")

