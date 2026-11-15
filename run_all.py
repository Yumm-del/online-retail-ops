# -*- coding: utf-8 -*-
"""
run_all.py —— 一键跑完整分析流程
目的：按依赖顺序执行 01–07 七个脚本，任何一步失败立即停止。
用法：python run_all.py
前提：data/raw/Online Retail.xlsx 已存在（见 README 下载步骤）。
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "data", "raw", "Online Retail.xlsx")

if not os.path.exists(RAW):
    raise SystemExit(
        "缺少原始数据：data/raw/Online Retail.xlsx\n"
        "请先按 README「复现步骤」下载并解压 UCI Online Retail 数据集。"
    )

STEPS = [
    "src/01_profile.py",
    "src/02_clean.py",
    "src/03_rfm.py",
    "src/04_cohort.py",
    "src/05_attribution.py",
    "src/06_lifecycle.py",
    "src/07_dashboard.py",
]

for step in STEPS:
    print(f"\n>>> 运行 {step}")
    # 用当前解释器执行，保证依赖一致；check=True 让失败立刻中断
    subprocess.run([sys.executable, os.path.join(BASE, step)],
                   cwd=BASE, check=True)

print("\n全部完成：dashboard/Online-Retail-用户运营看板.xlsx")
