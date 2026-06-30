"""Standalone Betfair Brownlow predictor scraper.

Pulls Betfair's published Brownlow vote predictions straight from the JSON
feed that powers their on-site predictor widget — no browser, no AG-Grid
HTML scraping (which silently misparsed and went stale). The widget reads the
active season from /widgets/brownlow/parameters then calls
/brownlow?year=<season>&widget=brownlow, returning one row per player with a
season-total `total` (the exact number Betfair displays).

Saves to data_2026/betfair_predictions.csv (+ _prev backup).
"""

import os
import shutil
import datetime
import pandas as pd
import requests

_API_BASE = 'https://betfair-data-supplier-prod.herokuapp.com/api'
_BF_CSV = 'data_2026/betfair_predictions.csv'
# Per-round 3-2-1 the season total is built from. Drives the Polls-a-Vote
# round verdict. Rounds are Betfair's native round_number (AFL/display
# convention: 0 = Opening Round), matching the dashboard's My_Rounds picks.
_BF_ROUND_CSV = 'data_2026/betfair_round_votes.csv'

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _save_with_backup(df, csv_path):
    _prev = csv_path.replace('.csv', '_prev.csv')
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    if os.path.exists(csv_path):
        shutil.copy2(csv_path, _prev)
    df.to_csv(csv_path, index=False)


def _resolve_year(sess, timeout):
    """Betfair's widget reads the active season from the parameters endpoint."""
    try:
        pj = sess.get(f'{_API_BASE}/widgets/brownlow/parameters',
                      params={'name': 'general'}, timeout=timeout).json()
        if pj.get('year'):
            return pj['year']
    except Exception:
        pass
    return str(datetime.date.today().year)


def fetch(timeout=30):
    try:
        print('[Betfair] Fetching predictions from JSON API...')
        sess = requests.Session()
        sess.headers.update({'User-Agent': _UA, 'Accept': 'application/json'})

        year = _resolve_year(sess, timeout)
        resp = sess.get(f'{_API_BASE}/brownlow',
                        params={'year': year, 'widget': 'brownlow'}, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        df = pd.DataFrame(payload)
        if df.empty or 'name' not in df.columns or 'total' not in df.columns:
            raise ValueError(f'Unexpected API payload (cols={list(df.columns)[:6]})')

        df['Total_Votes'] = pd.to_numeric(df['total'], errors='coerce').fillna(0.0)
        df['Player'] = df['name'].astype(str).str.title().str.strip()
        if 'team' in df.columns:
            df['Team'] = df['team'].apply(
                lambda t: t.get('name', '') if isinstance(t, dict) else '')
        else:
            df['Team'] = ''
        # Stable sort preserves API order on tied totals, matching Betfair's own
        # leaderboard tie-break (e.g. Cripps ranked above Newcombe, both 17.5).
        df = df.sort_values('Total_Votes', ascending=False, kind='stable').reset_index(drop=True)
        df['Rank'] = df.index + 1
        df = df[['Player', 'Team', 'Total_Votes', 'Rank']]

        _save_with_backup(df, _BF_CSV)
        print(f'[Betfair] OK ({len(df)} players, season {year})')
        print(df.head(10).to_string(index=False))

        # Round-level votes (per-round 3-2-1). Only scored games are kept:
        # bye/dnp and unplayed placeholder rounds (no 'vote' key) are omitted so
        # they read as "no coverage" (NA) in the round verdict, never as a
        # 0-vote disagreement. vote==0 (played, didn't poll) IS kept so it can
        # register as real disagreement.
        round_rows = []
        for rec in payload:
            pname = str(rec.get('name', '')).title().strip()
            if not pname:
                continue
            for v in rec.get('votes') or []:
                if not isinstance(v, dict) or 'vote' not in v:
                    continue
                if str(v.get('bye', '0')) == '1' or str(v.get('dnp', '0')) == '1':
                    continue
                try:
                    rn = int(v['round_number'])
                    vote = float(v['vote'])
                except (TypeError, ValueError, KeyError):
                    continue
                round_rows.append({'Player': pname, 'Round': rn, 'Vote': vote})
        if round_rows:
            rdf = pd.DataFrame(round_rows).sort_values(['Player', 'Round']).reset_index(drop=True)
            _save_with_backup(rdf, _BF_ROUND_CSV)
            print(f'[Betfair] round-level votes: {len(rdf)} rows '
                  f'({rdf["Round"].nunique()} rounds) -> {_BF_ROUND_CSV}')

        return True

    except Exception as e:
        print(f'[Betfair] FAILED: {e}')
        if os.path.exists(_BF_CSV):
            print('[Betfair] Using existing cached CSV (unchanged)')
        return False


if __name__ == '__main__':
    fetch()
