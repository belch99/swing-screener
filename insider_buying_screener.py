"""
Insider Buying Screener (SEC Form 4)
--------------------------------------
Pulls every Form 4 (insider transaction) filed with the SEC on the most recent
business day, keeps only genuine OPEN MARKET PURCHASES by officers/directors/
10%+ owners (excludes option exercises, stock grants/awards, and gifts - those
aren't real conviction buys), and filters for size so this isn't cluttered
with $2,000 dribble purchases.

Data source: SEC EDGAR daily filing index + individual Form 4 XML documents.
100% free, no API key. SEC asks that automated requests identify themselves
with a descriptive User-Agent - see USER_AGENT below, personalize it with
your own contact info if you want (not required to run, just SEC's preference).

SETUP (run once):
    pip install requests pandas

RUN:
    python insider_buying_screener.py

    Optional flags:
    python insider_buying_screener.py --min-value 100000 --min-price 5

Output:
    Prints matches to the console and saves them to insider_buys_results.csv
"""

import argparse
import re
import sys
import time
from datetime import date, timedelta
from xml.etree import ElementTree

import pandas as pd
import requests

USER_AGENT = "swing-screener-personal-use contact@example.com"  # SEC asks for a descriptive UA - edit if you like
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_DELAY = 0.15  # seconds between SEC requests, stays comfortably under their 10 req/sec limit


def previous_business_day(from_date=None):
    d = from_date or date.today()
    d = d - timedelta(days=1)
    while d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        d = d - timedelta(days=1)
    return d


def fetch_daily_index(target_date, attempts_back=5):
    """Fetch the SEC daily filing index for target_date. If empty/missing
    (holiday, weekend edge case), step back further business days."""
    d = target_date
    for _ in range(attempts_back):
        year = d.year
        quarter = (d.month - 1) // 3 + 1
        date_str = d.strftime("%Y%m%d")
        url = f"https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/form.{date_str}.idx"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text, d
        except requests.RequestException:
            pass
        d = previous_business_day(d)
    return None, None


def parse_form4_rows(index_text):
    """Extract (cik, company, date_filed, file_path) for Form Type == '4' rows only
    (excludes 4/A amendments, Form 3, Form 5, etc.)."""
    rows = []
    started = False
    for line in index_text.splitlines():
        if line.startswith("Form Type"):
            started = True
            continue
        if not started:
            continue
        if not line.strip():
            continue
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 5:
            continue
        form_type = parts[0].strip()
        if form_type != "4":
            continue
        company, cik, date_filed, file_path = parts[1], parts[2], parts[3], parts[4]
        rows.append({"cik": cik, "company": company, "date_filed": date_filed, "file_path": file_path})
    return rows


def fetch_and_parse_filing(file_path):
    """Fetch one Form 4 submission and extract qualifying open-market purchases.
    Returns a list of transaction dicts (usually 0 or 1, occasionally more if an
    insider reported multiple purchase lots in one filing)."""
    url = f"https://www.sec.gov/Archives/{file_path}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return []
        text = resp.text
    except requests.RequestException:
        return []

    xml_match = re.search(r"<XML>(.*?)</XML>", text, re.DOTALL)
    xml_text = xml_match.group(1).strip() if xml_match else None
    if not xml_text:
        # some filings embed the ownership doc without an <XML> wrapper
        doc_match = re.search(r"(<ownershipDocument>.*?</ownershipDocument>)", text, re.DOTALL)
        xml_text = doc_match.group(1) if doc_match else None
    if not xml_text:
        return []

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []

    def find_text(el, path):
        node = el.find(path)
        return node.text.strip() if node is not None and node.text else None

    ticker = find_text(root, "./issuer/issuerTradingSymbol")
    if not ticker:
        return []

    owner_name = find_text(root, "./reportingOwner/reportingOwnerId/rptOwnerName") or "Unknown"
    is_officer = find_text(root, "./reportingOwner/reportingOwnerRelationship/isOfficer") == "1"
    is_director = find_text(root, "./reportingOwner/reportingOwnerRelationship/isDirector") == "1"
    is_ten_pct = find_text(root, "./reportingOwner/reportingOwnerRelationship/isTenPercentOwner") == "1"
    officer_title = find_text(root, "./reportingOwner/reportingOwnerRelationship/officerTitle")

    if is_officer and officer_title:
        title = officer_title
    elif is_officer:
        title = "Officer"
    elif is_director:
        title = "Director"
    elif is_ten_pct:
        title = "10%+ Owner"
    else:
        title = "Insider"

    results = []
    for txn in root.findall("./nonDerivativeTable/nonDerivativeTransaction"):
        code = find_text(txn, "./transactionCoding/transactionCode")
        acquired_disposed = find_text(txn, "./transactionAmounts/transactionAcquiredDisposedCode/value")
        if code != "P" or acquired_disposed != "A":
            continue  # only genuine open-market purchases, not exercises/grants/gifts

        shares_text = find_text(txn, "./transactionAmounts/transactionShares/value")
        price_text = find_text(txn, "./transactionAmounts/transactionPricePerShare/value")
        txn_date = find_text(txn, "./transactionDate/value")

        try:
            shares = float(shares_text)
            price = float(price_text)
        except (TypeError, ValueError):
            continue

        results.append({
            "ticker": ticker.upper(),
            "insider_name": owner_name,
            "title": title,
            "transaction_date": txn_date,
            "shares": shares,
            "price": round(price, 2),
            "total_value": round(shares * price, 2),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="SEC Form 4 insider open-market purchase screener")
    parser.add_argument("--min-value", type=float, default=100_000, help="Minimum dollar value of a single purchase to include")
    parser.add_argument("--min-price", type=float, default=5.0, help="Minimum share price to include")
    parser.add_argument("--output", default="insider_buys_results.csv")
    args = parser.parse_args()

    target = previous_business_day()
    print(f"Fetching SEC Form 4 daily index for {target}...")
    index_text, actual_date = fetch_daily_index(target)
    if not index_text:
        print("Could not fetch a daily index (SEC may be down or this was a market holiday). Exiting with no results.")
        pd.DataFrame([]).to_csv(args.output, index=False)
        return

    rows = parse_form4_rows(index_text)
    print(f"Found {len(rows)} Form 4 filings for {actual_date}. Fetching and parsing each one...")

    all_matches = []
    for i, row in enumerate(rows, 1):
        if i % 50 == 0:
            print(f"  ...{i}/{len(rows)} processed")
        matches = fetch_and_parse_filing(row["file_path"])
        for m in matches:
            m["filed_date"] = row["date_filed"]
            all_matches.append(m)
        time.sleep(REQUEST_DELAY)

    if not all_matches:
        print("\nNo qualifying open-market purchases found.")
        pd.DataFrame([]).to_csv(args.output, index=False)
        return

    df = pd.DataFrame(all_matches)
    df = df[(df["total_value"] >= args.min_value) & (df["price"] >= args.min_price)]

    if df.empty:
        print("\nFilings found, but none met the value/price thresholds.")
        pd.DataFrame([]).to_csv(args.output, index=False)
        return

    df = df.sort_values("total_value", ascending=False)
    df.to_csv(args.output, index=False)

    print(f"\nFound {len(df)} qualifying insider purchases. Saved to {args.output}\n")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
