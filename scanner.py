# -*- coding: utf-8 -*-
import requests
import pandas as pd
from tqdm import tqdm
import time
import json

# ================= 参数 =================
BASE_URL = "https://fapi.binance.com"
INTERVAL = "1d"
LIMIT = 300
INVEST = 20
LEVERAGE = 20
TP = 0.02
MAX_DEVIATION = 0.02  
MAX_PULLUP = -0.20    

# ================= 工具函数 =================
def get_symbols():
    try:
        r = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo").json()
        return [s["symbol"] for s in r["symbols"] if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT" and s["status"] == "TRADING"]
    except: return []

def get_klines(symbol):
    r = requests.get(f"{BASE_URL}/fapi/v1/klines", params={"symbol": symbol, "interval": INTERVAL, "limit": LIMIT}, timeout=10)
    df = pd.DataFrame(r.json(), columns=["open_time","open","high","low","close","volume","close_time","qv","n","tb","tq","ignore"])
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    return df

def get_price(symbol):
    r = requests.get(f"{BASE_URL}/fapi/v1/ticker/price", params={"symbol": symbol})
    return float(r.json()["price"])

# ================= 策略函数 =================
def is_signal_BIG_GREEN_RED_5(df):
    prev2, prev1 = df.iloc[-3], df.iloc[-2]
    return (prev2["close"] >= prev2["open"] * 1.05 and prev1["close"] < prev1["open"])

def is_signal_NEW1_LONG_SHADOW_REVERSE(df):
    prev2, prev1 = df.iloc[-3], df.iloc[-2]
    return (prev1["close"] >= prev1["open"] * 1.05 and prev2["open"] < prev1["close"])

def is_signal_NEW5_SMALL_BODY_REVERSE_SAFE(df):
    prev2, prev1 = df.iloc[-3], df.iloc[-2]
    return (prev2["close"] >= prev2["open"] * 1.05 and abs(prev1["close"] - prev1["open"]) < (prev1["high"] - prev1["low"]) * 0.3 and prev1["close"] < prev1["open"])

# ================= 回测函数 =================
def backtest(df, strategy_func):
    trades = []
    n = len(df)
    for i in range(2, n - 1):
        if not strategy_func(df.iloc[:i+1]): continue
        entry = df.iloc[i]["open"]
        tp = entry * (1 - TP)
        max_dd = 0
        exit_idx = None
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

# ================= 扫描逻辑 =================
symbols = get_symbols()
strategies = [("BIG_5%", is_signal_BIG_GREEN_RED_5), ("NEW1_REVERSE", is_signal_NEW1_LONG_SHADOW_REVERSE), ("NEW5_SAFE", is_signal_NEW5_SMALL_BODY_REVERSE_SAFE)]

all_signals = []

for sym in tqdm(symbols, desc="扫描中"):
    try:
        df = get_klines(sym)
        if len(df) < 10: continue
        entry_price = df.iloc[-1]["open"]
        current_price = get_price(sym)
        deviation = (entry_price - current_price) / entry_price
        if deviation >= MAX_DEVIATION or deviation <= MAX_PULLUP: continue

        for name, func in strategies:
            if func(df):
                stats = backtest(df, func)
                if stats:
                    all_signals.append({
                        "symbol": sym, "strategy": name,
                        "entry": round(entry_price, 4), "current": round(current_price, 4),
                        "deviation": f"{round(deviation*100, 2)}%", "winrate": f"{round(stats['winrate'], 2)}%",
                        "profit": round(stats['total_profit'], 2), "max_dd": round(stats['max_dd'], 2),
                        "update_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    })
        time.sleep(0.1)
    except: continue

with open('results.json', 'w', encoding='utf-8') as f:
    json.dump(all_signals, f, ensure_ascii=False, indent=4)