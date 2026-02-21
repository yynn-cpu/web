# -*- coding: utf-8 -*-
"""
📡 实盘扫描器 + 即时回测（同步版）
保持原始逻辑，杜绝未来函数差异
"""

import requests
import pandas as pd
from tqdm import tqdm
import time
import json  # 新增：用于导出数据给网页

# ================= 参数 (保持不变) =================
BASE_URL = "https://fapi.binance.com"
INTERVAL = "1d"
LIMIT = 300
INVEST = 20
LEVERAGE = 20
TP = 0.02
MAX_DEVIATION = 0.02      # 跌远阈值 +2%
MAX_PULLUP = -0.20       # 爆拉阈值 -20%

# ================= 工具函数 (保持不变) =================
def get_symbols():
    r = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo").json()
    return [s["symbol"] for s in r["symbols"] if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT" and s["status"] == "TRADING"]

def get_klines(symbol):
    r = requests.get(f"{BASE_URL}/fapi/v1/klines", params={"symbol": symbol, "interval": INTERVAL, "limit": LIMIT}, timeout=10)
    df = pd.DataFrame(r.json(), columns=["open_time","open","high","low","close","volume","close_time","qv","n","tb","tq","ignore"])
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    return df

def get_price(symbol):
    r = requests.get(f"{BASE_URL}/fapi/v1/ticker/price", params={"symbol": symbol})
    return float(r.json()["price"])

# ================= 策略逻辑 (原封不动) =================
def is_signal_BIG_GREEN_RED_5(df):
    prev2 = df.iloc[-3]
    prev1 = df.iloc[-2]
    return (prev2["close"] >= prev2["open"] * 1.05 and prev1["close"] < prev1["open"])

def is_signal_NEW1_LONG_SHADOW_REVERSE(df):
    prev2 = df.iloc[-3]
    prev1 = df.iloc[-2]
    return (prev1["close"] >= prev1["open"] * 1.05 and prev2["open"] < prev1["close"])

def is_signal_NEW5_SMALL_BODY_REVERSE_SAFE(df):
    prev2 = df.iloc[-3]
    prev1 = df.iloc[-2]
    return (prev2["close"] >= prev2["open"] * 1.05 and abs(prev1["close"] - prev1["open"]) < (prev1["high"] - prev1["low"]) * 0.3 and prev1["close"] < prev1["open"])

# ================= 回测逻辑 (原封不动) =================
def backtest(df, strategy_func):
    trades = []
    n = len(df)
    for i in range(2, n - 1):
        if not strategy_func(df.iloc[:i+1]): continue
        entry = df.iloc[i]["open"]
        tp = entry * (1 - TP)
        max_dd, exit_idx = 0, None
        for j in range(i, n):
            k = df.iloc[j]
            dd = (k["high"] - entry) / entry * INVEST * LEVERAGE
            max_dd = max(max_dd, dd)
            if k["low"] <= tp:
                exit_idx, exit_price = j, tp
                break
        if exit_idx is None:
            exit_idx, exit_price = n - 1, df.iloc[-1]["close"]
        profit = (entry - exit_price) / entry * INVEST * LEVERAGE
        trades.append({"profit": profit, "max_dd": max_dd, "hold": exit_idx - i + 1})
    if not trades: return None
    tdf = pd.DataFrame(trades)
    return {"trades": len(tdf), "winrate": (tdf["profit"] > 0).mean() * 100, "total_profit": tdf["profit"].sum(), "max_dd": tdf["max_dd"].max(), "avg_hold": tdf["hold"].mean()}

# ================= 扫描主程序 =================
symbols = get_symbols()
print(f"🔍 扫描合约数量：{len(symbols)}")

strategies = [
    ("BIG_GREEN_RED_5%", is_signal_BIG_GREEN_RED_5),
    ("NEW1_LONG_SHADOW_REVERSE", is_signal_NEW1_LONG_SHADOW_REVERSE),
    ("NEW5_SMALL_BODY_REVERSE_SAFE", is_signal_NEW5_SMALL_BODY_REVERSE_SAFE)
]

# 用于保存给网页的结果
web_results = []

for sym in tqdm(symbols, desc="实盘扫描中"):
    try:
        df = get_klines(sym)
        if len(df) < 10: continue
        today = df.iloc[-1]
        entry_price = today["open"]
        current_price = get_price(sym)
        deviation = (entry_price - current_price) / entry_price

        if deviation >= MAX_DEVIATION or deviation <= MAX_PULLUP: continue

        for name, func in strategies:
            if not func(df): continue
            stats = backtest(df, func)
            if not stats: continue

            # 打印到控制台 (保持原有习惯)
            print(f"\n📌 {sym} | {name} | 胜率: {stats['winrate']:.2f}% | 盈利: {stats['total_profit']:.2f}")

            # 存储结果
            web_results.append({
                "symbol": sym,
                "strategy": name,
                "entry": entry_price,
                "current": current_price,
                "dev": f"{deviation*100:.2f}%",
                "wr": f"{stats['winrate']:.2f}%",
                "profit": f"{stats['total_profit']:.2f}",
                "dd": f"{stats['max_dd']:.2f}",
                "update": time.strftime("%H:%M:%S")
            })
        time.sleep(0.1)
    except Exception: continue

# 保存 JSON 文件用于网页同步
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(web_results, f, indent=4, ensure_ascii=False)

print(f"\n✅ 扫描结束，共发现 {len(web_results)} 个信号，已更新 data.json")