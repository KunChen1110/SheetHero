import pandas as pd

# Load Titanic dataset
df = pd.read_csv("tc06_input01.csv")

# Use explicit numeric/binary features for Pearson correlation.
df["Sex"] = df["Sex"].map({"male": 0, "female": 1})
features = [
    "Sex",
    "Age",
    "Fare",
    "Pclass",
    "SibSp",
    "Parch",
    "HasCabin",
    "Embarked_C",
    "Embarked_Q",
    "Embarked_S",
]

results = {}
for col in features:
    valid = df[["Survived", col]].apply(pd.to_numeric, errors="coerce").dropna()
    results[col] = round(valid[col].corr(valid["Survived"]), 3)

output_df = pd.DataFrame([results])
output_df.to_excel("tc06_output01.xlsx", index=False)
print(output_df)
