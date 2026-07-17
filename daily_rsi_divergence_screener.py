"""
daily_rsi_divergence_screener.py
Scans full NYSE + Nasdaq ticker list for FRESH bullish RSI(14) divergence
on the daily timeframe.

Bullish divergence = price makes a LOWER low while RSI makes a HIGHER low
at that same point — signals fading downside momentum before price turns.

Filters:
  - Price > $5
  - 20-day avg volume > 500,000
  - Two most recent swing lows within LOOKBACK_DAYS trading days
  - The second (most recent) swing low must have occurred within the
    last RECENCY_DAYS trading days, so only fresh divergences show up
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
import time

# ---------- CONFIG ----------
TICKERS_FILE = "all_tickers.csv"
OUTPUT_FILE = "daily_rsi_divergence_results.csv"
MIN_PRICE = 5.0
MIN_AVG_VOLUME = 500_000
RSI_PERIOD = 14
SWING_WINDOW = 3
LOOKBACK_DAYS = 40
RECENCY_DAYS = 5
DOWNLOAD_PERIOD = "4mo"
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


def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def find_swing_lows(close, window):
    lows = []
    for i in range(window, len(close) - window):
        segment = close.iloc[i - window: i + window + 1]
        if close.iloc[i] == segment.min():
            if lows and i - lows[-1] <= window:
                continue
            lows.append(i)
    return lows


def check_bullish_divergence(df):
    recent = df.tail(LOOKBACK_DAYS).reset_index(drop=True)
    swing_idxs = find_swing_lows(recent["Close"], SWING_WINDOW)

    if len(swing_idxs) < 2:
        return False, None, None

    low2_idx = swing_idxs[-1]
    low1_idx = swing_idxs[-2]

    price_low1 = recent["Close"].iloc[low1_idx]
    price_low2 = recent["Close"].iloc[low2_idx]
    rsi_low1 = recent["RSI"].iloc[low1_idx]
    rsi_low2 = recent["RSI"].iloc[low2_idx]

    if pd.isna(rsi_low1) or pd.isna(rsi_low2):
        return False, None, None

    lower_price_low = price_low2 < price_low1
    higher_rsi_low = rsi_low2 > rsi_low1
    is_recent = (len(recent) - 1 - low2_idx) <= RECENCY_DAYS

    if lower_price_low and higher_rsi_low and is_recent:
        return True, low1_idx, low2_idx

    return False, None, None


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

            df = df.dropna(subset=["Close", "Volume"]).reset_index(drop=True)
            if len(df) < RSI_PERIOD + LOOKBACK_DAYS:
                continue

            df["RSI"] = compute_rsi(df["Close"], RSI_PERIOD)

            last = df.iloc[-1]
            close = last["Close"]
            avg_vol = df["Volume"].tail(20).mean()
            current_rsi = last["RSI"]

            if close <= MIN_PRICE:
                continue
            if avg_vol <= MIN_AVG_VOLUME:
                continue

            is_div, low1_idx, low2_idx = check_bullish_divergence(df)
            if not is_div:
                continue

            recent = df.tail(LOOKBACK_DAYS).reset_index(drop=True)
            results.append({
                "ticker": ticker,
                "close_date": datetime.now().strftime("%Y-%m-%d"),
                "close": round(close, 2),
                "current_rsi": round(current_rsi, 1),
                "price_low1": round(recent["Close"].iloc[low1_idx], 2),
                "price_low2": round(recent["Close"].iloc[low2_idx], 2),
                "rsi_low1": round(recent["RSI"].iloc[low1_idx], 1),
                "rsi_low2": round(recent["RSI"].iloc[low2_idx], 1),
                "avg_vol": int(avg_vol),
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

    print(f"Scan complete. {len(df_out)} tickers show fresh bullish RSI divergence.")
    print(f"Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()