"""
Daily 20/50 SMA Cross Screener
--------------------------------
Scans NASDAQ + NYSE listed stocks for a daily close where the 20-day SMA
crosses above the 50-day SMA (a "golden cross" on the daily timeframe).

Filters applied:
  - Last close > $5
  - 20-day average volume > 500,000
  - Cross must have happened on the MOST RECENTLY CLOSED daily bar

Data source: Yahoo Finance via the free `yfinance` library. No API key needed.

SETUP (run once):
    pip install yfinance pandas

RUN:
    python daily_sma_cross_screener.py

    Optional flags:
    python daily_sma_cross_screener.py --tickers all_tickers.csv --min-price 5 --min-avg-vol 500000

Output:
    Prints matches to the console and saves them to daily_cross_results.csv
"""

import argparse
import socket
import sys
import time
import pandas as pd
import yfinance as yf

socket.setdefaulttimeout(30)  # hard ceiling on any network call so a stalled request fails fast instead of hanging

CHUNK_SIZE = 200          # tickers per batch download (keeps requests stable)
LOOKBACK_PERIOD = "1y"    # enough daily bars to compute a 50-day SMA reliably


def load_tickers(path: str) -> list[str]:
    df = pd.read_csv(path)
    tickers = df["ticker"].dropna().astype(str).str.upper().tolist()
    # Drop obvious non-common-stock symbols: warrants, units, rights, when-issued, preferreds
    cleaned = [t for t in tickers if t.isalpha() and 1 <= len(t) <= 5]
    return sorted(set(cleaned))


def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def screen_batch(tickers, min_price, min_avg_vol):
    matches = []
    try:
        data = yf.download(
            tickers=tickers,
            period=LOOKBACK_PERIOD,
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=True,
            timeout=30,
        )
    except Exception as e:
        print(f"  batch download failed: {e}", file=sys.stderr)
        return matches

    for t in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                df = data[t]
            df = df.dropna(how="all")
            if df.empty or len(df) < 51:  # need 51+ daily bars for a reliable 50-day SMA
                continue

            close = df["Close"]
            volume = df["Volume"]

            sma20 = close.rolling(20).mean()
            sma50 = close.rolling(50).mean()

            if len(sma20) < 2 or pd.isna(sma20.iloc[-1]) or pd.isna(sma50.iloc[-1]):
                continue
            if pd.isna(sma20.iloc[-2]) or pd.isna(sma50.iloc[-2]):
                continue

            last_close = close.iloc[-1]
            if last_close <= min_price:
                continue

            avg_vol = volume.rolling(20).mean().iloc[-1]
            if pd.isna(avg_vol) or avg_vol <= min_avg_vol:
                continue

            crossed_today = sma20.iloc[-2] <= sma50.iloc[-2] and sma20.iloc[-1] > sma50.iloc[-1]  # "today" = most recent daily close
            if not crossed_today:
                continue

            last_vol = volume.iloc[-1]

            matches.append({
                "ticker": t,
                "close_date": df.index[-1].date(),
                "close": round(float(last_close), 2),
                "sma20": round(float(sma20.iloc[-1]), 2),
                "sma50": round(float(sma50.iloc[-1]), 2),
                "avg_vol": int(avg_vol),
                "last_vol": int(last_vol),
            })
        except Exception:
            continue

    return matches


def main():
    parser = argparse.ArgumentParser(description="Daily 20/50 SMA cross screener")
    parser.add_argument("--tickers", default="all_tickers.csv", help="CSV file with a 'ticker' column")
    parser.add_argument("--min-price", type=float, default=5.0)
    parser.add_argument("--min-avg-vol", type=float, default=500_000)
    parser.add_argument("--output", default="daily_cross_results.csv")
    args = parser.parse_args()

    tickers = load_tickers(args.tickers)
    print(f"Loaded {len(tickers)} tickers. Scanning in batches of {CHUNK_SIZE}...")

    all_matches = []
    batches = list(chunk(tickers, CHUNK_SIZE))
    for i, batch in enumerate(batches, 1):
        print(f"  batch {i}/{len(batches)} ({len(batch)} tickers)...")
        matches = screen_batch(batch, args.min_price, args.min_avg_vol)
        all_matches.extend(matches)
        time.sleep(1)  # small pause to be polite to Yahoo's endpoint

    if not all_matches:
        print("\nNo matches found today.")
        return

    result_df = pd.DataFrame(all_matches).sort_values("ticker")
    result_df.to_csv(args.output, index=False)

    print(f"\nFound {len(result_df)} matches. Saved to {args.output}\n")
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()
