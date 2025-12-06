import pandas as pd
from scipy.stats import pearsonr

# Load Titanic dataset
df = pd.read_csv("tc06_input01".csv)

# Check missing values
if df.isnull().values.any():
    print("Feedback: I found missing values — how would you like me to handle them? Can I treat them as NULL?")

# Encode categorical variables
df['Sex'] = df['Sex'].map({'male': 0, 'female': 1})
df['Embarked'] = df['Embarked'].map({'S': 0, 'C': 1, 'Q': 2})
df['Cabin'] = df['Cabin'].notnull().astype(int)  # 1 if cabin info exists, else 0

# Columns to correlate with 'Survived'
factors = ['Sex', 'Age', 'Fare', 'Cabin', 'Embarked']

# Compute Pearson correlation
results = {}
for col in factors:
    valid = df[['Survived', col]].dropna()
    if valid[col].nunique() > 1:  # to avoid constant variable errors
        corr, _ = pearsonr(valid['Survived'], valid[col])
        results[col] = corr
    else:
        results[col] = None

# Create output DataFrame
output_df = pd.DataFrame([results])

# Save to Excel
output_df.to_excel("output6.xlsx", index=False)

print("### Answer")
print(output_df)
print("\n### Output")
print("Saved as titanic_correlation.xlsx")
