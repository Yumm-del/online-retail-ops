# -*- coding: utf-8 -*-
"""
06_lifecycle.py —— 新老客结构（生命周期视角）
目的：把每月收入拆成「新客首购」与「老客复购」，判断增长靠拉新还是靠留存。
输入：data/clean/clean_customer.csv
输出：data/analysis/monthly_new_returning.csv、charts/new_vs_returning.png
原理：每个客户取首次购买月份；当月收入按「首次购买月 == 当月」分为新客收入，
      其余为老客收入；同时统计新客/老客人数，避免只看金额不看人头。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = r"D:\file_of_claude\online-retail-ops"
CLEAN = os.path.join(BASE, "data", "clean", "clean_customer.csv")
OUT_DIR = os.path.join(BASE, "data", "analysis")
CHART_DIR = os.path.join(BASE, "charts")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_csv(CLEAN, parse_dates=["InvoiceDate"])
df["Month"] = df["InvoiceDate"].dt.to_period("M")
df["FirstMonth"] = df.groupby("CustomerID")["InvoiceDate"].transform("min").dt.to_period("M")
df["IsNew"] = df["Month"] == df["FirstMonth"]

monthly = df.groupby(["Month", "IsNew"]).agg(
    Revenue=("Revenue", "sum"),
    Customers=("CustomerID", "nunique"),
    Orders=("InvoiceNo", "nunique"),
).reset_index()

wide = monthly.pivot(index="Month", columns="IsNew",
                     values=["Revenue", "Customers", "Orders"]).fillna(0)
wide.columns = [f"{'New' if c[1] else 'Returning'}{c[0]}" for c in wide.columns]
wide["TotalRevenue"] = wide["NewRevenue"] + wide["ReturningRevenue"]
wide["NewRevenueShare"] = wide["NewRevenue"] / wide["TotalRevenue"]
wide["NewCustomerShare"] = wide["NewCustomers"] / (wide["NewCustomers"] + wide["ReturningCustomers"])
wide.index = wide.index.astype(str)
wide.to_csv(os.path.join(OUT_DIR, "monthly_new_returning.csv"))

lines = [
    f"全期新客收入占比：{wide['NewRevenue'].sum() / wide['TotalRevenue'].sum():.1%}",
    f"全期老客收入占比：{wide['ReturningRevenue'].sum() / wide['TotalRevenue'].sum():.1%}",
    "",
    "逐月新客收入占比：",
]
for m, r in wide.iterrows():
    lines.append(
        f"  {m}：新客 £{r['NewRevenue']:,.0f}（{r['NewRevenueShare']:.1%}）｜"
        f"老客 £{r['ReturningRevenue']:,.0f}｜新客 {r['NewCustomers']:.0f} 人"
    )
with open(os.path.join(OUT_DIR, "lifecycle_summary.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# 堆叠柱状图
fig, ax = plt.subplots(figsize=(10, 4.8))
x = np.arange(len(wide))
ax.bar(x, wide["NewRevenue"], color="#F59E0B", label="新客收入")
ax.bar(x, wide["ReturningRevenue"], bottom=wide["NewRevenue"],
       color="#1D4ED8", label="老客复购收入")
ax.set_xticks(x)
ax.set_xticklabels(wide.index, rotation=45, ha="right")
ax.set_ylabel("收入（£）")
ax.set_title("月度收入结构：新客首购 vs 老客复购")
ax.legend()
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "new_vs_returning.png"), dpi=160)
plt.close(fig)

print("\n".join(lines))
