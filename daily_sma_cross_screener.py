"""
daily_sma_cross_screener.py
Scans full NYSE + Nasdaq ticker list for bullish 8/21 SMA momentum setups.

Filters:
  - Price > $5
  - 20-day avg volume > 500,000
  - Price is ABOVE both the 8MA and 21MA (bullish momentum only)
  - 8MA is ABOVE 21MA (confirms the cross/alignment)

Anything where price is below the 21MA is excluded (not a good momentum play).
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
LOOKBACK_DAYS = "3mo"   # enough history for 21MA + volume avg
BATCH_SIZE = 100        # yfinance batch download size
# -----------------------------


def load_tickers(path):
    df = pd.read_csv(path)
    # auto-detect the ticker column name
    for col in ["Ticker", "Symbol", "ticker", "symbol"]:
        if col in df.columns:
            return df[col].dropna().astype(str).str.upper().str.strip().tolist()
    # fallback: assume first column
    return df.iloc[:, 0].dropna().astype(str).str.upper().str.strip().tolist()


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def scan_batch(tickers):
    results = []
    try:
        data = yf.download(
            tickers,
            period=LOOKBACK_DAYS,
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

            df["MA8"] = df["Close"].rolling(FAST_MA).mean()
            df["MA21"] = df["Close"].rolling(SLOW_MA).mean()

            last = df.iloc[-1]
            price = last["Close"]
            ma8 = last["MA8"]
            ma21 = last["MA21"]
            avg_vol = df["Volume"].tail(20).mean()

            if pd.isna(ma8) or pd.isna(ma21):
                continue
            if price <= MIN_PRICE:
                continue
            if avg_vol <= MIN_AVG_VOLUME:
                continue
            if price <= ma21:
                continue  # below 21MA = not a good momentum play, excluded
            if price <= ma8:
                continue  # must be above both MAs
            if ma8 <= ma21:
                continue  # must be a bullish 8/21 alignment, not just above price

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "MA8": round(ma8, 2),
                "MA21": round(ma21, 2),
                "AvgVolume20D": int(avg_vol),
                "Signal": "Bullish 8/21 Momentum",
                "ScanDate": datetime.now().strftime("%Y-%m-%d"),
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
        time.sleep(1)  # be polite to yfinance

    df_out = pd.DataFrame(all_results)
    df_out = df_out.sort_values("AvgVolume20D", ascending=False)
    df_out.to_csv(OUTPUT_FILE, index=False)

    print(f"Scan complete. {len(df_out)} tickers passed filters.")
    print(f"Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
