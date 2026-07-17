"""
daily_sma_cross_screener.py
Scans full NYSE + Nasdaq ticker list for a FRESH bullish 8/21 SMA cross
that happened on the most recently closed daily bar (i.e. the cross
occurred TODAY at the close, not days ago).

A ticker qualifies only if:
  - Price > $5
  - 20-day avg volume > 500,000
  - Price is ABOVE both the 8-day SMA and 21-day SMA today
  - Today's 8-day SMA is ABOVE today's 21-day SMA
  - Yesterday's 8-day SMA was BELOW OR EQUAL to yesterday's 21-day SMA
    (this is what confirms the cross just happened, not that it's been
    running for days)
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
            if len(df) < SLOW_MA + 2:
                continue

            df["SMA8"] = df["Close"].rolling(FAST_MA).mean()
            df["SMA21"] = df["Close"].rolling(SLOW_MA).mean()

            today = df.iloc[-1]
            yesterday = df.iloc[-2]

            close = today["Close"]
            sma8_today = today["SMA8"]
            sma21_today = today["SMA21"]
            sma8_yday = yesterday["SMA8"]
            sma21_yday = yesterday["SMA21"]
            avg_vol = df["Volume"].tail(20).mean()
            last_vol = today["Volume"]
            close_date = df.index[-1].strftime("%Y-%m-%d")

            if pd.isna(sma8_today) or pd.isna(sma21_today):
                continue
            if pd.isna(sma8_yday) or pd.isna(sma21_yday):
                continue
            if close <= MIN_PRICE:
                continue
            if avg_vol <= MIN_AVG_VOLUME:
                continue
            if close <= sma21_today:
                continue
            if close <= sma8_today:
                continue
            if sma8_today <= sma21_today:
                continue
            # FRESH CROSS CHECK: yesterday it was NOT yet above, today it is
            if sma8_yday > sma21_yday:
                continue

            results.append({
                "ticker": ticker,
                "close_date": close_date,
                "close": round(close, 2),
                "sma8": round(sma8_today, 2),
                "sma21": round(sma21_today, 2),
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

    for i, batch in enumerate(batches, 1):
        print(f"Scanning batch {i}/{len(batches)} ({len(batch)} tickers)...")
        batch_results = scan_batch(batch)
        all_results.extend(batch_results)
        time.sleep(1)

    df_out = pd.DataFrame(all_results)
    if not df_out.empty:
        df_out = df_out.sort_values("ticker")
    df_out.to_csv(OUTPUT_FILE, index=False)

    print(f"Scan complete. {len(df_out)} fresh crosses found today.")
    print(f"Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()