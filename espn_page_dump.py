"""
Diagnostic: load ESPN page, scroll to bottom, wait 25s, save full HTML.
Run from brownlow_engine directory.
"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import StringIO

URL = (
    "https://www.espn.com.au/afl/story/_/page/POINTSBET20242/"
    "afl-2026-brownlow-medal-predictor-tracker-leaderboard-odds-every-vote"
)

opts = uc.ChromeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1920,1080")
opts.add_argument(
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

driver = uc.Chrome(options=opts, use_subprocess=True)
try:
    print(f"Loading {URL} ...")
    driver.get(URL)

    # Scroll slowly to bottom to trigger lazy loading
    for scroll_pos in range(0, 20000, 500):
        driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
        time.sleep(0.3)
    print("Scrolled to bottom, waiting 15s for dynamic content ...")
    time.sleep(15)

    # Scroll back up and wait a bit more
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(3)

    html = driver.page_source
    print(f"Page source: {len(html):,} chars")

    with open("espn_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved espn_debug.html")

    # Quick analysis
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    print(f"\nTables found: {len(tables)}")
    for i, t in enumerate(tables):
        rows = t.find_all("tr")
        headers = [c.get_text(strip=True) for c in rows[0].find_all(["th","td"])] if rows else []
        print(f"  Table {i}: {len(rows)} rows, headers: {headers[:12]}")

    text = soup.get_text(" ", strip=True)
    print(f"\nVisible text: {len(text):,} chars")

    # Search for vote patterns
    for pat in [r"\d\.?\d? votes?", r"Round \d+ votes", r"Game \d"]:
        hits = re.findall(r".{0,80}" + pat + r".{0,80}", text, re.IGNORECASE)[:3]
        if hits:
            print(f'\nPattern "{pat}":')
            for h in hits:
                print(f"  {h!r}")

    # Try pd.read_html
    try:
        dfs = pd.read_html(StringIO(html))
        print(f"\npd.read_html found {len(dfs)} tables")
        for i, df in enumerate(dfs):
            print(f"  df[{i}]: shape={df.shape}, cols={df.columns.tolist()[:8]}")
    except Exception as e:
        print(f"pd.read_html error: {e}")

finally:
    driver.quit()
    print("\nDone.")
