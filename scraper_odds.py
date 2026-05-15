"""
Brownlow Odds Scraper - Headless Chrome
Scrapes Brownlow winner odds from Sportsbet, TAB, Ladbrokes, Pointsbet, Bet365
"""

import pandas as pd
import time
import os
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

os.makedirs("data_2026", exist_ok=True)

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
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def clean_odds(text):
    """Extract decimal odds from text"""
    text = str(text).strip()
    # Match patterns like $3.50, 3.50, 3/1
    match = re.search(r'\$?([\d]+\.[\d]+)', text)
    if match:
        val = float(match.group(1))
        return val if val > 1.0 else None
    # Fractional odds e.g. 5/2
    frac = re.search(r'(\d+)/(\d+)', text)
    if frac:
        return round(int(frac.group(1))/int(frac.group(2)) + 1, 2)
    return None

def clean_name(name):
    name = str(name).strip()
    if '(' in name:
        name = name[:name.index('(')].strip()
    # Remove common suffixes
    for suffix in [' (', ' -', ' *']:
        if suffix in name:
            name = name[:name.index(suffix)].strip()
    return name

all_odds = []

# ── Sportsbet ────────────────────────────────────────────────
def scrape_sportsbet(driver):
    print("  Scraping Sportsbet...")
    results = []
    try:
        driver.get("https://www.sportsbet.com.au/betting/australian-rules/afl-brownlow-medal")
        time.sleep(4)
        
        # Accept cookies if prompted
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(),'Accept')]")
            btn.click()
            time.sleep(1)
        except: pass
        
        # Scroll to load all odds
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Try multiple selectors
        selectors = [
            ("[data-automation-id*='competitorName']", "[data-automation-id*='price']"),
            (".sc-fhYwyz", ".sc-bcXHqe"),
            (".competitor-name", ".price-text"),
            (".name", ".odds"),
        ]
        
        for name_sel, price_sel in selectors:
            try:
                names = driver.find_elements(By.CSS_SELECTOR, name_sel)
                prices = driver.find_elements(By.CSS_SELECTOR, price_sel)
                if names and prices:
                    for n, p in zip(names, prices):
                        name = clean_name(n.text)
                        odds = clean_odds(p.text)
                        if name and odds and len(name) > 3:
                            results.append({'player': name, 'odds_decimal': odds, 'bookie': 'Sportsbet'})
                    if results:
                        break
            except: continue
        
        # Fallback: parse page source for odds patterns
        if not results:
            source = driver.page_source
            # Look for JSON data
            matches = re.findall(r'"name":"([^"]+)","price":([\d.]+)', source)
            for name, price in matches:
                odds = float(price)
                if odds > 1.0 and len(name) > 3:
                    results.append({'player': clean_name(name), 'odds_decimal': odds, 'bookie': 'Sportsbet'})
        
        print(f"    {'✓' if results else '⚠'} {len(results)} odds found")
    except Exception as e:
        print(f"    ✗ Error: {e}")
    return results

# ── TAB ──────────────────────────────────────────────────────
def scrape_tab(driver):
    print("  Scraping TAB...")
    results = []
    try:
        driver.get("https://www.tab.com.au/sports/betting/Australian%20Rules/competitions/Brownlow%20Medal/markets/Brownlow%20Medal%20Winner")
        time.sleep(4)
        
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(),'Accept') or contains(text(),'OK')]")
            btn.click()
            time.sleep(1)
        except: pass
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        selectors = [
            (".runner-name", ".price-button"),
            (".competitor", ".odds-button"),
            ("[class*='RunnerName']", "[class*='Price']"),
            (".name", "[class*='price']"),
        ]
        
        for name_sel, price_sel in selectors:
            try:
                names = driver.find_elements(By.CSS_SELECTOR, name_sel)
                prices = driver.find_elements(By.CSS_SELECTOR, price_sel)
                if names and prices:
                    for n, p in zip(names, prices):
                        name = clean_name(n.text)
                        odds = clean_odds(p.text)
                        if name and odds and len(name) > 3:
                            results.append({'player': name, 'odds_decimal': odds, 'bookie': 'TAB'})
                    if results: break
            except: continue
        
        if not results:
            source = driver.page_source
            matches = re.findall(r'"runnerName":"([^"]+)"[^}]*"winPrice":([\d.]+)', source)
            for name, price in matches:
                odds = float(price)
                if odds > 1.0:
                    results.append({'player': clean_name(name), 'odds_decimal': odds, 'bookie': 'TAB'})
        
        print(f"    {'✓' if results else '⚠'} {len(results)} odds found")
    except Exception as e:
        print(f"    ✗ Error: {e}")
    return results

# ── Ladbrokes ────────────────────────────────────────────────
def scrape_ladbrokes(driver):
    print("  Scraping Ladbrokes...")
    results = []
    try:
        driver.get("https://www.ladbrokes.com.au/sports/australian-rules-football/brownlow-medal")
        time.sleep(4)
        
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(),'Accept')]")
            btn.click()
            time.sleep(1)
        except: pass
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        selectors = [
            (".selection-name", ".price"),
            ("[class*='SelectionName']", "[class*='Price']"),
            (".competitor-name", ".odds"),
            (".name", ".price-text"),
        ]
        
        for name_sel, price_sel in selectors:
            try:
                names = driver.find_elements(By.CSS_SELECTOR, name_sel)
                prices = driver.find_elements(By.CSS_SELECTOR, price_sel)
                if names and prices:
                    for n, p in zip(names, prices):
                        name = clean_name(n.text)
                        odds = clean_odds(p.text)
                        if name and odds and len(name) > 3:
                            results.append({'player': name, 'odds_decimal': odds, 'bookie': 'Ladbrokes'})
                    if results: break
            except: continue
        
        if not results:
            source = driver.page_source
            matches = re.findall(r'"name":"([A-Z][a-z]+ [A-Z][a-z]+)"[^}]*"price":([\d.]+)', source)
            for name, price in matches:
                odds = float(price)
                if odds > 1.0:
                    results.append({'player': clean_name(name), 'odds_decimal': odds, 'bookie': 'Ladbrokes'})
        
        print(f"    {'✓' if results else '⚠'} {len(results)} odds found")
    except Exception as e:
        print(f"    ✗ Error: {e}")
    return results

# ── Pointsbet ────────────────────────────────────────────────
def scrape_pointsbet(driver):
    print("  Scraping Pointsbet...")
    results = []
    try:
        driver.get("https://pointsbet.com.au/sports/aussie-rules/brownlow-medal")
        time.sleep(4)
        
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(),'Accept')]")
            btn.click()
            time.sleep(1)
        except: pass
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        selectors = [
            (".outcome-name", ".price"),
            ("[class*='OutcomeName']", "[class*='Price']"),
            (".name", ".odds"),
        ]
        
        for name_sel, price_sel in selectors:
            try:
                names = driver.find_elements(By.CSS_SELECTOR, name_sel)
                prices = driver.find_elements(By.CSS_SELECTOR, price_sel)
                if names and prices:
                    for n, p in zip(names, prices):
                        name = clean_name(n.text)
                        odds = clean_odds(p.text)
                        if name and odds and len(name) > 3:
                            results.append({'player': name, 'odds_decimal': odds, 'bookie': 'Pointsbet'})
                    if results: break
            except: continue
        
        if not results:
            source = driver.page_source
            matches = re.findall(r'"fixedPrice":([\d.]+).*?"outcomeName":"([^"]+)"', source)
            for price, name in matches:
                odds = float(price)
                if odds > 1.0 and len(name) > 3:
                    results.append({'player': clean_name(name), 'odds_decimal': odds, 'bookie': 'Pointsbet'})
        
        print(f"    {'✓' if results else '⚠'} {len(results)} odds found")
    except Exception as e:
        print(f"    ✗ Error: {e}")
    return results

# ── Bet365 ───────────────────────────────────────────────────
def scrape_bet365(driver):
    print("  Scraping Bet365...")
    results = []
    try:
        driver.get("https://www.bet365.com.au/#/AC/B3/C20604709/D20607968/")
        time.sleep(5)
        
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(),'Accept')]")
            btn.click()
            time.sleep(1)
        except: pass
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        
        selectors = [
            (".gl-ParticipantFixedWidth_Name", ".gl-ParticipantFixedWidth_Odds"),
            (".participant-name", ".price"),
            ("[class*='ParticipantName']", "[class*='Odds']"),
            (".name", ".odds"),
        ]
        
        for name_sel, price_sel in selectors:
            try:
                names = driver.find_elements(By.CSS_SELECTOR, name_sel)
                prices = driver.find_elements(By.CSS_SELECTOR, price_sel)
                if names and prices:
                    for n, p in zip(names, prices):
                        name = clean_name(n.text)
                        odds = clean_odds(p.text)
                        if name and odds and len(name) > 3:
                            results.append({'player': name, 'odds_decimal': odds, 'bookie': 'Bet365'})
                    if results: break
            except: continue
        
        print(f"    {'✓' if results else '⚠'} {len(results)} odds found")
    except Exception as e:
        print(f"    ✗ Error: {e}")
    return results

# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("BROWNLOW ODDS SCRAPER (Headless Chrome)")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    print("\nStarting headless Chrome...")
    driver = get_driver()
    
    try:
        scrapers = [
            scrape_sportsbet,
            scrape_tab,
            scrape_ladbrokes,
            scrape_pointsbet,
            scrape_bet365,
        ]
        
        for scraper in scrapers:
            results = scraper(driver)
            all_odds.extend(results)
            time.sleep(2)
    
    finally:
        driver.quit()
        print("\nBrowser closed.")
    
    if all_odds:
        df = pd.DataFrame(all_odds)
        df = df[df['odds_decimal'] > 1.0].copy()
        df['implied_prob'] = (100 / df['odds_decimal']).round(2)
        df['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        df.to_csv("data_2026/bookmaker_odds.csv", index=False)
        print(f"\n✓ Saved {len(df)} odds to data_2026/bookmaker_odds.csv")
        
        # Best odds per player across all bookies
        best = df.groupby('player')['odds_decimal'].max().reset_index()
        best.columns = ['player', 'best_odds']
        best['implied_prob'] = (100 / best['best_odds']).round(2)
        best['bookie'] = df.groupby('player').apply(
            lambda x: x.loc[x['odds_decimal'].idxmax(), 'bookie']
        ).values
        best = best.sort_values('best_odds')
        best.to_csv("data_2026/best_odds.csv", index=False)
        
        print(f"✓ Best odds saved to data_2026/best_odds.csv")
        print(f"\nTop 15 by market price:")
        print(best.head(15).to_string(index=False))
    else:
        print("\n⚠ No odds scraped.")
        print("Bookmakers may have changed their page structure.")
        print("Use manual entry in the dashboard Value Finder instead.")
        
        # Create template
        template = pd.DataFrame({
            'player': ['Nick Daicos','Marcus Bontempelli','Zak Butters',
                      'Bailey Smith','Lachie Neale','Christian Petracca'],
            'odds_decimal': [3.25, 6.0, 10.0, 7.0, 12.0, 8.0],
            'implied_prob': [30.8, 16.7, 10.0, 14.3, 8.3, 12.5],
            'bookie': ['Manual']*6,
            'scraped_at': [datetime.now().strftime('%Y-%m-%d %H:%M')]*6
        })
        template.to_csv("data_2026/bookmaker_odds.csv", index=False)
        template.rename(columns={'player':'player','odds_decimal':'best_odds'})\
            [['player','best_odds','implied_prob']]\
            .to_csv("data_2026/best_odds.csv", index=False)
        print("✓ Template odds file created — edit data_2026/bookmaker_odds.csv manually")

print("\nDone.")
