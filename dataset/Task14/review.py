import pandas as pd

# read the file
df = pd.read_csv("tc14_input01.csv")

# group the rating by brand 
country_brand_rating = df.groupby(["country", "brand"]).agg(
    avg_rating=("rating", "mean"),
    num_reviews=("rating", "count")
).reset_index()

# ouput Excel
country_brand_rating.to_excel("output14.xlsx", index=False)

print("✅ Country-brand average rating saved to country_brand_avg_rating.xlsx")
