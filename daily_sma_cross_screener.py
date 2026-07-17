"""
daily_sma_cross_screener.py
Scans full NYSE + Nasdaq ticker list for bullish 8/21 SMA momentum setups.

Filters:
  - Price > $5
  - 20-day avg volume > 500,000
  - Price is ABOVE both the 8-day SMA and 21-day SMA
  - 8-day SMA is ABOVE the 21-day SMA (confirms bullish alignment)

If price is below the 21-day SMA, it's excluded — not a good momentum play.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
import time

# ---------- CONFIG ----------
TICKERS_FILE = "all_tickers.csv"
OUTPUT_FILE = "daily_cross_results.csv"
MIN_PRICE = 5.0
MIN_AVG_VOLUME = 500_000
FAST_MA = 8
SLOW_MA = 21
DOWNLOAD_PERIOD = "3mo"
BATCH_SIZE = 100
# -----------------------------


def load_tickers(path):
    df = pd.read_csv(path)
    for col in ["Ticker", "Symbol", "ticker", "symbol"]:
        if col in df.columns:
            return df[col].dropna().astype(str).str.upper().str.strip().tolist()
    return df.iloc[:, 0].dropna().astype(str).str.upper().str.strip().tolist()


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def scan_batch(tickers):
    results = []
    try:
        data = yf.download(
            tickers,
            period=DOWNLOAD_PERIOD,
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        print(f"Batch download failed: {e}")
        return results

    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                if ticker not in data.columns.get_level_values(0):
                    continue
                df = data[ticker]

            df = df.dropna(subset=["Close", "Volume"])
            if len(df) < SLOW_MA + 1:
                continue

            df["SMA8"] = df["Close"].rolling(FAST_MA).mean()
            df["SMA21"] = df["Close"].rolling(SLOW_MA).mean()

            last = df.iloc[-1]
            close = last["Close"]
            sma8 = last["SMA8"]
            sma21 = last["SMA21"]
            avg_vol = df["Volume"].tail(20).mean()
            last_vol = last["Volume"]
            close_date = df.index[-1].strftime("%Y-%m-%d")

            if pd.isna(sma8) or pd.isna(sma21):
                continue
            if close <= MIN_PRICE:
                continue
            if avg_vol <= MIN_AVG_VOLUME:
                continue
            if close <= sma21:
                continue
            if close <= sma8:
                continue
            if sma8 <= sma21:
                continue

            results.append({
                "ticker": ticker,
                "close_date": close_date,
                "close": round(close, 2),
                "sma8": round(sma8, 2),
                "sma21": round(sma21, 2),
                "avg_vol": int(avg_vol),
                "last_vol": int(last_vol),
            })
        except Exception:
            continue

    return results


def main():
    tickers = load_tickers(TICKERS_FILE)
    print(f"Loaded {len(tickers)} tickers from {TICKERS_FILE}")

    all_results = []
    batches = list(chunk_list(tickers, BATCH_SIZE))
