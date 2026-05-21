"""
Brownlow Odds Scraper — Oddschecker
Scrapes multi-bookmaker Brownlow winner odds from Oddschecker's comparison table.
Output: data_2026/bookmaker_odds.csv  (wide: Player | Bookie1 | Bookie2 | …)
        data_2026/best_odds.csv       (long: player, best_odds, implied_prob, best_bookie)
Uses playwright instead of undetected-chromedriver for more reliable anti-bot evasion.
"""

import os
import re
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

os.makedirs("data_2026", exist_ok=True)

DEBUG = False  # When True: save page source to oddschecker_debug.html and exit

URL = "https://www.oddschecker.com/australian-rules/afl/afl-brownlow-medal/winner"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Injected into every page to mask automation fingerprint
_STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver',  {get: () => undefined});
    Object.defineProperty(navigator, 'plugins',    {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages',  {get: () => ['en-AU', 'en']});
    Object.defineProperty(navigator, 'platform',   {get: () => 'Win32'});
    window.chrome = {runtime: {}};
"""


def _new_context(pw):
    """Launch Chromium with stealth settings; return (browser, page)."""
    browser = pw.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
        ],
    )
    ctx = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        locale='en-AU',
        timezone_id='Australia/Melbourne',
        user_agent=_UA,
        extra_http_headers={
            'Accept-Language': 'en-AU,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        },
    )
    ctx.add_init_script(_STEALTH_JS)
    page = ctx.new_page()
    return browser, page


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


def _dismiss_overlays(page):
    """Click cookie / consent banners if present."""
    for sel in [
        '#onetrust-accept-btn-handler',
        'button:text-matches("accept all", "i")',
        'button:text-matches("accept cookies", "i")',
        'button:text-matches("^accept$", "i")',
        'button[aria-label="Close"]',
    ]:
        try:
            page.locator(sel).first.click(timeout=3000)
            page.wait_for_timeout(800)
            return
        except Exception:
            continue


def scrape_oddschecker(page) -> pd.DataFrame:
    print(f"  Loading: {URL}")
    page.goto(URL, wait_until='domcontentloaded', timeout=30000)

    # Wait for odds table — try progressively broader selectors
    for sel in ["tr[data-bname]", "tbody#t1", "table.eventTable", ".bc", "table"]:
        try:
            page.wait_for_selector(sel, timeout=15000)
            print(f"  Page ready (matched '{sel}')")
            break
        except PlaywrightTimeout:
            continue
    else:
        print("  Warning: timed out waiting for table — continuing with current state")

    # Let bookmaker columns finish rendering
    page.wait_for_timeout(6000)

    if DEBUG:
        with open("oddschecker_debug.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("  DEBUG: page source saved to oddschecker_debug.html — exiting.")
        return pd.DataFrame()

    _dismiss_overlays(page)

    # Scroll to trigger lazy-loaded odds columns
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(1000)

    soup = BeautifulSoup(page.content(), "html.parser")

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


# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=" * 60)
    print("BROWNLOW ODDS SCRAPER — ODDSCHECKER")
    print(f"Run time: {now}")
    print("=" * 60)

    print("\nStarting browser (playwright/chromium)...")
    with sync_playwright() as pw:
        browser, page = _new_context(pw)
        try:
            df = scrape_oddschecker(page)
        finally:
            browser.close()
            print("Browser closed.\n")

    if df.empty:
        print("No odds found — the page may have blocked the scraper.")
        print("Set DEBUG=True to inspect the captured HTML.")
    else:
        bookie_cols = [c for c in df.columns if c != "Player"]
        n_players = len(df)
        n_bookies = len(bookie_cols)

        # ── Wide-format CSV ──────────────────────────────────────
        df.to_csv("data_2026/bookmaker_odds.csv", index=False)

        # ── Best-odds CSV (dashboard compat) ─────────────────────
        best_rows = []
        for _, row in df.iterrows():
            vals = {b: row[b] for b in bookie_cols if pd.notna(row.get(b))}
            if not vals:
                continue
            best_bookie = max(vals, key=vals.get)
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

        print(f"Players found   : {n_players}")
        print(f"Bookmakers found: {n_bookies}")
        print(f"Bookmakers      : {', '.join(bookie_cols)}")
        print(f"\nSaved -> data_2026/bookmaker_odds.csv  ({n_players} players × {n_bookies} bookmakers)")
        print(f"Saved -> data_2026/best_odds.csv")
        print(f"\nTop 15 shortest-priced (best odds available):")
        print(best_df.head(15).to_string(index=False))

    print("\nDone.")
