# Online Retail 用户运营数据分析

用公开数据集（UCI Online Retail，541,909 行）做一套完整的用户运营分析：**清洗 → RFM 分层 → 留存队列 → 波动归因 → 新老客结构 → Excel 看板 → 报告**。

## 结论速览

- **收入集中**：Top 10% 客户贡献 60.2% 收入；「重要价值客户」21.7% 人数贡献 66.7% 收入。
- **增长靠老客**：可识别客户收入中 75.1% 来自老客；11 月老客占 88.2%。
- **11 月旺季是普涨**：环比 +34.5%，68% 来自客户数、41% 来自人均订单数，客单价 -8%；剔除 Top 10% 客户后仍是全年最高。
- **留存非逐月衰减**：M1 24.6% → M3 27.3% → M6 28.7%，补货周期约 2–3 个月，触达应按周期而非每月群发。
- **数据陷阱**：账面最大单 £168,469.60 在 12 分钟后被全额冲销；只删退货行会让 12 月虚增 £192,448。

## 目录结构

```
online-retail-ops/
├─ data/
│  ├─ raw/                 # 原始 zip 与 xlsx（不入库）
│  ├─ interim/             # 缓存 pickle（不入库）
│  ├─ clean/               # 清洗后明细（不入库，脚本生成）
│  ├─ analysis/            # RFM、队列、月度汇总等结果 CSV
│  ├─ profile.txt          # 原始数据体检报告
│  └─ cleaning_log.txt     # 清洗日志（每一步丢了多少行）
├─ src/
│  ├─ 01_profile.py        # 数据体检
│  ├─ 02_clean.py          # 去重、退货配对、非商品行剔除
│  ├─ 03_rfm.py            # RFM 八分群
│  ├─ 04_cohort.py         # 月度留存队列
│  ├─ 05_attribution.py    # 月度波动归因、幽灵单检验、时段分布
│  ├─ 06_lifecycle.py      # 新老客收入结构
│  └─ 07_dashboard.py      # 生成 Excel 看板
├─ dashboard/
│  └─ Online-Retail-用户运营看板.xlsx
├─ charts/                 # RFM、留存、归因图表 PNG
├─ report/
│  └─ 用户运营数据分析报告.md
├─ run_all.py              # 一键按顺序跑完整流程
└─ requirements.txt
```

## 复现步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 下载数据（约 23 MB）
mkdir -p data/raw
curl -L -o data/raw/online-retail.zip \
  "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
python -c "import zipfile; zipfile.ZipFile('data/raw/online-retail.zip').extractall('data/raw')"

# 3. 一键跑完
python run_all.py
```

## 方法要点

1. **退货配对**：同客户 + 同商品 + 同单价 + 数量绝对值相同，取退货前最近一笔未匹配销售，配对成功后两边一起剔除。只删 C 发票会把已冲销的原单留在数据里。
2. **RFM 打分**：R/F/M 各五分位 1–5 分，三维 ≥4 分为「高」，组合 8 类；分群阈值可调，结论看相对排序。
3. **留存右删失**：2011-12 只有 9 天，落在该月的格子不计；平均曲线只用能完整观测到 M6 的 6 个队列，避免「越往后只剩高留存队列」的假象。
4. **波动归因**：收入 = 客户数 × 人均订单数 × 客单价，用对数变化分解贡献；再剔除 Top 10% 客户验证是否普涨。
5. **口径说明**：25.28% 销售行无 CustomerID，客户级结论只覆盖有身份的交易。

## 局限

公开数据集、单国单品类、无成本/流量数据；留存用「当月有购买」定义，对低频批发客户会低估活跃；结论不能直接外推到其他行业。

## 数据来源

UCI Machine Learning Repository — [Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)（ID 352）
