# 20/50 SMA Cross Screener + Dashboard (Weekly + Daily)

Scans every NASDAQ + NYSE listed stock for a 20-period SMA crossing above the
50-period SMA, filtered for price > $5 and average volume > 500K. Two modes,
one dashboard site with tabs to switch between them:

- **Weekly** — runs automatically every Saturday morning via GitHub Actions
- **Daily** — you manually trigger it yourself after each day's market close

## What's in this folder

- `weekly_sma_cross_screener.py` — runs the weekly scan
- `daily_sma_cross_screener.py` — runs the daily scan
- `generate_dashboard.py` — builds both dashboard pages (`--mode weekly` or `--mode daily`)
- `all_tickers.csv` — the list of NASDAQ + NYSE tickers to scan (shared by both)
- `docs/index.html` — the Weekly dashboard page (auto-rebuilt every Saturday)
- `docs/daily.html` — the Daily dashboard page (rebuilt when you manually trigger it)
- `docs/.nojekyll` — tells GitHub Pages not to run this through Jekyll (required — do not delete)
- `.github/workflows/weekly-screener.yml` — the Saturday automation
- `.github/workflows/daily-screener.yml` — manual-trigger-only workflow for the daily scan

Setup instructions are in the message this came with.

## Running the daily scan after market close

1. Go to your repo's **Actions** tab
2. Click **Daily SMA Cross Screener** on the left
3. Click **Run workflow** → **Run workflow**
4. Wait a few minutes, then open your dashboard link and click the **Daily** tab
