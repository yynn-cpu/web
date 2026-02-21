# -*- coding: utf-8 -*-
import requests
import pandas as pd
from tqdm import tqdm
import time
import json
import subprocess

# ================= 参数配置 =================
BASE_URL = "https://fapi.binance.com"
INTERVAL = "1d"
LIMIT = 300
INVEST = 20
LEVERAGE = 20
TP = 0.02
MAX_DEVIATION = 0.02
MAX_PULLUP = -0.20

# ================= 策略逻辑 =================
def is_signal_BIG_GREEN_RED_5(df):
    """大阳后调"""
    prev2 = df.iloc[-3]
    prev1 = df.iloc[-2]
    return (prev2["close"] >= prev2["open"] * 1.05 and prev1["close"] < prev1["open"])

def is_signal_NEW1_LONG_SHADOW_REVERSE(df):
    """长影反转"""
    prev2 = df.iloc[-3]
    prev1 = df.iloc[-2]
    return (prev1["close"] >= prev1["open"] * 1.05 and prev2["open"] < prev1["close"])

def is_signal_NEW5_SMALL_BODY_REVERSE_SAFE(df):
    """缩量安全"""
    prev2 = df.iloc[-3]
    prev1 = df.iloc[-2]
    body = abs(prev1["close"] - prev1["open"])
    hrange = prev1["high"] - prev1["low"]
    return (prev2["close"] >= prev2["open"] * 1.05 and body < hrange * 0.3 and prev1["close"] < prev1["open"])

# ================= 功能函数 =================
def get_symbols():
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo").json()
        return [s["symbol"] for s in r["symbols"] if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT" and s["status"] == "TRADING"]
    except: return []

def get_klines(symbol):
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/klines", params={"symbol": symbol, "interval": INTERVAL, "limit": LIMIT}, timeout=10)
        if r.status_code != 200: return pd.DataFrame()
        df = pd.DataFrame(r.json(), columns=["ot","open","high","low","close","v","ct","qv","n","tb","tq","i"])
        df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
        return df
    except: return pd.DataFrame()

def get_price(symbol):
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/ticker/price", params={"symbol": symbol})
        return float(r.json()["price"])
    except: return 0.0

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

def push_to_web(msg):
    """强制推送逻辑：解决冲突并上传数据"""
    try:
        subprocess.run("git add data.json", shell=True, capture_output=True)
        subprocess.run(f'git commit -m "{msg}"', shell=True, capture_output=True)
        # 使用强制推送解决远程领先问题
        subprocess.run("git push origin main -f", shell=True, capture_output=True)
        print(f"\n🚀 数据已同步 (信号数达到阈值: {msg})")
    except Exception as e:
        print(f"\n❌ 同步失败: {e}")

# ================= 扫描启动 =================
symbols = get_symbols()
print(f"🔍 扫描合约数量：{len(symbols)}")

strategies = [
    ("大阳后调", is_signal_BIG_GREEN_RED_5),
    ("长影反转", is_signal_NEW1_LONG_SHADOW_REVERSE),
    ("缩量安全", is_signal_NEW5_SMALL_BODY_REVERSE_SAFE)
]

web_results = []
signal_counter = 0

for sym in tqdm(symbols, desc="实盘扫描中"):
    df = get_klines(sym)
    if df.empty or len(df) < 10: continue
    
    entry_price = df.iloc[-1]["open"]
    current_price = get_price(sym)
    if current_price == 0: continue
    deviation = (entry_price - current_price) / entry_price

    if deviation >= MAX_DEVIATION or deviation <= MAX_PULLUP: continue

    for name, func in strategies:
        if not func(df): continue
        stats = backtest(df, func)
        if not stats: continue

        web_results.append({
            "symbol": sym, "strategy": name, "entry": entry_price,
            "current": current_price, "dev": f"{deviation*100:.2f}%",
            "wr": f"{stats['winrate']:.2f}%", "profit": f"{stats['total_profit']:.2f}",
            "dd": f"{stats['max_dd']:.2f}", "hold": f"{stats['avg_hold']:.2f}", # 持仓数据
            "time": time.strftime("%H:%M:%S")
        })
        
        signal_counter += 1
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(web_results, f, indent=4, ensure_ascii=False)

        # 满足5个信号推送一次
        if signal_counter >= 5:
            push_to_web(f"Batch update: {signal_counter} signals")
            signal_counter = 0
    time.sleep(0.1)

if signal_counter > 0:
    push_to_web("Final update")
print("\n🏁 扫描任务完成")