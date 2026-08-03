"""
Quick updater: fetches missing 2026 rounds from wheeloratings.com and
appends to wheelo_2026.csv. Runs much faster than the full scraper.
"""

import os
import io
import time
import glob
import shutil
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

SEASON = 2026
DOWNLOAD_DIR = os.path.abspath("data_wheelo/downloads")
OUTPUT_CSV = "data_wheelo/wheelo_2026.csv"
BASE_URL = "https://www.wheeloratings.com/afl_match_stats.html"

# ── Round numbering rule ─────────────────────────────────────
# The AFL introduced a standalone "Opening Round" in 2024. Wheelo numbers that
# fixture Round 0, so for any season with an Opening Round every Wheelo round
# sits one behind the AFLTables convention this repo uses everywhere:
#
#     afltables_round = wheelo_round + 1   for 2024, 2025, 2026
#     afltables_round = wheelo_round       for 2015-2023
#
# 2023 does NOT get the +1 — the AFL had no Opening Round that year, and
# wheelo_2023.csv on disk carries no offset, matching fitzroy_stats_all.csv on
# Disposals at 100% (n=7,730) with the round used as-is. The rule was
# previously written as `season >= 2023`, which would have applied a spurious
# +1 to 2023 and broken that alignment on any re-scrape.
#
# This script only ever runs for SEASON = 2026, which is on the +1 side of the
# rule, so the offset is unconditional here. The guard below keeps that
# assumption honest if SEASON is ever bumped or reused.
OPENING_ROUND_FIRST_SEASON = 2024
ROUND_OFFSET = 1 if SEASON >= OPENING_ROUND_FIRST_SEASON else 0

# Wheelo's own published per-game Brownlow vote predictions. The dashboard's
# Model Comparison sums the 'Votes' column per player to reproduce
# wheeloratings.com's published leaderboard exactly (not our match-stats sum).
BROWNLOW_CSV_URL = "https://www.wheeloratings.com/src/data/wheelo-brownlow-predictions.csv"
BROWNLOW_OUTPUT = "data_2026/wheelo_brownlow_predictions.csv"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def fetch_brownlow_predictions():
    """Download Wheelo's published Brownlow vote predictions (plain CSV, no
    Selenium needed). Independent of the match-stats fetch below."""
    import requests
    try:
        os.makedirs(os.path.dirname(BROWNLOW_OUTPUT), exist_ok=True)
        resp = requests.get(
            BROWNLOW_CSV_URL,
            headers={"User-Agent": "Mozilla/5.0"}, timeout=30,
        )
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if "Player" not in df.columns or "Votes" not in df.columns:
            print(f"  Brownlow predictions: unexpected columns "
                  f"{list(df.columns)[:6]} — skipped")
            return
        df.to_csv(BROWNLOW_OUTPUT, index=False)
        lead = (df.groupby("Player")["Votes"].sum()
                .sort_values(ascending=False).head(8))
        print(f"  Brownlow predictions: saved {len(df)} rows -> {BROWNLOW_OUTPUT}")
        print("  Top: " + ", ".join(f"{p} {v:.1f}" for p, v in lead.items()))
    except Exception as e:
        print(f"  Brownlow predictions fetch failed: {e}")


def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def clear_downloads():
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv")):
        os.remove(f)


def wait_for_download(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        files = [
            f for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv"))
            if not f.endswith('.crdownload')
        ]
        if files:
            time.sleep(0.5)
            return max(files, key=os.path.getmtime)
        time.sleep(0.5)
    return None


def click_download(driver):
    selectors = [
        "//a[contains(text(),'Download') and contains(text(),'CSV')]",
        "//button[contains(text(),'CSV')]",
        "//a[contains(@href,'csv')]",
        "//a[contains(text(),'Download')]",
        "//*[contains(@class,'download')]",
    ]
    for sel in selectors:
        try:
            btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, sel))
            )
            btn.click()
            return True
        except Exception:
            continue
    # Fallback: any visible CSV element
    try:
        for el in driver.find_elements(By.XPATH, "//*[contains(text(),'CSV')]"):
            if el.is_displayed() and el.is_enabled():
                el.click()
                return True
    except Exception:
        pass
    return False


def parse_table_from_page(driver):
    try:
        for table in driver.find_elements(By.TAG_NAME, "table"):
            html = table.get_attribute('outerHTML')
            dfs = pd.read_html(io.StringIO(html))
            for df in dfs:
                if len(df) > 5 and len(df.columns) > 8:
                    return df
    except Exception:
        pass
    return None


def fetch_round(driver, wheelo_round):
    """Fetch one round. Returns DataFrame or None."""
    url = f"{BASE_URL}?id={SEASON}{wheelo_round:02d}"
    driver.get(url)
    time.sleep(2)

    # Check page has data
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
    except Exception:
        if str(SEASON) not in driver.title and "Round" not in driver.page_source:
            return None

    # Try download first
    clear_downloads()
    if click_download(driver):
        filepath = wait_for_download(timeout=10)
        if filepath:
            try:
                df = pd.read_csv(filepath)
                print(f"  Wheelo R{wheelo_round:02d}: downloaded {len(df)} rows")
                return df
            except Exception as e:
                print(f"  Wheelo R{wheelo_round:02d}: download parse error — {e}")

    # Fallback: parse from page
    df = parse_table_from_page(driver)
    if df is not None:
        print(f"  Wheelo R{wheelo_round:02d}: parsed {len(df)} rows from page")
        return df

    print(f"  Wheelo R{wheelo_round:02d}: no data")
    return None


def main():
    # Wheelo's published Brownlow leaderboard (drives Model Comparison) — fetch
    # first so it refreshes even if the Selenium match-stats step below fails.
    print("Fetching Wheelo published Brownlow predictions...")
    fetch_brownlow_predictions()

    # Load existing data
    if os.path.exists(OUTPUT_CSV):
        existing = pd.read_csv(OUTPUT_CSV)
        existing_rounds = set(existing['Round'].unique())
    else:
        existing = pd.DataFrame()
        existing_rounds = set()

    print(f"Existing AFLTables rounds: {sorted(existing_rounds)}")

    # 2026 has an Opening Round, so afltables_round = wheelo_round + ROUND_OFFSET
    # (see the rule at the top of this file). Wheelo rounds 0-23 → AFLTables 1-24.
    # Fetch rounds not already in the CSV, up to AFLTables round 24.
    max_wheelo_round = 23  # try up to Wheelo round 23 (AFLTables 24)
    rounds_to_fetch = [
        r for r in range(0, max_wheelo_round + 1)
        if (r + ROUND_OFFSET) not in existing_rounds
    ]
    print(f"Wheelo rounds to fetch: {rounds_to_fetch}")

    if not rounds_to_fetch:
        print("Data already up to date.")
        return

    driver = get_driver()
    new_rows = []
    consecutive_empty = 0

    try:
        print(f"\nFetching {SEASON} missing rounds from wheeloratings.com...\n")
        for wheelo_round in rounds_to_fetch:
            afltables_round = wheelo_round + ROUND_OFFSET
            df = fetch_round(driver, wheelo_round)
            if df is not None and len(df) > 0:
                df['Season'] = SEASON
                df['Round'] = afltables_round
                new_rows.extend(df.to_dict('records'))
                consecutive_empty = 0
            else:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    print(f"  3 consecutive empty rounds — stopping.")
                    break
            time.sleep(1)
    finally:
        driver.quit()

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([existing, new_df], ignore_index=True) if not existing.empty else new_df
        # Backup and save
        if os.path.exists(OUTPUT_CSV):
            shutil.copy2(OUTPUT_CSV, OUTPUT_CSV.replace('.csv', '_prev.csv'))
        combined.to_csv(OUTPUT_CSV, index=False)
        print(f"\nSaved {len(combined)} total rows to {OUTPUT_CSV}")
        print(f"  Added {len(new_df)} new rows for AFLTables rounds "
              f"{sorted(new_df['Round'].unique())}")

        # Show updated leaderboard
        col = next((c for c in ['ExpVotes', 'RatingPoints'] if c in combined.columns), None)
        if col:
            agg = combined.groupby('Player')[col].sum().sort_values(ascending=False).head(10)
            print(f"\nTop 10 by {col}:")
            for p, v in agg.items():
                print(f"  {v:6.2f}  {p}")
    else:
        print("\nNo new data retrieved.")


if __name__ == '__main__':
    main()
