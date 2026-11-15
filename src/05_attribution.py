# -*- coding: utf-8 -*-
"""
05_attribution.py —— 收入波动归因
目的：回答三个问题：
      1) 11 月收入高峰是季节性普涨，还是少数大客户/单笔大单造成的？
      2) 如果不做退货配对，12 月会被那笔 16.8 万英镑的幽灵单抬高多少？
      3) 一周中哪天、一天中哪个时段成交最集中（用于触达节奏）？
输入：data/clean/clean_sales.csv、clean_net.csv
输出：data/analysis/monthly_summary.csv、attribution.txt
      charts/monthly_revenue.png、charts/weekday_hour.png
原理：
  - 收入 = 客户数 × 人均订单数 × 客单价，用对数分解算三者对环比增长的贡献；
  - 剔除 Top 10% 客户后再看月度曲线：如果 11 月仍是最高，说明是普涨（季节性）；
  - 对比「只删退货行」与「退货配对」两种口径的 12 月收入，量化幽灵单影响。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = r"D:\file_of_claude\online-retail-ops"
CLEAN = os.path.join(BASE, "data", "clean", "clean_sales.csv")
NET = os.path.join(BASE, "data", "clean", "clean_net.csv")
OUT_DIR = os.path.join(BASE, "data", "analysis")
CHART_DIR = os.path.join(BASE, "charts")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

sales = pd.read_csv(CLEAN, parse_dates=["InvoiceDate"])
net = pd.read_csv(NET, parse_dates=["InvoiceDate"])
for d in (sales, net):
    d["Month"] = d["InvoiceDate"].dt.to_period("M")

# 1. 月度汇总（收入用净口径：有效销售 + 未配对退货）
net_rev = net.groupby("Month")["Revenue"].sum()
sales_rev = sales.groupby("Month")["Revenue"].sum()
orders = sales.groupby("Month")["InvoiceNo"].nunique()
customers = sales.groupby("Month")["CustomerID"].nunique()
monthly = pd.DataFrame({
    "NetRevenue": net_rev,
    "SalesRevenue": sales_rev,
    "Orders": orders,
    "Customers": customers,
})
monthly["AOV"] = monthly["SalesRevenue"] / monthly["Orders"]
monthly["OrdersPerCustomer"] = monthly["Orders"] / monthly["Customers"]
monthly.index = monthly.index.astype(str)
monthly.to_csv(os.path.join(OUT_DIR, "monthly_summary.csv"))

# 2. 11 月 vs 10 月：对数分解
oct_row, nov_row = monthly.loc["2011-10"], monthly.loc["2011-11"]
d_ln_rev = np.log(nov_row["SalesRevenue"] / oct_row["SalesRevenue"])
parts = {
    "客户数": np.log(nov_row["Customers"] / oct_row["Customers"]),
    "人均订单数": np.log(nov_row["OrdersPerCustomer"] / oct_row["OrdersPerCustomer"]),
    "客单价": np.log(nov_row["AOV"] / oct_row["AOV"]),
}
contrib = {k: v / d_ln_rev for k, v in parts.items()}

# 3. 剔除 Top 10% 客户后的月度曲线
cust_total = sales.groupby("CustomerID")["Revenue"].sum()
top10_ids = cust_total.nlargest(int(len(cust_total) * 0.10)).index
sales_ex_top = sales[~sales["CustomerID"].isin(top10_ids)]
monthly_ex_top = sales_ex_top.groupby("Month")["Revenue"].sum()
monthly_ex_top.index = monthly_ex_top.index.astype(str)

# 4. 幽灵单：只删退货行 vs 退货配对
raw = pd.read_pickle(os.path.join(BASE, "data", "interim", "raw.pkl")).drop_duplicates()
raw["Revenue"] = raw["Quantity"] * raw["UnitPrice"]
raw_sales = raw[(~raw["InvoiceNo"].astype(str).str.startswith("C"))
                & (raw["Quantity"] > 0) & (raw["UnitPrice"] > 0)]
raw_sales["Month"] = raw_sales["InvoiceDate"].dt.to_period("M")
naive_dec = raw_sales.loc[raw_sales["Month"].astype(str) == "2011-12", "Revenue"].sum()
clean_dec = monthly.loc["2011-12", "SalesRevenue"]
phantom_gap = naive_dec - clean_dec
phantom_rows = raw[(raw["InvoiceNo"].astype(str) == "581483")]
phantom_value = phantom_rows["Revenue"].sum()

# 5. 11 月大客户集中度
nov_sales = sales[sales["Month"].astype(str) == "2011-11"]
nov_top10_share = (nov_sales.groupby("CustomerID")["Revenue"].sum()
                   .nlargest(10).sum() / nov_sales["Revenue"].sum())

# 6. 星期 / 小时成交分布（按「日均」口径，避免天数不同造成偏差）
sales["Weekday"] = sales["InvoiceDate"].dt.dayofweek
sales["Hour"] = sales["InvoiceDate"].dt.hour
weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
wd_daily = []
for wd in range(7):
    sub = sales[sales["Weekday"] == wd]
    n_days = sub["InvoiceDate"].dt.date.nunique()
    wd_daily.append(sub["Revenue"].sum() / n_days if n_days else 0)
wd_avg = pd.Series(wd_daily, index=weekday_names)

# 小时口径：统一除以「全部交易日数」。
# 若除以「该小时有交易的天数」，一张 20:02 的批发大单会让该时段看起来异常火爆。
n_trading_days = sales["InvoiceDate"].dt.date.nunique()
hour_daily = []
for h in range(24):
    sub = sales[sales["Hour"] == h]
    hour_daily.append(sub["Revenue"].sum() / n_trading_days)
hour_avg = pd.Series(hour_daily, index=range(24))

# 7. 输出文字结论
lines = []
add = lines.append
add("=" * 60)
add("收入波动归因")
add("=" * 60)
add("")
add("1) 月度净收入（已做退货配对）")
for m, r in monthly.iterrows():
    add(f"  {m}：£{r['NetRevenue']:,.0f}｜订单 {r['Orders']:,}｜客户 {r['Customers']:,}"
        f"｜客单价 £{r['AOV']:,.0f}")
add("")
add("2) 11 月环比 10 月：为什么涨？")
add(f"  收入：£{oct_row['SalesRevenue']:,.0f} → £{nov_row['SalesRevenue']:,.0f}"
    f"（{nov_row['SalesRevenue']/oct_row['SalesRevenue']-1:+.1%}）")
for k in parts:
    add(f"  {k}：{parts[k]:+.3f}（对数变化），对总收入增长贡献 {contrib[k]:.0%}")
add("")
add("3) 剔除 Top 10% 客户后，11 月是否仍为高峰？")
add(f"  剔除后 11 月收入：£{monthly_ex_top.get('2011-11', 0):,.0f}")
add(f"  剔除后 10 月收入：£{monthly_ex_top.get('2011-10', 0):,.0f}")
add(f"  剔除后最高月份：{monthly_ex_top.idxmax()}（£{monthly_ex_top.max():,.0f}）")
add(f"  11 月 Top 10 客户收入占比：{nov_top10_share:.1%}")
add("")
add("4) 幽灵大单检验：只删退货 vs 退货配对")
add(f"  只删 C 发票的 12 月销售：£{naive_dec:,.0f}")
add(f"  退货配对后的 12 月销售：£{clean_dec:,.0f}")
add(f"  差额：£{phantom_gap:,.0f}（其中 581483 单笔 £{phantom_value:,.0f}）")
add("")
add("5) 成交时间分布（日均收入）")
add("  星期：" + "｜".join(f"{k} £{v:,.0f}" for k, v in wd_avg.items()))
add("  小时 Top 6：" + "｜".join(f"{h}点 £{hour_avg[h]:,.0f}"
                              for h in hour_avg.nlargest(6).index))
with open(os.path.join(OUT_DIR, "attribution.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# 8. 图 1：月度净收入
fig, ax = plt.subplots(figsize=(10, 4.8))
x = range(len(monthly))
ax.plot(x, monthly["NetRevenue"], marker="o", color="#C1121F", lw=2, label="净收入")
ax.bar(x, monthly["NetRevenue"], color="#FCA5A5", alpha=0.35)
ax.set_xticks(list(x))
ax.set_xticklabels(monthly.index, rotation=45, ha="right")
ax.set_ylabel("收入（£）")
ax.set_title("月度净收入：11 月为全年高峰，12 月仅 9 天数据")
ax.set_ylim(0, monthly["NetRevenue"].max() * 1.15)
peak = monthly["NetRevenue"].idxmax()
ax.annotate(f"11 月 £{monthly.loc[peak, 'NetRevenue']:,.0f}",
            (list(monthly.index).index(peak), monthly.loc[peak, "NetRevenue"]),
            textcoords="offset points", xytext=(0, 12), ha="center", fontsize=9)
ax.grid(axis="y", alpha=0.25)
ax.legend(loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "monthly_revenue.png"), dpi=160)
plt.close(fig)

# 9. 图 2：星期 × 小时热力图
pivot = np.zeros((7, 24))
for wd in range(7):
    for h in range(24):
        sub = sales[(sales["Weekday"] == wd) & (sales["Hour"] == h)]
        pivot[wd, h] = sub["Revenue"].sum() / n_trading_days
fig, ax = plt.subplots(figsize=(12, 4.2))
im = ax.imshow(pivot, aspect="auto", cmap="YlOrRd")
ax.set_yticks(range(7))
ax.set_yticklabels(weekday_names)
ax.set_xticks(range(24))
ax.set_xticklabels([f"{h}" for h in range(24)], fontsize=8)
ax.set_xlabel("小时")
ax.set_title("成交热力图：星期 × 小时（日均收入，£）")
fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01, label="日均收入")
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "weekday_hour.png"), dpi=160)
plt.close(fig)

print("\n".join(lines))
