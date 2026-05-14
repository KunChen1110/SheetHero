import numpy as np
import pandas as pd
from scipy import stats 
import os
import matplotlib.pyplot as plt

# Read all the dataset
df_item = pd.read_csv("olist_order_items_dataset.csv")
df_reviews = pd.read_csv("olist_order_reviews_dataset.csv")
df_orders = pd.read_csv("olist_orders_dataset.csv")
df_products = pd.read_csv("olist_products_dataset.csv")
df_geolocation = pd.read_csv("olist_geolocation_dataset.csv")
df_sellers = pd.read_csv("olist_sellers_dataset.csv")
df_order_pay = pd.read_csv("olist_order_payments_dataset.csv")
df_customers = pd.read_csv("olist_customers_dataset.csv")
df_category = pd.read_csv("product_category_name_translation.csv")

print("Size of existing data frames : ")
print(f"Order item : {df_item.shape}")
print(f"Order review : {df_reviews.shape}")
print(f"Order : {df_orders.shape}")
print(f"Product : {df_products.shape}")
print(f"Location : {df_geolocation.shape}")
print(f"Seller  : {df_sellers.shape}")
print(f"Payment : {df_order_pay.shape}")
print(f"Client : {df_customers.shape}")
print(f"Translation : {df_category.shape}")

# translate the product name to English
df_products_en = df_products.merge(df_category, on='product_category_name', how='left')

# if no english name found, keep its original name
df_products_en['product_category_name_english'] = df_products_en['product_category_name_english'].fillna(df_products_en['product_category_name'])

# remove column product_category_name
df_products_en = df_products_en.drop('product_category_name', axis=1)
df_products_en = df_products_en.rename(columns={'product_category_name_english': 'product_category_name'})


# Merging all the dataset
print("\nMerging the dataset ...")


df_merged = df_orders.merge(df_item, on='order_id', how='inner')
print(f"Merge Order with Order ID : {df_merged.shape}")

df_merged = df_merged.merge(df_order_pay, on='order_id', how='left')
print(f"Add payment information : {df_merged.shape}")

df_merged = df_merged.merge(df_reviews, on='order_id', how='left')
print(f"Add remarks : {df_merged.shape}")


df_merged = df_merged.merge(df_products_en, on='product_id', how='left')
print(f"Add product information: {df_merged.shape}")


df_merged = df_merged.merge(df_customers, on='customer_id', how='left')
print(f"Add client information: {df_merged.shape}")

df_merged = df_merged.merge(df_sellers, on='seller_id', how='left')
print(f"Add seller information: {df_merged.shape}")


print(f"Size of final dataset\n")
print(f"rows: {df_merged.shape[0]:,}")
print(f"columns: {df_merged.shape[1]}")

print(f"\nDataset info:")
print(f"Memory usage: {df_merged.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

print(f"\nPreview of first 5 rows:")
print(df_merged.head())

print(f"\nList of column names:")
for i, col in enumerate(df_merged.columns, 1):
    print(f"{i:2d}. {col}")

print(f"\nMissing value statistics:")
missing_data = df_merged.isnull().sum()
missing_percent = (missing_data / len(df_merged)) * 100
missing_info = pd.DataFrame({
    'Missing Count': missing_data,
    'Missing Percentage (%)': missing_percent.round(2)
})
print(missing_info[missing_info['Missing Count'] > 0])

# Save merged dataset
output_filename = "output15.xlsx"
df_merged.to_excel(output_filename, index=False)
print(f"\nMerged dataset saved as: {output_filename}")


# Optional: Create dataset summary dictionary
data_dict = {
    'Dataset': [
        'Original Order Items', 'Original Order Reviews', 'Original Orders', 'Original Products',
        'Geolocation', 'Sellers', 'Order Payments', 'Customers', 'Category Translation', 'Merged Dataset'
    ],
    'Rows': [
        df_item.shape[0], df_reviews.shape[0], df_orders.shape[0],
        df_products.shape[0], df_geolocation.shape[0], df_sellers.shape[0],
        df_order_pay.shape[0], df_customers.shape[0], df_category.shape[0],
        df_merged.shape[0]
    ],
    'Columns': [
        df_item.shape[1], df_reviews.shape[1], df_orders.shape[1],
        df_products.shape[1], df_geolocation.shape[1], df_sellers.shape[1],
        df_order_pay.shape[1], df_customers.shape[1], df_category.shape[1],
        df_merged.shape[1]
    ]
}

df_summary = pd.DataFrame(data_dict)
print(f"\nDataset Summary:")
print(df_summary)

# Save summary information
df_summary.to_csv("dataset_summary.csv", index=False)
print("Dataset summary saved as: dataset_summary.csv")
