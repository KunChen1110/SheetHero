import pandas as pd

# Load the Iris dataset from CSV
# Make sure the file path is correct relative to your script
df = pd.read_csv("IRIS.csv")

# Filter the dataset for species Iris-setosa
df_setosa = df[df["species"] == "Iris-setosa"]

# Select only numeric columns
numeric_cols = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
df_numeric = df_setosa[numeric_cols]

# Compute the correlation matrix
corr_matrix = df_numeric.corr()

# Round to 2 decimal places
corr_matrix = corr_matrix.round(2)

# Print label and the matrix
print("Correlation Matrix for Iris-setosa:")
corr_matrix.to_excel("output8.xlsx", index=False)
