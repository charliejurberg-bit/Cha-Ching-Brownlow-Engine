"""Standalone Betfair Brownlow predictor scraper.
Page uses HTML tables: player name in col 0, vote (1/2/3) in col 1.
Plain requests is sufficient — no Playwright needed.
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

# Normalise unicode dashes/hyphens (en-dash, em-dash, etc.) → regular hyphen
_DASH_RE = re.compile(r'[‐-―−﹘﹣－­–—]')


def _save_with_backup(df, csv_path):
    _prev = csv_path.replace('.csv', '_prev.csv')
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    if os.path.exists(csv_path):
        shutil.copy2(csv_path, _prev)
    df.to_csv(csv_path, index=False)


def _clean_name(raw):
    """Title-case, normalise dashes, require at least 2 words."""
    name = _DASH_RE.sub('-', raw).title().strip()
    if len(name.split()) < 2:
        return None
    return name


def _parse_html(html_text):
    """Parse player-vote rows from Betfair's HTML table structure."""
    soup = BeautifulSoup(html_text, 'html.parser')
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

    if not votes:
        raise ValueError('No vote rows found in page tables')

    df = (
        pd.DataFrame([{'Player': n, 'Total_Votes': v} for n, v in votes.items()])
        .sort_values('Total_Votes', ascending=False)
        .reset_index(drop=True)
    )
    df['Rank'] = df.index + 1
    return df


def fetch():
    import requests
    try:
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
        print(f"[Betfair] OK ({len(df)} players)")
        print(df.head(10).to_string(index=False))
        return True
    except Exception as e:
        print(f"[Betfair] FAILED: {e}")
        if os.path.exists(_BF_CSV):
            print("[Betfair] Existing cached CSV unchanged")
        return False


if __name__ == '__main__':
    fetch()
