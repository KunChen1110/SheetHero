import pandas as pd

# Load temp table
df = pd.read_excel("temp.xlsx")

# List of brand columns
brands = ["Vivo", "Samsung", "Xiaomi", "Oppo", "Apple", "Realme", "Lenovo", "Others"]

# Replace '-' with 0 and convert to numeric
for col in brands:
    df[col] = pd.to_numeric(df[col].replace("-", 0), errors="coerce").fillna(0)

# Compute unit shipment for each brand
for col in brands:
    df[col + " (Unit shipment)"] = df["Total Shipment"] * df[col] / 100

# Select output columns
output_cols = ["Year"] + [b + " (Unit shipment)" for b in brands]
output_df = df[output_cols]

# Save
output_df.to_excel("output5.xlsx", index=False)

print(output_df.head())



