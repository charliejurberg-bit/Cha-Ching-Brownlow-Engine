"""Standalone ESPN Brownlow predictor scraper.
Uses Playwright with scrolling to reveal lazy-loaded per-game vote sections.
Saves to data_2026/espn_predictions.csv (+ _prev backup).
"""

import os
import re
import shutil
import pandas as pd
from io import StringIO

_ESPN_URL = (
    "https://www.espn.com.au/afl/story/_/page/POINTSBET20242/"
    "afl-2026-brownlow-medal-predictor-tracker-leaderboard-odds-every-vote"
)
_ESPN_CSV = 'data_2026/espn_predictions.csv'

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver',  {get: () => undefined});
    Object.defineProperty(navigator, 'plugins',    {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages',  {get: () => ['en-AU', 'en']});
    Object.defineProperty(navigator, 'platform',   {get: () => 'Win32'});
    window.chrome = {runtime: {}};
"""


def _save_with_backup(df, csv_path):
    _prev = csv_path.replace('.csv', '_prev.csv')
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    if os.path.exists(csv_path):
        shutil.copy2(csv_path, _prev)
    df.to_csv(csv_path, index=False)


def _pw_get_html(url, wait_for=None, scroll=False, extra_sleep_ms=6000, timeout_ms=30000):
    from playwright.sync_api import sync_playwright, TimeoutError as _PWT
    html = ''
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox',
                  '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage'],
        )
        ctx = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='en-AU',
            timezone_id='Australia/Melbourne',
            user_agent=_UA,
            extra_http_headers={
                'Accept-Language': 'en-AU,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
        )
        ctx.add_init_script(_STEALTH_JS)
        page = ctx.new_page()
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
            if wait_for:
                sels = [wait_for] if isinstance(wait_for, str) else wait_for
                for s in sels:
                    try:
                        page.wait_for_selector(s, timeout=15000)
                        break
                    except _PWT:
                        continue
            page.wait_for_timeout(extra_sleep_ms)
            if scroll:
                for pos in range(0, 25000, 600):
                    page.evaluate(f"window.scrollTo(0, {pos})")
                    page.wait_for_timeout(200)
                page.wait_for_timeout(extra_sleep_ms)
            html = page.content()
        except Exception:
            pass
        finally:
            browser.close()
    return html


def _parse_votes(html_text):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text(" ", strip=True)
    votes = {}

    # Strategy A: "N - Player (TEAM)[, Player (TEAM), ...]"
    # Each vote block can list multiple players at the same vote level (comma-separated).
    vote_block_re = re.compile(
        r"(\d+\.?\d*)\s*[-–—]\s*"
        r"((?:[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)+\s*\([A-Z]{1,4}\)(?:\s*,\s*)?)+)"
    )
    player_re = re.compile(
        r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)+)\s*\([A-Z]{1,4}\)"
    )
    for m in vote_block_re.finditer(text):
        try:
            val = float(m.group(1))
        except ValueError:
            continue
        if not (0 < val <= 3):
            continue
        for pm in player_re.finditer(m.group(2)):
            name = pm.group(1).title().strip()
            votes[name] = votes.get(name, 0) + val

    # Strategy B: table scan for per-round vote columns
    if not votes:
        try:
            raw_tables = pd.read_html(StringIO(html_text))
        except Exception:
            raw_tables = []
        for tdf in raw_tables:
            tdf.columns = [str(c).strip().upper() for c in tdf.columns]
            if 'PLAYER' not in tdf.columns:
                continue
            vote_cols = []
            for c in tdf.columns:
                if c in ('PLAYER', 'TEAM', 'VOTES'):
                    continue
                num = pd.to_numeric(tdf[c], errors='coerce')
                valid = num.dropna()
                if len(valid) > 0 and float(valid.max()) <= 3.0 and float(valid.min()) >= 0.0:
                    vote_cols.append(c)
            if not vote_cols:
                continue
            tdf_v = tdf[['PLAYER'] + vote_cols].copy()
            for c in vote_cols:
                tdf_v[c] = pd.to_numeric(tdf_v[c], errors='coerce').fillna(0)
            tdf_v['_total'] = tdf_v[vote_cols].sum(axis=1)
            for _, row in tdf_v.iterrows():
                player = str(row['PLAYER']).title().strip()
                if not player or player in ('Nan', '') or row['_total'] <= 0:
                    continue
                votes[player] = votes.get(player, 0) + float(row['_total'])

    return votes


def fetch():
    try:
        html = _pw_get_html(
            _ESPN_URL,
            wait_for=['article', 'main', 'body'],
            scroll=True,
        )
        if not html:
            raise ValueError('Playwright returned empty page')

        votes = _parse_votes(html)
        if not votes:
            raise ValueError('No vote data found on ESPN page')

        df = (
            pd.DataFrame([{'Player': n, 'Total_Votes': v} for n, v in votes.items()])
            .sort_values('Total_Votes', ascending=False)
            .reset_index(drop=True)
        )
        df['Rank'] = df.index + 1
        _save_with_backup(df, _ESPN_CSV)

        print(f"[ESPN] OK ({len(df)} players)")
        print(df.head(10).to_string(index=False))
        return True

    except Exception as e:
        print(f"[ESPN] FAILED: {e}")
        if os.path.exists(_ESPN_CSV):
            print("[ESPN] Using existing cached CSV (unchanged)")
        return False


if __name__ == '__main__':
    fetch()
