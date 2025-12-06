import os
import json
import re

# ==== 1. 按出现顺序建立要处理的文件列表 ====
file_list = [
    "olist_order_items_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_customers_dataset.csv",
    "product_category_name_translation.csv"
]

# ==== 2. 自动生成新的文件名并重命名 ====
mapping = {}  # old → new

for idx, old_name in enumerate(file_list, start=1):
    new_name = f"tc15_input{idx:02d}.csv"

    if os.path.exists(old_name):
        print(f"Renaming {old_name} → {new_name}")
        os.rename(old_name, new_name)
        mapping[old_name] = new_name
    else:
        print(f"WARNING: file not found: {old_name}")

# ==== 3. 修改 Python 脚本（比如 main.py） ====
target_script = "merge_script.py"   # 修改这里为你的实际 Python 文件

with open(target_script, "r") as f:
    code = f.read()

for old, new in mapping.items():
    print(f"Updating reference {old} → {new}")
    code = code.replace(f'"{old}"', f'"{new}"')

with open(target_script, "w") as f:
    f.write(code)

# ==== 4. 保存映射到 mapping.json ====
with open("tc15_mapping.json", "w") as f:
    json.dump(mapping, f, indent=4)

print("\n=== Done ===")
print("所有文件已重命名并同步更新 Python 脚本。")
print("mapping 已输出到 tc15_mapping.json")
