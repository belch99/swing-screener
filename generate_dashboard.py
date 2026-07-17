"""
Generates a dashboard page (docs/index.html for weekly, docs/daily.html for daily)
from the corresponding results CSV. Run after the matching screener script.
GitHub Pages serves whatever is in docs/.

Usage:
    python generate_dashboard.py --mode weekly
    python generate_dashboard.py --mode daily
"""

import argparse
import json
import os
from datetime import datetime, timezone

import pandas as pd

MODES = {
    "weekly": {
        "results_file": "weekly_cross_results.csv",
        "output_file": "docs/index.html",
        "eyebrow": "Weekly Scan · Golden Cross",
        "title": "20/50 Weekly SMA Screener",
        "sub": "Scans every NASDAQ and NYSE listed stock for a 20-week SMA closing above the 50-week SMA on the most recently closed weekly bar — filtered for price above $5 and average volume above 500K.",
        "chips": ["Price &gt; $5", "20W Avg Vol &gt; 500K", "Fresh cross only"],
        "footer": "NASDAQ + NYSE · Data via Yahoo Finance · Runs every Saturday via GitHub Actions",
        "empty_sub": "The scan ran clean — no tickers met all three conditions this week. Check back next Saturday.",
        "fast_col": "sma20",
        "slow_col": "sma50",
        "fast_label": "SMA 20",
        "slow_label": "SMA 50",
    },
    "daily": {
        "results_file": "daily_cross_results.csv",
        "output_file": "docs/daily.html",
        "eyebrow": "Daily Scan · 8/21 Momentum",
        "title": "8/21 Daily SMA Screener",
        "sub": "Scans every NASDAQ and NYSE listed stock for price trading above both the 8-day and 21-day SMA, with the 8-day SMA above the 21-day SMA — filtered for price above $5 and average volume above 500K.",
        "chips": ["Price &gt; $5", "20D Avg Vol &gt; 500K", "Price above 8 &amp; 21 SMA"],
        "footer": "NASDAQ + NYSE · Data via Yahoo Finance · Runs automatically at 4:00 PM ET market close",
        "empty_sub": "The scan ran clean — no tickers met all conditions today. Refresh again after tomorrow's close.",
        "fast_col": "sma8",
        "slow_col": "sma21",
        "fast_label": "SMA 8",
        "slow_label": "SMA 21",
    },
    "insiders": {
        "results_file": "insider_buys_results.csv",
        "output_file": "docs/insiders.html",
        "eyebrow": "Insider Activity · Form 4",
        "title": "Insider Buying Screener",
        "sub": "Every SEC Form 4 open-market purchase filed by officers, directors, and 10%+ owners on the most recent business day — option exercises, stock grants, and gifts excluded. Sorted by dollar size, biggest first.",
        "chips": ["Open-market purchases only", "Min $100K", "Price &gt; $5"],
        "footer": "Data via SEC EDGAR · Runs automatically every weekday morning, pre-market",
        "empty_sub": "No qualifying insider purchases met the threshold on the most recent filing day.",
    },
}


def load_results(results_file, mode):
    if not os.path.exists(results_file):
        return []
    df = pd.read_csv(results_file)
    if df.empty:
        return []
    if mode == "insiders":
        df = df.sort_values("total_value", ascending=False)
    else:
        df = df.sort_values("ticker")
    return df.to_dict(orient="records")


def nav_html(active_mode):
    def tab(mode, label, href):
        cls = "nav-tab nav-tab-active" if mode == active_mode else "nav-tab"
        return f'<a class="{cls}" href="{href}">{label}</a>'
    return f"""
    <nav class="top-nav">
      {tab("weekly", "Weekly", "index.html")}
      {tab("daily", "Daily", "daily.html")}
      {tab("insiders", "Insiders", "insiders.html")}
    </nav>"""


def build_html(rows, mode):
    cfg = MODES[mode]
    run_time = datetime.now(timezone.utc).strftime("%b %d, %Y — %H:%M UTC")
    data_json = json.dumps(rows, default=str)
    count = len(rows)

    if mode == "insiders":
        ticker_tape_items = "".join(
            f'<span class="tape-item"><span class="tape-ticker">{r["ticker"]}</span>'
            f'<span class="tape-price">${r["total_value"]:,.0f}</span></span>'
            for r in rows
        ) if rows else '<span class="tape-item tape-empty">NO QUALIFYING INSIDER PURCHASES</span>'
    else:
        ticker_tape_items = "".join(
            f'<span class="tape-item"><span class="tape-ticker">{r["ticker"]}</span>'
            f'<span class="tape-price">${r["close"]:.2f}</span></span>'
            for r in rows
        ) if rows else '<span class="tape-item tape-empty">NO CROSSES DETECTED THIS CYCLE</span>'
    ticker_tape_html = ticker_tape_items + ticker_tape_items

    if mode == "insiders":
        rows_html = ""
        for r in rows:
            rows_html += f"""
        <tr>
          <td class="col-ticker">{r['ticker']}</td>
          <td>{r['insider_name']}</td>
          <td class="mono">{r['title']}</td>
          <td class="mono">{r['transaction_date']}</td>
          <td class="mono num">{r['shares']:,.0f}</td>
          <td class="mono num">${r['price']:.2f}</td>
          <td class="mono num">${r['total_value']:,.0f}</td>
        </tr>"""
        table_headers = """
            <tr>
              <th>Ticker</th>
              <th>Insider</th>
              <th>Title</th>
              <th>Transaction Date</th>
              <th class="num">Shares</th>
              <th class="num">Price</th>
              <th class="num">Total Value</th>
            </tr>"""
    else:
        fast_col = cfg["fast_col"]
        slow_col = cfg["slow_col"]
        rows_html = ""
        for r in rows:
            rows_html += f"""
        <tr>
          <td class="col-ticker">{r['ticker']}</td>
          <td class="mono">{r['close_date']}</td>
          <td class="mono num">${r['close']:.2f}</td>
          <td class="mono num">{r[fast_col]:.2f}</td>
          <td class="mono num">{r[slow_col]:.2f}</td>
          <td class="mono num">{r['avg_vol']:,}</td>
          <td class="mono num">{r['last_vol']:,}</td>
        </tr>"""
        table_headers = f"""
            <tr>
              <th>Ticker</th>
              <th>Cross Date</th>
              <th class="num">Close</th>
              <th class="num">{cfg['fast_label']}</th>
              <th class="num">{cfg['slow_label']}</th>
              <th class="num">Avg Vol</th>
              <th class="num">Last Vol</th>
            </tr>"""

    empty_state = f"""
        <div class="empty-state">
          <div class="empty-glyph">◇</div>
          <div class="empty-title">No crosses this cycle</div>
          <div class="empty-sub">{cfg['empty_sub']}</div>
        </div>""" if not rows else ""

    table_block = f"""
        <table class="results">
          <thead>{table_headers}
          </thead>
          <tbody>{rows_html}
          </tbody>
        </table>""" if rows else empty_state

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{cfg['title']}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0B0E11;
    --surface: #12161B;
    --surface-raised: #171C22;
    --line: #232A31;
    --text: #E6EDF3;
    --text-dim: #7C8B9B;
    --accent: #3DDC84;
    --accent-dim: #1E5E3B;
    --amber: #F0A83B;
    --red: #E5484D;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
  }}
  .tape-wrap {{
    background: var(--surface-raised);
    border-bottom: 1px solid var(--line);
    overflow: hidden;
    white-space: nowrap;
    padding: 10px 0;
  }}
  .tape-track {{
    display: inline-flex;
    animation: scroll 40s linear infinite;
  }}
  @media (prefers-reduced-motion: reduce) {{
    .tape-track {{ animation: none; overflow-x: auto; }}
  }}
  @keyframes scroll {{
    from {{ transform: translateX(0); }}
    to {{ transform: translateX(-50%); }}
  }}
  .tape-item {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 0 24px;
    border-right: 1px solid var(--line);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
  }}
  .tape-empty {{ color: var(--text-dim); letter-spacing: 0.06em; }}
  .tape-ticker {{ color: var(--text); font-weight: 600; }}
  .tape-price {{ color: var(--text-dim); }}

  .top-nav {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 20px 24px 0;
    display: flex;
    gap: 8px;
  }}
  .nav-tab {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    letter-spacing: 0.04em;
    text-decoration: none;
    color: var(--text-dim);
    border: 1px solid var(--line);
    border-radius: 100px;
    padding: 8px 18px;
    transition: all 0.15s ease;
  }}
  .nav-tab:hover {{ color: var(--text); border-color: var(--text-dim); }}
  .nav-tab-active {{
    color: var(--bg);
    background: var(--accent);
    border-color: var(--accent);
    font-weight: 600;
  }}

  header {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 32px 24px 32px;
  }}
  .eyebrow {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.14em;
    color: var(--accent);
    text-transform: uppercase;
    margin-bottom: 14px;
  }}
  h1 {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 40px;
    font-weight: 600;
    letter-spacing: -0.01em;
    margin-bottom: 10px;
  }}
  .sub {{
    color: var(--text-dim);
    font-size: 15px;
    max-width: 620px;
    line-height: 1.55;
  }}
  .meta-row {{
    display: flex;
    gap: 32px;
    margin-top: 28px;
    flex-wrap: wrap;
  }}
  .meta-item {{
    font-family: 'IBM Plex Mono', monospace;
  }}
  .meta-label {{
    font-size: 11px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
  }}
  .meta-value {{
    font-size: 20px;
    color: var(--text);
    font-weight: 500;
  }}
  .meta-value.accent {{ color: var(--accent); }}

  main {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 24px 80px;
  }}

  .criteria {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 32px;
  }}
  .chip {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--text-dim);
    border: 1px solid var(--line);
    border-radius: 100px;
    padding: 6px 14px;
    background: var(--surface);
  }}

  table.results {{
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
  }}
  table.results thead th {{
    text-align: left;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
    padding: 14px 18px;
    border-bottom: 1px solid var(--line);
    background: var(--surface-raised);
  }}
  table.results th.num, table.results td.num {{ text-align: right; }}
  table.results tbody tr {{
    border-bottom: 1px solid var(--line);
    transition: background 0.15s ease;
  }}
  table.results tbody tr:last-child {{ border-bottom: none; }}
  table.results tbody tr:hover {{ background: var(--surface-raised); }}
  table.results td {{
    padding: 14px 18px;
    font-size: 14px;
  }}
  td.col-ticker {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 15px;
  }}
  td.mono {{ font-family: 'IBM Plex Mono', monospace; color: var(--text-dim); }}
  td.mono.num {{ color: var(--text); }}

  .empty-state {{
    text-align: center;
    padding: 90px 24px;
    border: 1px dashed var(--line);
    border-radius: 8px;
  }}
  .empty-glyph {{
    font-size: 32px;
    color: var(--accent-dim);
    margin-bottom: 16px;
  }}
  .empty-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 20px;
    font-weight: 600;
    margin-bottom: 8px;
  }}
  .empty-sub {{
    color: var(--text-dim);
    font-size: 14px;
    max-width: 380px;
    margin: 0 auto;
    line-height: 1.5;
  }}

  footer {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 24px 60px;
    color: var(--text-dim);
    font-size: 12px;
    font-family: 'IBM Plex Mono', monospace;
  }}

  @media (max-width: 700px) {{
    h1 {{ font-size: 30px; }}
    table.results {{ display: block; overflow-x: auto; }}
    .meta-row {{ gap: 20px; }}
  }}
</style>
</head>
<body>

  <div class="tape-wrap">
    <div class="tape-track">{ticker_tape_html}</div>
  </div>
  {nav_html(mode)}

  <header>
    <div class="eyebrow">{cfg['eyebrow']}</div>
    <h1>{cfg['title']}</h1>
    <p class="sub">{cfg['sub']}</p>
    <div class="meta-row">
      <div class="meta-item">
        <div class="meta-label">Last run</div>
        <div class="meta-value">{run_time}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Matches</div>
        <div class="meta-value accent">{count}</div>
      </div>
    </div>
  </header>

  <main>
    <div class="criteria">
      {"".join(f'<span class="chip">{c}</span>' for c in cfg['chips'])}
    </div>
    {table_block}
  </main>

  <footer>
    {cfg['footer']}
  </footer>

<script>
  window.SCREENER_DATA = {data_json};
</script>
</body>
</html>"""

    os.makedirs("docs", exist_ok=True)
    with open(cfg["output_file"], "w") as f:
        f.write(html)
    print(f"Dashboard written to {cfg['output_file']} ({count} matches)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the screener dashboard page")
    parser.add_argument("--mode", choices=["weekly", "daily", "insiders"], required=True)
    args = parser.parse_args()

    cfg = MODES[args.mode]
    rows = load_results(cfg["results_file"], args.mode)
    build_html(rows, args.mode)