# -*- coding: utf-8 -*-
"""
04_cohort.py —— 月度留存队列（Cohort Retention）
目的：按「首次购买月份」把客户分成队列，观察每个队列在第 N 个月还有多少人回来购买。
输入：data/clean/clean_customer.csv
输出：data/analysis/cohort_matrix.csv、cohort_summary.txt
      charts/cohort_heatmap.png、charts/retention_curve.png
原理：
  - 队列 = 客户第一次购买的月份；
  - 第 N 月留存 = 该队列在第 N 个自然月仍有购买的人数 / 队列总人数；
  - 数据截止 2011-12-09，12 月只有 9 天，属于不完整月份，在图表里标注；
  - 早期队列能观察到更长周期，晚期队列被右删失（right-censored），
    所以平均值只对「有观测数据」的格子加权，不把缺失当 0。
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

# 1. 每个客户的首次购买月份（队列）
first = df.groupby("CustomerID")["InvoiceDate"].min().dt.to_period("M")
first.name = "Cohort"

# 2. 客户 × 活跃月份
active = df[["CustomerID", "Month"]].drop_duplicates()
active = active.join(first, on="CustomerID")
active["Offset"] = (active["Month"] - active["Cohort"]).apply(lambda x: x.n)

# 3. 队列规模与留存计数
cohort_size = first.value_counts().sort_index()
pivot = (active.groupby(["Cohort", "Offset"])["CustomerID"]
         .nunique().unstack(fill_value=0))
pivot = pivot.reindex(cohort_size.index)

max_offset = int(pivot.columns.max())
matrix = pd.DataFrame(index=pivot.index, columns=range(max_offset + 1), dtype=float)
for off in matrix.columns:
    matrix[off] = pivot[off] / cohort_size if off in pivot.columns else np.nan

# 4. 右删失与不完整月份处理
# 数据截止 2011-12-09：2011-12 只有 9 天，任何落在该月的格子都会被低估，一律置为缺失；
# 队列月 + N 晚于最后月份的格子同样缺失。
last_month = df["Month"].max()
incomplete_months = {pd.Period("2011-12", "M")}
for cohort in matrix.index:
    for off in matrix.columns:
        target = cohort + off
        if target > last_month or target in incomplete_months:
            matrix.loc[cohort, off] = np.nan

# 5. 加权平均留存曲线
# 关键：只用「能完整观测到 M6」的同一批队列（2010-12 – 2011-05）计算，
# 避免观测窗口越长、只剩早期高留存队列，导致曲线虚假上升。
fixed_cohorts = [c for c in matrix.index if c + 6 <= pd.Period("2011-11", "M")]
curve = []
for off in range(0, 7):
    col = matrix.loc[fixed_cohorts, off].dropna()
    sizes = cohort_size.reindex(col.index)
    curve.append({
        "Offset": off,
        "Retention": (col * sizes).sum() / sizes.sum() if len(col) else np.nan,
        "CohortsObserved": len(col),
    })
curve_df = pd.DataFrame(curve).set_index("Offset")

# 6. 汇总指标（基于同一批队列）
def weighted_at(off):
    if off not in curve_df.index:
        return float("nan")
    row = curve_df.loc[off]
    return row["Retention"] if pd.notna(row["Retention"]) else float("nan")


repeat_rate = (df.groupby("CustomerID")["InvoiceNo"].nunique() >= 2).mean()
lines = [
    f"客户数：{df['CustomerID'].nunique():,}",
    f"队列数：{len(cohort_size)}（{cohort_size.index.min()} – {cohort_size.index.max()}）",
    f"复购客户占比（≥2 次购买）：{repeat_rate:.1%}",
    f"M1 留存（次月）：{weighted_at(1):.1%}",
    f"M3 留存：{weighted_at(3):.1%}",
    f"M6 留存：{weighted_at(6):.1%}",
    "M12：无法计算（2011-12 仅 9 天数据）",
    f"曲线口径：固定 {len(fixed_cohorts)} 个可完整观测到 M6 的队列",
    "",
    "各队列规模：",
]
for c, n in cohort_size.items():
    lines.append(f"  {c}：{n:,} 人")
with open(os.path.join(OUT_DIR, "cohort_summary.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# 7. 热力图
plot_mat = matrix.copy()
fig, ax = plt.subplots(figsize=(11, 5.8))
data = np.ma.masked_invalid(plot_mat.values.astype(float))
im = ax.imshow(data, cmap="YlOrRd", aspect="auto", vmin=0, vmax=1)
ax.set_xticks(range(len(plot_mat.columns)))
ax.set_xticklabels([f"M{c}" for c in plot_mat.columns])
ax.set_yticks(range(len(plot_mat.index)))
ax.set_yticklabels([str(c) for c in plot_mat.index])
for i in range(plot_mat.shape[0]):
    for j in range(plot_mat.shape[1]):
        v = plot_mat.iloc[i, j]
        if pd.notna(v):
            ax.text(j, i, f"{v:.0%}", ha="center", va="center",
                    fontsize=7.5, color="black" if v < 0.6 else "white")
ax.set_xlabel("距首次购买的月份数")
ax.set_ylabel("首次购买月份（队列）")
ax.set_title("月度留存队列：首购后第 N 月仍购买的比例（12 月数据不完整）")
fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="留存率")
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "cohort_heatmap.png"), dpi=160)
plt.close(fig)

# 8. 平均留存曲线
fig, ax = plt.subplots(figsize=(8, 4.6))
valid = curve_df.dropna()
ax.plot(valid.index, valid["Retention"], marker="o", color="#C1121F", lw=2)
for off, row in valid.iterrows():
    if off in (1, 3, 6, 12):
        ax.annotate(f"{row['Retention']:.0%}", (off, row["Retention"]),
                    textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=9)
ax.set_xlabel("距首次购买的月份数")
ax.set_ylabel("加权平均留存率")
ax.set_title("留存曲线：首购后各月回访购买比例")
ax.set_ylim(0, 0.45)
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "retention_curve.png"), dpi=160)
plt.close(fig)

# 9. 输出
matrix.to_csv(os.path.join(OUT_DIR, "cohort_matrix.csv"))
print("\n".join(lines))
