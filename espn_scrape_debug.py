"""One-shot ESPN scrape debug — run from brownlow_engine directory."""
import time, sys
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = (
    "https://www.espn.com.au/afl/story/_/page/POINTSBET20242/"
    "afl-2026-brownlow-medal-predictor-tracker-leaderboard-odds-every-vote"
)

opts = uc.ChromeOptions()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1920,1080")
opts.add_argument("--lang=en-AU")
opts.add_argument(
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

print("Starting Chrome...")
driver = uc.Chrome(options=opts, use_subprocess=True)

try:
    driver.get(URL)
    for sel in ["table", "article", "main", "body"]:
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
            print(f"Page ready (matched '{sel}')")
            break
        except Exception:
            continue
    time.sleep(6)

    html = driver.page_source
    with open("espn_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ESPN DEBUG] Page source saved ({len(html):,} chars) -> espn_debug.html")

    # pd.read_html tables
    try:
        tables = pd.read_html(html)
        print(f"\n[ESPN DEBUG] pd.read_html found {len(tables)} tables")
        for i, t in enumerate(tables[:10]):
            print(f"\n--- Table {i} | shape {t.shape} ---")
            print(f"Columns: {list(t.columns)}")
            print(t.head(10).to_string(index=False))
    except Exception as e:
        print(f"pd.read_html error: {e}")

    # BeautifulSoup raw scan
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    tables_bs = soup.find_all("table")
    print(f"\n[ESPN DEBUG] BeautifulSoup found {len(tables_bs)} <table> elements")
    for i, tbl in enumerate(tables_bs[:6]):
        rows = tbl.find_all("tr")
        print(f"\n--- BS4 Table {i} | {len(rows)} rows ---")
        for row in rows[:6]:
            cells = row.find_all(["td", "th"])
            print([c.get_text(strip=True) for c in cells])

finally:
    driver.quit()
    print("\nDone.")
