"""Standalone Betfair Brownlow predictor scraper.
Tries plain requests first; falls back to Playwright if the page needs JS rendering.
Saves to data_2026/betfair_predictions.csv (+ _prev backup).
"""

import os
import shutil
import pandas as pd
from io import StringIO

_BF_URL = 'https://www.betfair.com.au/hub/sports/afl/brownlow-medal-predictor/'
_BF_CSV = 'data_2026/betfair_predictions.csv'

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


def _pw_get_html(url, wait_for=None, extra_sleep_ms=4000, timeout_ms=30000):
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
            html = page.content()
        except Exception:
            pass
        finally:
            browser.close()
    return html


def _parse_html(html_text):
    raw = pd.read_html(StringIO(html_text))
    if not raw:
        raise ValueError('No tables found on page')
    combined = pd.concat(raw, ignore_index=True)
    combined.columns = ['Player', 'Votes']
    combined = combined.dropna(subset=['Votes'])
    combined['Votes'] = pd.to_numeric(combined['Votes'], errors='coerce')
    combined = combined.dropna(subset=['Votes'])
    combined['Player'] = combined['Player'].astype(str).str.title().str.strip()
    combined = combined[combined['Player'].str.contains(' ', na=False)]
    agg = (
        combined.groupby('Player', as_index=False)['Votes'].sum()
        .sort_values('Votes', ascending=False).reset_index(drop=True)
    )
    if agg.empty:
        raise ValueError('No vote rows after filtering')
    df = agg.rename(columns={'Votes': 'Total_Votes'})
    df['Rank'] = df.index + 1
    return df


def fetch():
    # Attempt 1: plain requests (fast)
    try:
        import requests
        resp = requests.get(
            _BF_URL,
            headers={
                'User-Agent': _UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-AU,en;q=0.9',
                'Referer': 'https://www.betfair.com.au/',
            },
            timeout=20,
        )
        resp.raise_for_status()
        df = _parse_html(resp.text)
        _save_with_backup(df, _BF_CSV)
        print(f"[Betfair] OK ({len(df)} players via requests)")
        print(df.head(10).to_string(index=False))
        return True
    except Exception as e:
        print(f"[Betfair] requests failed ({e}), trying Playwright...")

    # Attempt 2: Playwright
    try:
        html = _pw_get_html(_BF_URL, wait_for=['table', 'article', 'main'])
        if not html:
            raise ValueError('Playwright returned empty page')
        df = _parse_html(html)
        _save_with_backup(df, _BF_CSV)
        print(f"[Betfair] OK ({len(df)} players via Playwright)")
        print(df.head(10).to_string(index=False))
        return True
    except Exception as e:
        print(f"[Betfair] FAILED: {e}")
        if os.path.exists(_BF_CSV):
            print("[Betfair] Using existing cached CSV (unchanged)")
        return False


if __name__ == '__main__':
    fetch()
