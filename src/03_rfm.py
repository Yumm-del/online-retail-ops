# -*- coding: utf-8 -*-
"""
03_rfm.py —— RFM 用户分层
目的：按最近购买时间（R）、购买频次（F）、消费金额（M）把客户分成 8 类，
      并给出每类的人数、收入贡献与运营动作。
输入：data/clean/clean_customer.csv
输出：data/analysis/rfm_customers.csv、rfm_segments.csv
      charts/rfm_segments.png、charts/revenue_concentration.png
原理：
  - R/F/M 各自用五分位打分（1–5）。R 越小越好，所以打分方向反过来；
  - 8 类分群用「高/低」二元组合：得分 ≥4 记为高，否则为低；
  - 同时算收入集中度（Top 10%/20% 客户贡献多少收入），判断是否依赖大客户。
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

# 中文字体（Windows 自带微软雅黑）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_csv(CLEAN, parse_dates=["InvoiceDate"])
snapshot = df["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)

# 1. 客户级 RFM
rfm = df.groupby("CustomerID").agg(
    LastPurchase=("InvoiceDate", "max"),
    FirstPurchase=("InvoiceDate", "min"),
    Frequency=("InvoiceNo", "nunique"),
    Monetary=("Revenue", "sum"),
    Items=("Quantity", "sum"),
).reset_index()
rfm["Recency"] = (snapshot - rfm["LastPurchase"]).dt.days
rfm["AOV"] = rfm["Monetary"] / rfm["Frequency"]

# 2. 五分位打分（rank 处理并列值，避免 qcut 边界重复报错）
def score_high(series):
    """数值越大越好：1–5 分。"""
    return pd.qcut(series.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)


rfm["R_score"] = pd.qcut(rfm["Recency"].rank(method="first", ascending=False),
                         5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["F_score"] = score_high(rfm["Frequency"])
rfm["M_score"] = score_high(rfm["Monetary"])

# 3. 八分群：各维度得分 ≥4 记为「高」
def seg_name(r, f, m):
    key = (r >= 4, f >= 4, m >= 4)
    mapping = {
        (True, True, True): "重要价值客户",
        (False, True, True): "重要保持客户",
        (True, False, True): "重要发展客户",
        (False, False, True): "重要挽留客户",
        (True, True, False): "一般价值客户",
        (False, True, False): "一般保持客户",
        (True, False, False): "一般发展客户",
        (False, False, False): "一般挽留客户",
    }
    return mapping[key]


rfm["Segment"] = [
    seg_name(r, f, m)
    for r, f, m in zip(rfm["R_score"], rfm["F_score"], rfm["M_score"])
]

ACTIONS = {
    "重要价值客户": "专属客服 + 新品优先 + 会员权益，重点维护不打扰",
    "重要保持客户": "流失预警，复购券 + 高频品类推荐，7 天内触达",
    "重要发展客户": "提升购买频次：跨品类推荐 + 满减凑单",
    "重要挽留客户": "大额召回券 + 人工回访，先问原因再给方案",
    "一般价值客户": "提客单：组合装、满减门槛设计",
    "一般保持客户": "低成本自动化触达，内容种草为主",
    "一般发展客户": "新客培育：首复购券 + 使用引导",
    "一般挽留客户": "低成本邮件/短信召回，不投入人工",
}

# 4. 分群汇总
total_cust = len(rfm)
total_rev = rfm["Monetary"].sum()
seg = rfm.groupby("Segment").agg(
    Customers=("CustomerID", "count"),
    Revenue=("Monetary", "sum"),
    AvgRecency=("Recency", "mean"),
    AvgFrequency=("Frequency", "mean"),
    AvgMonetary=("Monetary", "mean"),
    AvgAOV=("AOV", "mean"),
).reset_index()
seg["CustomerShare"] = seg["Customers"] / total_cust
seg["RevenueShare"] = seg["Revenue"] / total_rev
seg["Action"] = seg["Segment"].map(ACTIONS)
seg = seg.sort_values("Revenue", ascending=False)

# 5. 收入集中度
ranked = rfm.sort_values("Monetary", ascending=False).reset_index(drop=True)
ranked["CumRevenueShare"] = ranked["Monetary"].cumsum() / total_rev
ranked["CumCustomerShare"] = (ranked.index + 1) / len(ranked)
top10 = ranked.loc[int(len(ranked) * 0.10) - 1, "CumRevenueShare"]
top20 = ranked.loc[int(len(ranked) * 0.20) - 1, "CumRevenueShare"]

summary = [
    f"客户数：{total_cust:,}",
    f"总收入：£{total_rev:,.0f}",
    f"客单价（人均消费）：£{rfm['Monetary'].mean():,.0f}",
    f"人均购买次数：{rfm['Frequency'].mean():.1f}",
    f"Top 10% 客户贡献收入：{top10:.1%}",
    f"Top 20% 客户贡献收入：{top20:.1%}",
    "",
    "分群明细：",
]
for _, r in seg.iterrows():
    summary.append(
        f"{r['Segment']}：{r['Customers']:,} 人（{r['CustomerShare']:.1%}），"
        f"收入 £{r['Revenue']:,.0f}（{r['RevenueShare']:.1%}），"
        f"平均 R={r['AvgRecency']:.0f} 天 / F={r['AvgFrequency']:.1f} 次 / "
        f"M=£{r['AvgMonetary']:,.0f}"
    )
with open(os.path.join(OUT_DIR, "rfm_summary.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(summary))

# 6. 图 1：各分群人数占比 vs 收入占比
plot_seg = seg.copy()
fig, ax = plt.subplots(figsize=(10, 5.2))
y = np.arange(len(plot_seg))
ax.barh(y - 0.2, plot_seg["CustomerShare"], height=0.38,
        color="#93C5FD", label="客户数占比")
ax.barh(y + 0.2, plot_seg["RevenueShare"], height=0.38,
        color="#C1121F", label="收入占比")
ax.set_yticks(y)
ax.set_yticklabels(plot_seg["Segment"])
ax.invert_yaxis()
ax.set_xlabel("占比")
ax.set_title("RFM 八分群：人数占比 vs 收入占比")
ax.legend(loc="lower right")
ax.grid(axis="x", alpha=0.25)
for i, (c, r) in enumerate(zip(plot_seg["CustomerShare"], plot_seg["RevenueShare"])):
    ax.text(c + 0.005, i - 0.2, f"{c:.1%}", va="center", fontsize=8)
    ax.text(r + 0.005, i + 0.2, f"{r:.1%}", va="center", fontsize=8, color="#7F1D1D")
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "rfm_segments.png"), dpi=160)
plt.close(fig)

# 7. 图 2：收入集中度曲线
fig, ax = plt.subplots(figsize=(7.2, 4.6))
ax.plot(ranked["CumCustomerShare"], ranked["CumRevenueShare"], color="#C1121F", lw=2)
ax.plot([0, 1], [0, 1], ls="--", color="#9CA3AF", lw=1, label="完全均等线")
for share, label in ((0.1, "Top 10%"), (0.2, "Top 20%")):
    idx = int(len(ranked) * share) - 1
    ax.axvline(share, color="#6B7280", ls=":", lw=1)
    ax.scatter([share], [ranked.loc[idx, "CumRevenueShare"]], color="#111827", zorder=3)
    ax.annotate(f"{label} 贡献 {ranked.loc[idx, 'CumRevenueShare']:.1%}",
                (share, ranked.loc[idx, "CumRevenueShare"]),
                textcoords="offset points", xytext=(10, -14), fontsize=9)
ax.set_xlabel("客户累计占比（按消费额从高到低）")
ax.set_ylabel("累计收入占比")
ax.set_title("收入集中度：少数客户贡献多数收入")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1.02)
ax.grid(alpha=0.25)
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "revenue_concentration.png"), dpi=160)
plt.close(fig)

# 8. 输出
rfm.to_csv(os.path.join(OUT_DIR, "rfm_customers.csv"), index=False)
seg.to_csv(os.path.join(OUT_DIR, "rfm_segments.csv"), index=False)
print("\n".join(summary))
