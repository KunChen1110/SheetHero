import pandas as pd
from sklearn.linear_model import LinearRegression

# Read csv
df = pd.read_csv("tc07_input01.csv")

# Coverting “Did it rain on that day?” to numerical value（Yes -> 1, No -> 0）
df["Did it rain on that day?"] = df["Did it rain on that day?"].map({"Yes": 1, "No": 0})

# Feature variable
X = df[[
    "Temperature (F)",
    "Ice-cream Price ($)",
    "Number of Tourists (thousands)",
    "Did it rain on that day?"
]]

# Target variable
y = df["Ice Cream Sales ($,thousands)"]

# Use linear regression model
model = LinearRegression()
model.fit(X, y)

# Extract weights
weights = model.coef_
intercept = model.intercept_

# Output the weight table
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

# save the result to Excel
output_df.to_excel("output7.xlsx", index=False)

print("✅ Regression weights saved to output7.xlsx")

