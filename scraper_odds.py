"""
Brownlow Odds Scraper — Oddschecker
Scrapes multi-bookmaker Brownlow winner odds from Oddschecker's comparison table.
Output: data_2026/bookmaker_odds.csv  (wide: Player | Bookie1 | Bookie2 | …)
        data_2026/best_odds.csv       (long: player, best_odds, implied_prob, best_bookie, scraped_at)

Both of the above are rewritten in full on every run. Two append-only archives
sit alongside them so the odds history survives:
        data_2026/best_odds_history.csv       (best_odds.csv schema, one block per run)
        data_2026/bookmaker_odds_history.csv  (long: player, bookie, odds, scraped_at)

The bookmaker archive is long-format on purpose: the wide frame's bookmaker
columns vary run to run, so it cannot be appended to safely. Each append is
keyed on scraped_at, so re-running the scraper without a fresh scrape is a
no-op rather than a duplicate block.
"""

import os
import re
import time
from datetime import datetime

import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

os.makedirs("data_2026", exist_ok=True)

DEBUG = False  # When True: save page source to oddschecker_debug.html and exit

URL = "https://www.oddschecker.com/australian-rules/afl/afl-brownlow-medal/winner"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _chrome_major_version() -> int | None:
    """Read the installed Chrome major version from the Windows registry."""
    try:
        import subprocess
        for key in [
            r"HKLM\Software\Google\Chrome\BLBeacon",
            r"HKCU\Software\Google\Chrome\BLBeacon",
            r"HKLM\Software\Wow6432Node\Google\Chrome\BLBeacon",
        ]:
            r = subprocess.run(
                ["reg", "query", key, "/v", "version"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                ver = r.stdout.strip().split()[-1]
                return int(ver.split(".")[0])
    except Exception:
        pass
    return None


def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-AU")
    options.add_argument(f"--user-agent={BROWSER_UA}")
    version_main = _chrome_major_version()
    if version_main:
        print(f"  Detected Chrome {version_main} — requesting matching ChromeDriver")
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=version_main)
    return driver


def parse_odds(text: str) -> float | None:
    """Convert fractional ('5/1'), decimal ('6.00'), or 'EVS' to decimal float."""
    text = str(text).strip()
    if not text or text.upper() in {"SP", "N/A", "-", "", "SUSP"}:
        return None
    if text.upper() in {"EVS", "EVENS"}:
        return 2.0
    m = re.match(r"^(\d+)/(\d+)$", text)
    if m:
        return round(int(m.group(1)) / int(m.group(2)) + 1, 2)
    try:
        v = float(text)
        return v if v > 1.0 else None
    except (ValueError, TypeError):
        return None


def dismiss_overlays(driver):
    xpaths = [
        "//*[@id='onetrust-accept-btn-handler']",
        "//button[contains(translate(., 'ACCEPT ALL', 'accept all'), 'accept all')]",
        "//button[contains(translate(., 'ACCEPT COOKIES', 'accept cookies'), 'accept cookies')]",
        "//button[contains(translate(., 'ACCEPT', 'accept'), 'accept')]",
        "//button[@aria-label='Close']",
    ]
    for xpath in xpaths:
        try:
            btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            btn.click()
            time.sleep(1)
            return
        except Exception:
            continue


def scrape_oddschecker(driver) -> pd.DataFrame:
    print(f"  Loading: {URL}")
    driver.get(URL)

    # Wait for odds rows — try progressively broader selectors
    for sel in ["tr[data-bname]", "tbody#t1", "table.eventTable", ".bc", "table"]:
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
            print(f"  Page ready (matched '{sel}')")
            break
        except Exception:
            continue
    else:
        print("  Warning: timed out waiting for table")

    time.sleep(6)  # Let all bookmaker columns finish rendering

    if DEBUG:
        with open("oddschecker_debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("  DEBUG: page source saved to oddschecker_debug.html — exiting.")
        return pd.DataFrame()

    dismiss_overlays(driver)

    # Scroll to trigger any lazy-loaded odds
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    html = driver.page_source

    soup = BeautifulSoup(html, "html.parser")

    # ── Locate the odds table ────────────────────────────────────
    table = (
        soup.find("table", id="ew_bookie_content")
        or soup.find("table", attrs={"data-mid": True})
        or soup.find("table", class_=re.compile(r"eventTable|comparison|odds", re.I))
        or soup.find("table")
    )

    if not table:
        print("  Error: no <table> found in page")
        return pd.DataFrame()

    # ── Build bk_code → bookmaker name from header area ─────────
    # data-bk lives on <span>/<a> elements inside thead <td>s, not on <th>s.
    bk_names: dict[str, str] = {}
    search_zone = table.find("thead") or table
    for el in search_zone.find_all(attrs={"data-bk": True}):
        bk = el.get("data-bk", "").strip()
        if not bk or bk in bk_names:
            continue
        img = el.find("img")
        if img is None and el.parent:
            img = el.parent.find("img")
        name = (img.get("alt", "").strip() if img else "") or bk
        bk_names[bk] = re.sub(r"\s{2,}", " ", name).strip() or bk

    if not bk_names:
        print("  Error: no bookmaker columns found (no data-bk attributes in header)")
        return pd.DataFrame()

    print(f"  Bookmakers found: {len(bk_names)}")

    # ── Extract player rows ──────────────────────────────────────
    rows: list[dict] = []
    seen_players: set[str] = set()

    # Player rows carry data-bname on the <tr>; search the whole document
    # rather than a specific tbody since ew_bookie_content may split headers/rows.
    for tr in soup.find_all("tr", attrs={"data-bname": True}):
        # Player name lives on data-bname of the <tr>, or data-name of a child <a>
        player = tr.get("data-bname", "").strip()
        if not player:
            a_el = tr.find("a", attrs={"data-name": True})
            if a_el:
                player = a_el.get("data-name", "").strip()
        if (
            not player
            or len(player) < 4
            or not re.search(r"[A-Za-z]{2,}\s[A-Za-z]{2,}", player)
            or any(c.isdigit() for c in player)
            or player in seen_players
        ):
            continue

        seen_players.add(player)
        row: dict = {"Player": player}

        # Odds are on <td data-bk> elements; data-odig holds the decimal value
        for td in tr.find_all("td", attrs={"data-bk": True}):
            bk = td.get("data-bk", "").strip()
            if not bk:
                continue
            bookie = bk_names.get(bk, bk)
            odds_str = td.get("data-odig") or td.get("data-o") or ""
            v = parse_odds(odds_str)
            if v is not None:
                row[bookie] = v

        if len(row) > 1:  # at least one bookmaker price
            rows.append(row)

    return pd.DataFrame(rows)


def _append_history(df, hist_path):
    """Append df to hist_path, writing the header only on first creation.
    Skips the append if the newest scraped_at already present in the file
    matches the newest scraped_at in df."""
    os.makedirs(os.path.dirname(hist_path) or ".", exist_ok=True)

    # Dedupe on scraped_at so a re-run against an unchanged scrape is a no-op.
    # Only the timestamp column is read — the archive grows all season and
    # there is no reason to parse the rest of it.
    try:
        if os.path.exists(hist_path):
            prev = pd.read_csv(hist_path, usecols=["scraped_at"])
            if not prev.empty and prev["scraped_at"].max() == df["scraped_at"].max():
                print(f"  Skipped -> {hist_path} (already holds {df['scraped_at'].max()})")
                return
    except Exception as e:
        # A truncated or malformed archive must never abort the scrape; fall
        # through and append, and let the duplicate be sorted out downstream.
        print(f"  Warning: could not read {hist_path} ({e}) — appending anyway")

    df.to_csv(hist_path, mode="a", index=False, header=not os.path.exists(hist_path))
    print(f"Saved -> {hist_path}  (+{len(df)} rows)")


# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=" * 60)
    print("BROWNLOW ODDS SCRAPER — ODDSCHECKER")
    print(f"Run time: {now}")
    print("=" * 60)

    print("\nStarting browser (undetected-chromedriver)...")
    driver = get_driver()
    try:
        df = scrape_oddschecker(driver)
    finally:
        driver.quit()
        print("Browser closed.\n")

    if df.empty:
        print("No odds found — the page may have blocked the scraper.")
        print("Try running without --headless or check if the market is listed.")
    else:
        bookie_cols = [c for c in df.columns if c != "Player"]
        n_players = len(df)
        n_bookies = len(bookie_cols)

        # ── Wide-format CSV ──────────────────────────────────────
        df.to_csv("data_2026/bookmaker_odds.csv", index=False)

        # Archive it long-format: the wide frame's bookmaker columns depend on
        # what Oddschecker rendered that run, so appending it as-is would go
        # ragged the first time a bookie drops off the page.
        long_df = (
            df.melt(id_vars="Player", var_name="bookie", value_name="odds")
              .dropna(subset=["odds"])
              .rename(columns={"Player": "player"})
        )
        long_df["scraped_at"] = now
        long_df = long_df[["player", "bookie", "odds", "scraped_at"]]
        _append_history(long_df, "data_2026/bookmaker_odds_history.csv")

        # ── Best-odds CSV (dashboard compat) ─────────────────────
        # Filter Betfair prices below 1.5 — those are lay prices, not back prices.
        # In a winner market with 100+ runners, no legitimate back price is < 1.5.
        BETFAIR_MIN_BACK = 1.5
        best_rows = []
        for _, row in df.iterrows():
            vals = {}
            for b in bookie_cols:
                v = row.get(b)
                if pd.notna(v):
                    if "betfair" in b.lower() and v < BETFAIR_MIN_BACK:
                        continue  # lay price — skip
                    vals[b] = v
            if not vals:
                continue
            best_bookie = max(vals, key=vals.get)   # highest decimal = best payout
            best_price = vals[best_bookie]
            best_rows.append({
                "player": row["Player"],
                "best_odds": best_price,
                "implied_prob": round(100 / best_price, 2),
                "best_bookie": best_bookie,
                "scraped_at": now,
            })

        best_df = (
            pd.DataFrame(best_rows)
            .sort_values("best_odds")
            .reset_index(drop=True)
        )
        best_df.to_csv("data_2026/best_odds.csv", index=False)
        _append_history(best_df, "data_2026/best_odds_history.csv")

        # ── Summary ──────────────────────────────────────────────
        print(f"Players found  : {n_players}")
        print(f"Bookmakers found: {n_bookies}")
        print(f"Bookmakers     : {', '.join(bookie_cols)}")
        print(f"\nSaved -> data_2026/bookmaker_odds.csv  ({n_players} players x {n_bookies} bookmakers)")
        print(f"Saved -> data_2026/best_odds.csv")

        print(f"\nTop 15 shortest-priced (best odds available):")
        print(best_df.head(15).to_string(index=False))

print("\nDone.")
