"""Standalone Betfair Brownlow predictor scraper.
Uses Playwright so the AG Grid leaderboard renders (plain requests can't see it).
Leaderboard order used as tie-breaker when vote totals are equal.
Saves to data_2026/betfair_predictions.csv (+ _prev backup).
"""

import os
import re
import shutil
import pandas as pd
from bs4 import BeautifulSoup

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

# Normalise unicode dashes/hyphens (en-dash, em-dash, minus-sign etc.) → ASCII hyphen
_DASH_RE = re.compile(r'[‐-―−﹘﹣－­–—]')


def _save_with_backup(df, csv_path):
    _prev = csv_path.replace('.csv', '_prev.csv')
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    if os.path.exists(csv_path):
        shutil.copy2(csv_path, _prev)
    df.to_csv(csv_path, index=False)


def _clean_name(raw):
    """Title-case, normalise dashes/spaces-around-dashes, require at least 2 words."""
    name = _DASH_RE.sub('-', raw).title().strip()
    name = re.sub(r'\s*-\s*', '-', name)  # "X - Y" → "X-Y"
    if len(name.split()) < 2:
        return None
    return name


def _pw_get_html(url, wait_selector=None, extra_sleep_ms=6000, timeout_ms=30000):
    from playwright.sync_api import sync_playwright, TimeoutError as _PWT
    html = ''
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox',
                  '--disable-blink-features=AutomationControlled',
                  '--disable-dev-shm-usage'],
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
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=15000)
                except _PWT:
                    pass
            page.wait_for_timeout(extra_sleep_ms)
            html = page.content()
        except Exception:
            pass
        finally:
            browser.close()
    return html


def _parse_leaderboard_order(soup):
    """Extract player rank order from the Betfair AG Grid widget.

    The AG Grid renders up to ~31 visible rows in the DOM. That's enough for
    tie-breaking purposes — lower-ranked players keep position 9999.
    Returns dict {clean_name: position (1-based)}.
    """
    lb_order = {}
    widget = soup.find(class_='brownlow-container')
    if not widget:
        return lb_order
    player_rows = []
    for row in widget.find_all('div', class_='ag-row'):
        # Only rows in the left-pinned player-name pane have a col-id="0" cell
        name_cell = row.find('div', attrs={'col-id': '0'})
        if name_cell:
            try:
                idx = int(row.get('row-index', 9999))
            except (ValueError, TypeError):
                idx = 9999
            name = _clean_name(name_cell.get_text(strip=True))
            if name:
                player_rows.append((idx, name))
    player_rows.sort(key=lambda x: x[0])
    for pos, (_, name) in enumerate(player_rows, start=1):
        lb_order[name] = pos
    return lb_order


def _parse_votes(soup):
    """Parse per-game vote rows from Betfair's ALL-CAPS HTML table structure."""
    votes = {}
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2:
            continue
        raw_player = cells[0].get_text(strip=True)
        raw_vote = cells[1].get_text(strip=True)
        try:
            vote = float(raw_vote)
        except ValueError:
            continue
        if not (0 < vote <= 3):
            continue
        name = _clean_name(raw_player)
        if not name:
            continue
        votes[name] = votes.get(name, 0) + vote
    return votes


def fetch():
    try:
        print('[Betfair] Fetching page via Playwright...')
        html = _pw_get_html(
            _BF_URL,
            wait_selector='.ag-row',
            extra_sleep_ms=6000,
        )
        if not html:
            raise ValueError('Playwright returned empty page')

        soup = BeautifulSoup(html, 'html.parser')

        lb_order = _parse_leaderboard_order(soup)
        print(f'[Betfair] Leaderboard order: {len(lb_order)} players found')
        if lb_order:
            top5 = sorted(lb_order.items(), key=lambda x: x[1])[:5]
            print(f'[Betfair] Top 5 from leaderboard: {top5}')

        votes = _parse_votes(soup)
        if not votes:
            raise ValueError('No vote rows found in Betfair page')

        df = pd.DataFrame([{'Player': n, 'Total_Votes': v} for n, v in votes.items()])
        def _lb_pos(name):
            # Try exact match first, then hyphen-free fallback
            # (AG Grid may use space where tr/td uses hyphen, e.g. "Luke Davies Uniacke")
            return lb_order.get(name, lb_order.get(name.replace('-', ' '), 9999))

        df['_lb_pos'] = df['Player'].map(_lb_pos)
        df = df.sort_values(['Total_Votes', '_lb_pos'], ascending=[False, True])
        df = df.drop(columns='_lb_pos').reset_index(drop=True)
        df['Rank'] = df.index + 1

        _save_with_backup(df, _BF_CSV)
        print(f'[Betfair] OK ({len(df)} players)')
        print(df.head(10).to_string(index=False))
        return True

    except Exception as e:
        print(f'[Betfair] FAILED: {e}')
        if os.path.exists(_BF_CSV):
            print('[Betfair] Using existing cached CSV (unchanged)')
        return False


if __name__ == '__main__':
    fetch()
