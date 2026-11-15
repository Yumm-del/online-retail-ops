# -*- coding: utf-8 -*-
"""
07_dashboard.py —— 生成 Excel 运营看板
目的：把清洗、RFM、留存、归因、新老客五块结果装进一个可直接给运营看的 xlsx。
输入：data/analysis/*.csv、data/cleaning_log.txt
输出：dashboard/Online-Retail-用户运营看板.xlsx
原理：用 openpyxl 写表 + 原生图表（不嵌图片），WPS / Excel 都能打开并联动筛选；
      数字格式、条件格式、冻结窗格按运营看板习惯设置。
"""
import os

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.drawing.image import Image as XLImage
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

BASE = r"D:\file_of_claude\online-retail-ops"
ANA = os.path.join(BASE, "data", "analysis")
CHART_DIR = os.path.join(BASE, "charts")
OUT_DIR = os.path.join(BASE, "dashboard")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "Online-Retail-用户运营看板.xlsx")

# ---------- 样式 ----------
DARK = "C1121F"
LIGHT = "FDE8E8"
GREY = "6B7280"
THIN = Side(style="thin", color="D1D5DB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
TITLE_FONT = Font(name="微软雅黑", size=16, bold=True, color="FFFFFF")
HEAD_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="微软雅黑", size=10)
NOTE_FONT = Font(name="微软雅黑", size=9, color=GREY)
TITLE_FILL = PatternFill("solid", fgColor=DARK)
HEAD_FILL = PatternFill("solid", fgColor="9B1C1C")
LIGHT_FILL = PatternFill("solid", fgColor=LIGHT)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)


def title(ws, text, last_col="J"):
    ws.merge_cells(f"A1:{last_col}1")
    c = ws["A1"]
    c.value = text
    c.font = TITLE_FONT
    c.fill = TITLE_FILL
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 30


def section(ws, row, text, last_col="J"):
    ws.merge_cells(f"A{row}:{last_col}{row}")
    c = ws[f"A{row}"]
    c.value = text
    c.font = Font(name="微软雅黑", size=11, bold=True, color="9B1C1C")
    c.fill = LIGHT_FILL
    c.alignment = Alignment(horizontal="left", vertical="center")


def table(ws, start_row, headers, rows, widths=None, formats=None, header_row=True):
    """写一张带边框的表，返回最后一行行号。"""
    r = start_row
    if header_row:
        for j, h in enumerate(headers, start=1):
            c = ws.cell(row=r, column=j, value=h)
            c.font = HEAD_FONT
            c.fill = HEAD_FILL
            c.alignment = CENTER
            c.border = BORDER
        r += 1
    for row in rows:
        for j, v in enumerate(row, start=1):
            c = ws.cell(row=r, column=j, value=v)
            c.font = BODY_FONT
            c.border = BORDER
            c.alignment = LEFT if j == len(row) and isinstance(v, str) else CENTER
            if formats and j <= len(formats) and formats[j - 1]:
                c.number_format = formats[j - 1]
        r += 1
    if widths:
        for j, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(j)].width = w
    return r - 1


def kpi(ws, row, col, label, value, fmt=None):
    c1 = ws.cell(row=row, column=col, value=label)
    c1.font = Font(name="微软雅黑", size=9, color=GREY)
    c1.alignment = CENTER
    c2 = ws.cell(row=row, column=col + 1, value=value)
    c2.font = Font(name="微软雅黑", size=14, bold=True, color="111827")
    c2.alignment = CENTER
    if fmt:
        c2.number_format = fmt


# ---------- 读数据 ----------
monthly = pd.read_csv(os.path.join(ANA, "monthly_summary.csv"))
seg = pd.read_csv(os.path.join(ANA, "rfm_segments.csv"))
cohort = pd.read_csv(os.path.join(ANA, "cohort_matrix.csv"), index_col=0)
life = pd.read_csv(os.path.join(ANA, "monthly_new_returning.csv"))
rfm = pd.read_csv(os.path.join(ANA, "rfm_customers.csv"))

total_rev = monthly["NetRevenue"].sum()
total_orders = int(monthly["Orders"].sum())
total_cust = len(rfm)
aov = monthly["SalesRevenue"].sum() / total_orders
repeat_rate = (rfm["Frequency"] >= 2).mean()
vip = seg[seg["Segment"] == "重要价值客户"].iloc[0]

wb = Workbook()

# ============================================================
# Sheet 1 总览
# ============================================================
ws = wb.active
ws.title = "总览"
title(ws, "Online Retail 用户运营数据分析看板", "J")
ws["A2"] = "数据范围：2010-12-01 至 2011-12-09｜英国线上礼品零售商｜541,909 行原始交易"
ws["A2"].font = NOTE_FONT
ws.merge_cells("A2:J2")

section(ws, 4, "核心指标", "J")
kpis = [
    ("净收入", total_rev, "£#,##0"),
    ("有效订单", total_orders, "#,##0"),
    ("可识别客户", total_cust, "#,##0"),
    ("客单价", aov, "£#,##0"),
    ("复购率", repeat_rate, "0.0%"),
]
col = 1
for label, value, fmt in kpis:
    kpi(ws, 5, col, label, value, fmt)
    col += 2
ws.row_dimensions[5].height = 20
ws.row_dimensions[6].height = 8

section(ws, 8, "月度净收入（已做退货配对）", "J")
rows = [[str(r["Month"]), float(r["NetRevenue"]), int(r["Orders"]),
         int(r["Customers"]), float(r["AOV"])] for _, r in monthly.iterrows()]
last = table(ws, 9, ["月份", "净收入", "订单数", "客户数", "客单价"], rows,
             widths=[12, 14, 10, 10, 10],
             formats=[None, "£#,##0", "#,##0", "#,##0", "£#,##0"])

chart = LineChart()
chart.title = "月度净收入趋势"
chart.y_axis.title = "收入（£）"
chart.x_axis.title = "月份"
data = Reference(ws, min_col=2, min_row=9, max_row=last)
cats = Reference(ws, min_col=1, min_row=10, max_row=last)
chart.add_data(data, titles_from_data=True)
chart.set_categories(cats)
chart.height = 8
chart.width = 17
chart.series[0].graphicalProperties.line.solidFill = DARK
chart.series[0].graphicalProperties.line.width = 22000
ws.add_chart(chart, "G9")

section(ws, last + 2, "关键结论（可直接放进周报）", "J")
findings = [
    "1. 收入高度集中：Top 10% 客户贡献 60.2% 收入，Top 20% 贡献 73.8%；21.7% 的「重要价值客户」贡献 66.7% 收入。",
    "2. 增长靠老客：可识别客户收入中，全期 75.1% 来自老客复购；11 月老客贡献 £991,941（88.2%），新客仅 11.8%。",
    "3. 11 月旺季是普涨：环比 +34.5%，68% 来自客户数增加、41% 来自人均订单数；剔除 Top 10% 客户后 11 月仍是最高。",
    "4. 留存不是逐月衰减：M1 24.6% → M3 27.3% → M6 28.7%，补货周期约 2–3 个月，触达应按周期而非每月轰炸。",
    "5. 数据陷阱：£168,469.60 的「最大单」12 分钟后被全额冲销；只删退货行会把 12 月抬高 £192,448。",
]
r = last + 3
for text in findings:
    ws.merge_cells(f"A{r}:J{r}")
    c = ws[f"A{r}"]
    c.value = text
    c.font = BODY_FONT
    c.alignment = LEFT
    ws.row_dimensions[r].height = 22
    r += 1

# ============================================================
# Sheet 2 RFM 分层
# ============================================================
ws = wb.create_sheet("RFM分层")
title(ws, "RFM 八分群：谁贡献收入、该做什么动作", "J")
ws["A2"] = "口径：R/F/M 各按五分位打 1–5 分；三维均以 ≥4 分为「高」，组合成 8 类。"
ws["A2"].font = NOTE_FONT
ws.merge_cells("A2:J2")

rows = []
for _, r in seg.iterrows():
    rows.append([r["Segment"], int(r["Customers"]), float(r["CustomerShare"]),
                 float(r["RevenueShare"]), float(r["Revenue"]),
                 float(r["AvgRecency"]), float(r["AvgFrequency"]),
                 float(r["AvgMonetary"]), r["Action"]])
last = table(ws, 4, ["分群", "客户数", "客户占比", "收入占比", "收入",
                     "平均R（天）", "平均F（次）", "平均M（£）", "运营动作"],
             rows, widths=[16, 9, 10, 10, 13, 11, 10, 12, 46],
             formats=[None, "#,##0", "0.0%", "0.0%", "£#,##0",
                      "0", "0.0", "£#,##0", None])

bar = BarChart()
bar.type = "bar"
bar.grouping = "clustered"
bar.title = "各分群：客户占比 vs 收入占比"
bar.x_axis.title = "占比"
cats = Reference(ws, min_col=1, min_row=5, max_row=last)
bar.add_data(Reference(ws, min_col=3, max_col=4, min_row=4, max_row=last),
             titles_from_data=True)
bar.series[0].graphicalProperties.solidFill = "93C5FD"
bar.series[1].graphicalProperties.solidFill = DARK
bar.set_categories(cats)
bar.height = 9
bar.width = 16
ws.add_chart(bar, "K4")

r = last + 2
ws.merge_cells(f"A{r}:J{r}")
ws[f"A{r}"] = ("读法：重要价值客户 21.7% 的人数贡献 66.7% 收入；一般挽留客户 39.7% 的人数只贡献 7.0% 收入——"
               "运营资源应优先给前四类，后四类以低成本自动化为主。")
ws[f"A{r}"].font = NOTE_FONT
ws[f"A{r}"].alignment = LEFT
ws.row_dimensions[r].height = 30

# ============================================================
# Sheet 3 留存队列
# ============================================================
ws = wb.create_sheet("留存队列")
title(ws, "月度留存队列：首购后第 N 月仍购买的比例", "N")
ws["A2"] = "说明：2011-12 只有 9 天数据，落在该月的格子不计入；平均曲线只用可完整观测到 M6 的 6 个队列。"
ws["A2"].font = NOTE_FONT
ws.merge_cells("A2:N2")

cols = [f"M{c}" for c in cohort.columns]
rows = []
for idx, r in cohort.iterrows():
    rows.append([str(idx)] + [None if pd.isna(v) else float(v) for v in r.values])
last = table(ws, 4, ["队列"] + cols, rows,
             widths=[12] + [8] * len(cols),
             formats=[None] + ["0.0%"] * len(cols))
ws.freeze_panes = "B5"

# 条件格式：0 白 → 60% 深红
ws.conditional_formatting.add(
    f"B5:{get_column_letter(len(cols) + 1)}{last}",
    ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF",
                   mid_type="num", mid_value=0.25, mid_color="FCA5A5",
                   end_type="num", end_value=0.5, end_color=DARK))

r = last + 2
section(ws, r, "留存指标与解读", "N")
notes = [
    "复购客户占比（≥2 次购买）：65.3%",
    "M1 留存 24.6%｜M3 留存 27.3%｜M6 留存 28.7%（固定 6 个队列加权）",
    "留存没有逐月衰减：典型补货周期约 2–3 个月，次月不是唯一关键窗口；触达节奏应按补货周期设计。",
    "2010-12 队列（883 人）留存显著高于后续队列（M1 36.6% vs 11%–24%），早期客户质量更高，后续拉新质量下滑。",
]
r += 1
for text in notes:
    ws.merge_cells(f"A{r}:N{r}")
    ws[f"A{r}"] = text
    ws[f"A{r}"].font = BODY_FONT
    ws[f"A{r}"].alignment = LEFT
    r += 1

# ============================================================
# Sheet 4 波动归因
# ============================================================
ws = wb.create_sheet("波动归因")
title(ws, "收入波动归因：11 月为什么涨、12 月为什么不能直接比", "H")
ws["A2"] = "方法：收入 = 客户数 × 人均订单数 × 客单价；用对数变化分解三者对环比增长的贡献。"
ws["A2"].font = NOTE_FONT
ws.merge_cells("A2:H2")

section(ws, 4, "11 月 vs 10 月：增长来自哪里", "H")
oct_r = monthly[monthly["Month"] == "2011-10"].iloc[0]
nov_r = monthly[monthly["Month"] == "2011-11"].iloc[0]
rows = [
    ["客户数", int(oct_r["Customers"]), int(nov_r["Customers"]),
     float(nov_r["Customers"] / oct_r["Customers"] - 1), "68%"],
    ["人均订单数", float(oct_r["OrdersPerCustomer"]), float(nov_r["OrdersPerCustomer"]),
     float(nov_r["OrdersPerCustomer"] / oct_r["OrdersPerCustomer"] - 1), "41%"],
    ["客单价", float(oct_r["AOV"]), float(nov_r["AOV"]),
     float(nov_r["AOV"] / oct_r["AOV"] - 1), "-8%"],
    ["收入", float(oct_r["SalesRevenue"]), float(nov_r["SalesRevenue"]),
     float(nov_r["SalesRevenue"] / oct_r["SalesRevenue"] - 1), "100%"],
]
last = table(ws, 5, ["指标", "10 月", "11 月", "环比变化", "对增长贡献"], rows,
             widths=[14, 14, 14, 12, 14],
             formats=[None, "£#,##0", "£#,##0", "0.0%", None])
# 客户数/人均订单数的绝对值不是金额，改格式
for rr in (6, 7):
    ws.cell(row=rr, column=2).number_format = "#,##0.0"
    ws.cell(row=rr, column=3).number_format = "#,##0.0"

section(ws, last + 2, "幽灵大单检验：只删退货行 vs 退货配对", "H")
rows = [
    ["只删 C 发票的 12 月销售", 637790, "会留下已冲销的原单"],
    ["退货配对后的 12 月销售", 445342, "正确口径"],
    ["差额（虚增）", 192448, "其中 581483 单笔 168,470"],
]
last2 = table(ws, last + 3, ["口径", "12 月销售（£）", "说明"], rows,
              widths=[26, 16, 30],
              formats=[None, "£#,##0", None])

section(ws, last2 + 2, "剔除 Top 10% 客户后，11 月仍是高峰", "H")
rows = [
    ["2011-10", 525707, "剔除后"],
    ["2011-11", 816857, "剔除后仍为全年最高"],
]
last3 = table(ws, last2 + 3, ["月份", "收入（£）", "结论"], rows,
              widths=[14, 16, 26],
              formats=[None, "£#,##0", None])

section(ws, last3 + 2, "成交时间分布（日均收入，指导触达窗口）", "H")
rows = [
    ["周四", 39663, "一周最高"],
    ["周二", 37928, "次高"],
    ["周一", 35427, ""],
    ["周三", 33323, ""],
    ["周五", 31441, ""],
    ["周日", 15827, "明显偏低"],
    ["周六", 0, "无交易"],
]
last4 = table(ws, last3 + 3, ["星期", "日均收入（£）", "备注"], rows,
              widths=[14, 16, 26],
              formats=[None, "£#,##0", None])
r = last4 + 2
ws.merge_cells(f"A{r}:H{r}")
ws[f"A{r}"] = "时段：10–15 点是成交集中区间（12 点最高）；触达/推送建议放在工作日上午 10–12 点。"
ws[f"A{r}"].font = NOTE_FONT
ws[f"A{r}"].alignment = LEFT

# 成交时段热力图（图片形式，右侧留白区）
hour_img = XLImage(os.path.join(CHART_DIR, "weekday_hour.png"))
hour_img.width = 700
hour_img.height = 245
ws.add_image(hour_img, "J4")

# ============================================================
# Sheet 5 新老客
# ============================================================
ws = wb.create_sheet("新老客")
title(ws, "月度收入结构：新客首购 vs 老客复购", "H")
ws["A2"] = "口径：客户首次购买月份 = 该客户的新客月；其余月份的收入计为老客复购。"
ws["A2"].font = NOTE_FONT
ws.merge_cells("A2:H2")

rows = []
for _, r in life.iterrows():
    rows.append([str(r["Month"]), float(r["NewRevenue"]), float(r["ReturningRevenue"]),
                 float(r["TotalRevenue"]), float(r["NewRevenueShare"])])
last = table(ws, 4, ["月份", "新客收入", "老客收入", "总收入", "新客收入占比"], rows,
             widths=[12, 14, 14, 14, 14],
             formats=[None, "£#,##0", "£#,##0", "£#,##0", "0.0%"])

stack = BarChart()
stack.type = "col"
stack.grouping = "stacked"
stack.overlap = 100
stack.title = "月度收入：新客 vs 老客"
stack.y_axis.title = "收入（£）"
cats = Reference(ws, min_col=1, min_row=5, max_row=last)
stack.add_data(Reference(ws, min_col=2, max_col=3, min_row=4, max_row=last),
               titles_from_data=True)
stack.series[0].graphicalProperties.solidFill = "F59E0B"
stack.series[1].graphicalProperties.solidFill = "1D4ED8"
stack.set_categories(cats)
stack.height = 8
stack.width = 18
ws.add_chart(stack, "G4")

r = last + 2
ws.merge_cells(f"A{r}:H{r}")
ws[f"A{r}"] = ("可识别客户收入中，全期新客占 24.9%、老客 75.1%；新客占比从 1 月的 41.2% 降到 11 月的 11.8%——"
               "客户池成熟后，增长主要靠老客复购，运营重点应从拉新转向留存与复购。")
ws[f"A{r}"].font = NOTE_FONT
ws[f"A{r}"].alignment = LEFT
ws.row_dimensions[r].height = 30

# ============================================================
# Sheet 6 数据说明
# ============================================================
ws = wb.create_sheet("数据说明")
title(ws, "数据口径与局限", "H")
lines = []
log_path = os.path.join(BASE, "data", "cleaning_log.txt")
if os.path.exists(log_path):
    lines = [ln for ln in open(log_path, encoding="utf-8").read().splitlines() if ln.strip()]

r = 3
section(ws, r, "清洗步骤与数量", "H")
r += 1
for ln in lines:
    ws.merge_cells(f"A{r}:H{r}")
    ws[f"A{r}"] = ln
    ws[f"A{r}"].font = BODY_FONT
    ws[f"A{r}"].alignment = LEFT
    r += 1

r += 1
section(ws, r, "分析局限（写报告/面试时主动说明）", "H")
r += 1
limits = [
    "1. 公开数据集：英国线上礼品零售商 2010-12 至 2011-12，不能直接外推到其他行业或当下市场。",
    "2. 25.3% 的销售行没有 CustomerID，只能做整体收入分析，无法进入 RFM 与留存；这部分收入占 14.9%。",
    "3. 数据只到 2011-12-09，12 月不完整；M12 留存无法计算。",
    "4. 没有成本、毛利、流量、曝光等数据，无法算 ROI、转化率与 LTV/CAC。",
    "5. 留存定义为「当月有购买」，不是登录/活跃；对低频批发客户会低估真实活跃。",
    "6. RFM 分群阈值用五分位 + 4 分线，换阈值分群结果会变，结论要看相对排序而非绝对人数。",
]
for text in limits:
    ws.merge_cells(f"A{r}:H{r}")
    ws[f"A{r}"] = text
    ws[f"A{r}"].font = BODY_FONT
    ws[f"A{r}"].alignment = LEFT
    ws.row_dimensions[r].height = 26
    r += 1

# 列宽统一设置提示
for sh in wb.worksheets:
    sh.sheet_view.showGridLines = False

wb.save(OUT)
print("dashboard written:", OUT)
