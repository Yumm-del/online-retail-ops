# -*- coding: utf-8 -*-
"""
02_clean.py —— 数据清洗与退货配对
目的：把原始交易流水清洗成两份可用于分析的明细：
      clean_sales.csv    全部有效销售行（含无 CustomerID 的零售流水）
      clean_customer.csv 有 CustomerID 的有效销售行（用于 RFM / 留存）
输入：data/interim/raw.pkl
输出：data/clean/*.csv、data/cleaning_log.txt
原理：
  1) 去完全重复行；
  2) 区分「销售」与「退货/冲销」——InvoiceNo 以 C 开头，或数量为负；
  3) 退货与原单配对：同客户 + 同商品 + 同单价 + 数量绝对值相同，
     取退货时间之前最近的一笔未匹配销售。配对成功后**两边一起剔除**；
     否则会出现「原单 +£168k、退货单 -£168k 被删掉」的幽灵收入；
  4) 无法配对的退货保留为负收入（真实退货），用于净收入口径；
  5) 剔除手续费、邮费、坏账调整等非商品行，避免污染商品与收入分析。
"""
import bisect
import os
from collections import defaultdict

import pandas as pd

BASE = r"D:\file_of_claude\online-retail-ops"
RAW_PKL = os.path.join(BASE, "data", "interim", "raw.pkl")
CLEAN_DIR = os.path.join(BASE, "data", "clean")
LOG = os.path.join(BASE, "data", "cleaning_log.txt")
os.makedirs(CLEAN_DIR, exist_ok=True)

# 非商品类编码：邮费、手工调整、坏账、银行费用、测试单等
NON_PRODUCT_CODES = {
    "POST", "D", "M", "DOT", "BANK CHARGES", "AMAZONFEE",
    "PAD", "CRUK", "B", "TEST001", "TEST002", "SP1002",
}

df = pd.read_pickle(RAW_PKL)
log = []
add = log.append


def section(title):
    add("")
    add(f"--- {title} ---")


add("=" * 60)
add("清洗日志")
add("=" * 60)
add(f"原始行数：{len(df):,}")

# 1. 去重
dup_n = df.duplicated().sum()
df = df.drop_duplicates().copy()
add(f"去除完全重复行：{dup_n:,}，剩余 {len(df):,}")

# 2. 计算金额、标记退货
df["Revenue"] = df["Quantity"] * df["UnitPrice"]
df["IsCancellation"] = (
    df["InvoiceNo"].astype(str).str.startswith("C") | (df["Quantity"] < 0)
)

# 3. 剔除非商品行
non_product = df["StockCode"].astype(str).isin(NON_PRODUCT_CODES)
add(f"剔除非商品行（邮费/调整/坏账等）：{non_product.sum():,}，"
    f"金额 {df.loc[non_product, 'Revenue'].sum():,.2f}")
df = df[~non_product].copy()

# 4. 拆销售与退货
sales = df[(~df["IsCancellation"]) & (df["Quantity"] > 0) & (df["UnitPrice"] > 0)].copy()
cancel = df[df["IsCancellation"]].copy()
# 负单价但非退货的行（如调整）单独记录，不进入销售也不进入退货
other = df[(~df["IsCancellation"]) & ((df["Quantity"] <= 0) | (df["UnitPrice"] <= 0))].copy()

section("口径拆分")
add(f"有效销售行：{len(sales):,}，金额 {sales['Revenue'].sum():,.2f}")
add(f"退货/冲销行：{len(cancel):,}，金额 {cancel['Revenue'].sum():,.2f}")
add(f"其他异常行（负价/零价非退货）：{len(other):,}，金额 {other['Revenue'].sum():,.2f}")

# 5. 退货与原单配对
# 配对键：客户 + 商品 + 单价（保留两位）+ 数量绝对值
sales["_key"] = list(zip(
    sales["CustomerID"], sales["StockCode"],
    sales["UnitPrice"].round(2), sales["Quantity"].abs().astype(int),
))

pool = defaultdict(list)  # key -> [(时间, 行索引)]，按时间升序
for idx, r in sales.iterrows():
    if pd.notna(r["CustomerID"]):
        pool[r["_key"]].append((r["InvoiceDate"], idx))
for k in pool:
    pool[k].sort()

matched_sales = set()
matched_cancel = set()

for idx, r in cancel.sort_values("InvoiceDate").iterrows():
    if pd.isna(r["CustomerID"]):
        continue
    key = (r["CustomerID"], r["StockCode"], round(r["UnitPrice"], 2),
           abs(int(r["Quantity"])))
    lst = pool.get(key)
    if not lst:
        continue
    # 找退货时间之前、最近一笔尚未匹配的销售（LIFO）
    pos = bisect.bisect_right(lst, (r["InvoiceDate"], float("inf"))) - 1
    while pos >= 0 and lst[pos][1] in matched_sales:
        pos -= 1
    if pos >= 0 and lst[pos][0] <= r["InvoiceDate"]:
        matched_sales.add(lst[pos][1])
        matched_cancel.add(idx)

# 配对成功的双边一起剔除
sales_valid = sales.drop(index=list(matched_sales)).drop(columns="_key")
cancel_unmatched = cancel.drop(index=list(matched_cancel))

section("退货配对结果")
add(f"配对成功的退货：{len(matched_cancel):,} 行，对应销售 {len(matched_sales):,} 行")
add(f"配对金额（销售侧）：{sales.loc[list(matched_sales), 'Revenue'].sum():,.2f}")
add(f"未配对退货（作为负收入保留）：{len(cancel_unmatched):,} 行，"
    f"金额 {cancel_unmatched['Revenue'].sum():,.2f}")

# 6. 关键案例：那张 16.8 万英镑的发票
big = df[df["InvoiceNo"].astype(str) == "581483"]
if len(big):
    ok = "已配对剔除" if big.index[0] in matched_sales else "未配对（仍在销售中）"
    add(f"最大单 581483（PAPER CRAFT, LITTLE BIRDIE，£168,469.60）：{ok}")

# 7. 客户维度数据
customer = sales_valid[sales_valid["CustomerID"].notna()].copy()
customer["CustomerID"] = customer["CustomerID"].astype(int)

# 8. 净收入序列 = 有效销售 + 未配对退货（负数）
net = pd.concat([sales_valid, cancel_unmatched], ignore_index=True)

section("最终产出")
add(f"clean_sales.csv：{len(sales_valid):,} 行，收入 {sales_valid['Revenue'].sum():,.2f}")
add(f"clean_customer.csv：{len(customer):,} 行，"
    f"客户 {customer['CustomerID'].nunique():,} 人，收入 {customer['Revenue'].sum():,.2f}")
add(f"无客户 ID 销售占比：{sales_valid['CustomerID'].isna().mean():.2%}")
add(f"时间范围：{sales_valid['InvoiceDate'].min()} 至 {sales_valid['InvoiceDate'].max()}")

# 输出
sales_valid.to_csv(os.path.join(CLEAN_DIR, "clean_sales.csv"), index=False)
customer.to_csv(os.path.join(CLEAN_DIR, "clean_customer.csv"), index=False)
net.to_csv(os.path.join(CLEAN_DIR, "clean_net.csv"), index=False)
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(log))
print("清洗完成：", LOG)
