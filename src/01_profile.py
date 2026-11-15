# -*- coding: utf-8 -*-
"""
01_profile.py —— 原始数据体检
目的：在做任何分析之前，先摸清数据的规模、质量问题与口径边界。
输入：data/raw/Online Retail.xlsx
输出：data/interim/raw.pkl（加速后续读取）、data/profile.txt（体检报告）
原理：把「缺失、重复、退货、异常价格、时间范围」逐项量化，后面清洗时才知道
      每一步丢掉了多少数据、为什么丢，避免拍脑袋删行。
"""
import os

import pandas as pd

BASE = r"D:\file_of_claude\online-retail-ops"
RAW_XLSX = os.path.join(BASE, "data", "raw", "Online Retail.xlsx")
OUT_TXT = os.path.join(BASE, "data", "profile.txt")
OUT_PKL = os.path.join(BASE, "data", "interim", "raw.pkl")

os.makedirs(os.path.dirname(OUT_PKL), exist_ok=True)

# 读取原始表：这是 UCI 提供的唯一 sheet
df = pd.read_excel(RAW_XLSX, sheet_name="Online Retail")

lines = []
add = lines.append
add("=" * 60)
add("原始数据体检报告")
add("=" * 60)
add(f"行数 × 列数：{df.shape[0]:,} × {df.shape[1]}")
add(f"列名：{list(df.columns)}")
add("")
add("--- 字段类型 ---")
add(df.dtypes.to_string())
add("")
add("--- 缺失值 ---")
miss = df.isna().sum()
for col, n in miss.items():
    add(f"{col}: {n:,}（{n / len(df):.2%}）")
add("")
add("--- 时间范围 ---")
add(f"最早：{df['InvoiceDate'].min()}")
add(f"最晚：{df['InvoiceDate'].max()}")
add("")
add("--- 规模指标 ---")
add(f"唯一订单号 InvoiceNo：{df['InvoiceNo'].nunique():,}")
add(f"唯一商品编码 StockCode：{df['StockCode'].nunique():,}")
add(f"唯一客户 CustomerID：{df['CustomerID'].nunique():,}（不含缺失）")
add(f"国家/地区：{df['Country'].nunique():,}")
add("")
add("--- 质量问题 ---")
dup = df.duplicated().sum()
add(f"完全重复行：{dup:,}")
cancel = df["InvoiceNo"].astype(str).str.startswith("C").sum()
add(f"退货单（InvoiceNo 以 C 开头）：{cancel:,}")
neg_qty = (df["Quantity"] <= 0).sum()
add(f"数量 ≤ 0 的行：{neg_qty:,}")
nonpos_price = (df["UnitPrice"] <= 0).sum()
add(f"单价 ≤ 0 的行：{nonpos_price:,}（含赠品/坏账调整）")
add("")
add("--- 缺失 CustomerID 的影响 ---")
no_cust = df["CustomerID"].isna()
rev = (df["Quantity"] * df["UnitPrice"])
add(f"无 CustomerID 行数：{no_cust.sum():,}，占金额 {rev[no_cust].sum() / rev.sum():.2%}")
add(f"有 CustomerID 行数：{(~no_cust).sum():,}，占金额 {rev[~no_cust].sum() / rev.sum():.2%}")
add("")
add("--- 国家 Top 10（按行数） ---")
add(df["Country"].value_counts().head(10).to_string())
add("")
add("--- 金额极值 ---")
add(f"Quantity 最小/最大：{df['Quantity'].min():,.0f} / {df['Quantity'].max():,.0f}")
add(f"UnitPrice 最小/最大：{df['UnitPrice'].min():,.2f} / {df['UnitPrice'].max():,.2f}")
add(f"单行最大金额：{rev.max():,.2f}")

with open(OUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("profile written:", OUT_TXT)

# 存一份 pickle，后续脚本直接读，避免反复解析 20 多 MB 的 xlsx
df.to_pickle(OUT_PKL)
print("pickle written:", OUT_PKL)
