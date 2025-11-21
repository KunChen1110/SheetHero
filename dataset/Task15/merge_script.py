import numpy as np
import pandas as pd
from scipy import stats 
import os
import matplotlib.pyplot as plt

# 读取所有数据集
df_item = pd.read_csv("olist_order_items_dataset.csv")
df_reviews = pd.read_csv("olist_order_reviews_dataset.csv")
df_orders = pd.read_csv("olist_orders_dataset.csv")
df_products = pd.read_csv("olist_products_dataset.csv")
df_geolocation = pd.read_csv("olist_geolocation_dataset.csv")
df_sellers = pd.read_csv("olist_sellers_dataset.csv")
df_order_pay = pd.read_csv("olist_order_payments_dataset.csv")
df_customers = pd.read_csv("olist_customers_dataset.csv")
df_category = pd.read_csv("product_category_name_translation.csv")

print("原始数据集大小:")
print(f"订单项目: {df_item.shape}")
print(f"订单评论: {df_reviews.shape}")
print(f"订单: {df_orders.shape}")
print(f"产品: {df_products.shape}")
print(f"地理位置: {df_geolocation.shape}")
print(f"卖家: {df_sellers.shape}")
print(f"订单支付: {df_order_pay.shape}")
print(f"客户: {df_customers.shape}")
print(f"类别翻译: {df_category.shape}")

# 第一步：将产品类别名称翻译为英文
df_products_en = df_products.merge(df_category, on='product_category_name', how='left')

# 对于没有翻译的类别，保留原始名称
df_products_en['product_category_name_english'] = df_products_en['product_category_name_english'].fillna(df_products_en['product_category_name'])

# 删除原始的葡萄牙语类别列（可选）
df_products_en = df_products_en.drop('product_category_name', axis=1)
df_products_en = df_products_en.rename(columns={'product_category_name_english': 'product_category_name'})

print(f"\n翻译后的产品数据集大小: {df_products_en.shape}")

# 第二步：逐步合并数据集
print("\n开始合并数据集...")

# 1. 从订单开始，合并订单项目
df_merged = df_orders.merge(df_item, on='order_id', how='inner')
print(f"订单 + 订单项目: {df_merged.shape}")

# 2. 合并支付信息
df_merged = df_merged.merge(df_order_pay, on='order_id', how='left')
print(f"加入支付信息: {df_merged.shape}")

# 3. 合并评论信息
df_merged = df_merged.merge(df_reviews, on='order_id', how='left')
print(f"加入评论信息: {df_merged.shape}")

# 4. 合并产品信息（使用翻译后的产品数据）
df_merged = df_merged.merge(df_products_en, on='product_id', how='left')
print(f"加入产品信息: {df_merged.shape}")

# 5. 合并客户信息
df_merged = df_merged.merge(df_customers, on='customer_id', how='left')
print(f"加入客户信息: {df_merged.shape}")

# 6. 合并卖家信息
df_merged = df_merged.merge(df_sellers, on='seller_id', how='left')
print(f"加入卖家信息: {df_merged.shape}")

# 检查最终数据集
print(f"\n最终合并数据集大小:")
print(f"行数: {df_merged.shape[0]:,}")
print(f"列数: {df_merged.shape[1]}")

print(f"\n数据集信息:")
print(f"内存使用: {df_merged.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

print(f"\n前5行预览:")
print(df_merged.head())

print(f"\n列名列表:")
for i, col in enumerate(df_merged.columns, 1):
    print(f"{i:2d}. {col}")

print(f"\n缺失值统计:")
missing_data = df_merged.isnull().sum()
missing_percent = (missing_data / len(df_merged)) * 100
missing_info = pd.DataFrame({
    '缺失数量': missing_data,
    '缺失比例%': missing_percent.round(2)
})
print(missing_info[missing_info['缺失数量'] > 0])

# 保存合并后的数据集
output_filename = "output15.xlsx"
df_merged.to_excel(output_filename, index=False)
print(f"\n合并后的数据集已保存为: {output_filename}")


# 可选：创建数据字典
data_dict = {
    '数据集': [
        '原始订单项目', '原始订单评论', '原始订单', '原始产品', 
        '地理位置', '卖家', '订单支付', '客户', '类别翻译', '合并后数据集'
    ],
    '行数': [
        df_item.shape[0], df_reviews.shape[0], df_orders.shape[0], 
        df_products.shape[0], df_geolocation.shape[0], df_sellers.shape[0],
        df_order_pay.shape[0], df_customers.shape[0], df_category.shape[0],
        df_merged.shape[0]
    ],
    '列数': [
        df_item.shape[1], df_reviews.shape[1], df_orders.shape[1],
        df_products.shape[1], df_geolocation.shape[1], df_sellers.shape[1],
        df_order_pay.shape[1], df_customers.shape[1], df_category.shape[1],
        df_merged.shape[1]
    ]
}

df_summary = pd.DataFrame(data_dict)
print(f"\n数据集汇总:")
print(df_summary)

# 保存汇总信息
df_summary.to_csv("dataset_summary.csv", index=False)
print("数据集汇总已保存为: dataset_summary.csv")