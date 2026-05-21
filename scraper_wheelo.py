"""
Wheelo Match Stats Scraper
Automatically downloads round-by-round player stats for all seasons
Saves to data_wheelo/ folder then merges into one CSV
Run: python scraper_wheelo.py
"""

import os
import time
import glob
import shutil
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

# ── Config ───────────────────────────────────────────────────
SEASONS = list(range(2015, 2027))
DOWNLOAD_DIR = os.path.abspath("data_wheelo/downloads")
OUTPUT_DIR = os.path.abspath("data_wheelo")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://www.wheeloratings.com/afl_match_stats.html"

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Configure automatic downloads
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True
    }
    options.add_experimental_option("prefs", prefs)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def wait_for_download(timeout=15):
    """Wait for a CSV file to appear in download dir"""
    start = time.time()
    while time.time() - start < timeout:
        files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv")) + \
                glob.glob(os.path.join(DOWNLOAD_DIR, "*.CSV"))
        # Exclude .crdownload (in progress)
        complete = [f for f in files if not f.endswith('.crdownload')]
        if complete:
            time.sleep(0.5)  # Small buffer to ensure write is complete
            return max(complete, key=os.path.getmtime)
    return None

def clear_downloads():
    """Clear download folder before each round"""
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv")):
        os.remove(f)

def select_season_round(driver, season, round_num):
    """Navigate to a specific season/round on Wheelo"""
    url = f"{BASE_URL}?id={season}{round_num:02d}"
    driver.get(url)
    time.sleep(2)
    
    # Check if page loaded with data
    try:
        # Look for table or data indicator
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        return True
    except:
        # Try checking page title or content
        if str(season) in driver.title or "Round" in driver.page_source:
            return True
        return False

def click_download(driver):
    """Find and click the Download CSV button"""
    # Try multiple selectors
    selectors = [
        "//a[contains(text(),'Download') and contains(text(),'CSV')]",
        "//button[contains(text(),'CSV')]",
        "//a[contains(@href,'csv')]",
        "//a[contains(@onclick,'csv') or contains(@onclick,'CSV')]",
        "//*[contains(@class,'download')]",
        "//a[contains(text(),'Download')]",
    ]
    
    for sel in selectors:
        try:
            btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, sel))
            )
            btn.click()
            return True
        except:
            continue
    
    # Try finding by partial text
    try:
        elements = driver.find_elements(By.XPATH, "//*[contains(text(),'CSV') or contains(text(),'csv')]")
        for el in elements:
            if el.is_displayed() and el.is_enabled():
                el.click()
                return True
    except:
        pass
    
    return False

def parse_table_from_page(driver, season, round_num):
    """Parse stats table directly from page source as fallback"""
    import io
    rows = []
    try:
        tables = driver.find_elements(By.TAG_NAME, "table")
        for table in tables:
            html = table.get_attribute('outerHTML')
            try:
                dfs = pd.read_html(io.StringIO(html))
                for df in dfs:
                    if len(df) > 5 and len(df.columns) > 8:
                        df['Season'] = season
                        df['Round'] = round_num
                        rows = df.to_dict('records')
                        return rows
            except:
                continue
    except:
        pass
    return rows

def scrape_all():
    print("=" * 60)
    print("WHEELO MATCH STATS SCRAPER")
    print(f"Seasons: {SEASONS[0]} - {SEASONS[-1]}")
    print(f"Download dir: {DOWNLOAD_DIR}")
    print("=" * 60)
    
    driver = get_driver()
    all_data = []
    failed = []
    
    try:
        # First load the page to accept any cookies
        print("\nInitialising browser...")
        driver.get(BASE_URL)
        time.sleep(3)
        
        # Accept cookies if prompted
        try:
            accept_btn = driver.find_element(By.XPATH, 
                "//button[contains(text(),'Accept') or contains(text(),'OK') or contains(text(),'agree')]")
            accept_btn.click()
            time.sleep(1)
            print("  Accepted cookies")
        except:
            pass
        
        # Check what the page looks like
        print(f"  Page title: {driver.title}")
        print(f"  Checking for download button...")
        
        # Look for all links/buttons on initial page
        all_links = driver.find_elements(By.TAG_NAME, "a")
        csv_links = [l for l in all_links if 'csv' in (l.text + (l.get_attribute('href') or '')).lower()]
        print(f"  Found {len(csv_links)} CSV-related links")
        for l in csv_links[:3]:
            print(f"    - '{l.text}' -> {l.get_attribute('href')}")
        
        # Main scraping loop
        for season in SEASONS:
            season_rows = []
            print(f"\nSeason {season}:")
            
            # Wheelo uses Round 0 for the Opening Round (AFL seasons from 2023+),
            # which corresponds to Round 1 in AFLTables. We scrape from Round 0
            # and store the round as round_num+1 to align with AFLTables numbering.
            wheelo_start = 0 if season >= 2023 else 1
            for round_num in range(wheelo_start, 30):
                clear_downloads()

                # Navigate to round
                has_data = select_season_round(driver, season, round_num)

                if not has_data:
                    if round_num == 0:
                        print(f"  Round 0: no Opening Round data — starting from Round 1")
                        continue
                    print(f"  Round {round_num}: no page data — stopping season")
                    break

                # AFLTables round number: Opening Round (Wheelo 0) → stored as Round 1
                afltables_round = round_num + 1 if season >= 2023 else round_num

                # Try download button first
                downloaded = False
                if click_download(driver):
                    filepath = wait_for_download(timeout=10)
                    if filepath:
                        try:
                            df = pd.read_csv(filepath)
                            df['Season'] = season
                            df['Round'] = afltables_round
                            rows = df.to_dict('records')
                            season_rows.extend(rows)
                            print(f"  Round {round_num}: ✓ downloaded {len(df)} rows")
                            downloaded = True
                        except Exception as e:
                            print(f"  Round {round_num}: download parse error — {e}")
                
                # Fallback: parse table from page
                if not downloaded:
                    rows = parse_table_from_page(driver, season, round_num)
                    if rows:
                        for row in rows:
                            row['Round'] = afltables_round
                        season_rows.extend(rows)
                        print(f"  Round {round_num}: ✓ parsed {len(rows)} rows from page")
                    else:
                        print(f"  Round {round_num}: ⚠ no data")
                        failed.append((season, afltables_round))
                        # Stop if 3 consecutive empty rounds
                        if round_num >= 3:
                            recent_failed = sum(1 for s,r in failed[-3:] if s==season and r >= afltables_round-2)
                            if recent_failed >= 3:
                                print(f"  3 consecutive empty rounds — moving to next season")
                                break
                
                time.sleep(1)
            
            if season_rows:
                df_season = pd.DataFrame(season_rows)
                df_season.to_csv(f"{OUTPUT_DIR}/wheelo_{season}.csv", index=False)
                all_data.extend(season_rows)
                print(f"  ✓ Season {season} saved: {len(season_rows)} total rows")
                print(f"  Columns: {list(df_season.columns)[:10]}...")
            else:
                print(f"  ⚠ Season {season}: no data retrieved")
    
    finally:
        driver.quit()
        print("\nBrowser closed.")
    
    # Merge all seasons
    if all_data:
        df_all = pd.DataFrame(all_data)
        df_all.to_csv(f"{OUTPUT_DIR}/wheelo_all_seasons.csv", index=False)
        print(f"\n✓ Merged {len(df_all):,} rows saved to data_wheelo/wheelo_all_seasons.csv")
        print(f"\nColumns found:")
        for col in df_all.columns:
            print(f"  - {col}")
        print(f"\nSample data:")
        print(df_all.head(3).to_string())
    else:
        print("\n⚠ No data scraped.")
        print("\nManual fallback instructions:")
        print("1. Go to https://www.wheeloratings.com/afl_match_stats.html")
        print("2. Select season and round")
        print("3. Click 'Download as CSV'")
        print("4. Save each file to data_wheelo/downloads/")
        print("5. Run: python merge_wheelo.py")
    
    print(f"\nFailed rounds: {len(failed)}")
    if failed:
        print(failed[:20])
    
    print("\nDone.")

if __name__ == "__main__":
    scrape_all()
