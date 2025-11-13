import pandas as pd

# 读取数据
df = pd.read_csv("mobile_review.csv")

# 按国家和品牌聚合平均评分和评论数量
country_brand_rating = df.groupby(["country", "brand"]).agg(
    avg_rating=("rating", "mean"),
    num_reviews=("rating", "count")
).reset_index()

# 输出 Excel
country_brand_rating.to_excel("country_brand_avg_rating.xlsx", index=False)

print("✅ Country-brand average rating saved to country_brand_avg_rating.xlsx")
