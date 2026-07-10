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
_ESPN_ROUND_CSV = 'data_2026/espn_round_votes.csv'

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

    # Step 1: read ESPN's official leaderboard table for tie-break ordering.
    # The table only covers the top ~17 players but its row order is authoritative.
    lb_order: dict[str, int] = {}
    lb_h2 = soup.find('h2', string=lambda s: s and 'LEADERBOARD' in s.upper())
    if lb_h2:
        lb_table = lb_h2.find_next('table')
        if lb_table:
            tbody = lb_table.find('tbody')
            if tbody:
                for pos, row in enumerate(tbody.find_all('tr'), start=1):
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        player_name = cells[1].get_text(strip=True).title().strip()
                        lb_order[player_name] = pos

    # Step 2: accumulate votes from per-game text — "N - Player (TEAM)[, Player (TEAM), ...]"
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

    return votes, lb_order


# Round headings and per-game vote lines in the ESPN predictor prose.
_ROUND_HDR_RE = re.compile(r'^(OPENING ROUND|ROUND (\d{1,2}))$', re.M)
_ROUND_VOTE_RE = re.compile(
    r"(\d+\.?\d*)\s*[-–—]\s*"
    r"((?:[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)+\s*\([A-Z]{1,4}\)(?:\s*,\s*)?)+)"
)
_ROUND_PLAYER_RE = re.compile(
    r"([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)+)\s*\([A-Z]{1,4}\)"
)


def _parse_round_votes(html_text):
    """Extract ESPN's per-round predictor votes → list of {Player, Round, Vote}.

    Round numbers use the AFL DISPLAY convention (Opening Round = 0, Round N = N),
    matching afl_predictor_round_votes.csv / betfair_round_votes.csv and the
    Polls-a-Vote consumer's My_Rounds picks — NOT raw AFLTables Round_num.

    ESPN's predictor publishes a fractional 3-2-1 spread per game (values like
    2.5 / 1.5 / 1 / 0.5, sometimes a value split across two players). Votes are
    stored AS-IS (float, unrounded) to preserve the weighting. Only named
    vote-getters appear; players who scored 0 are absent, which the round-verdict
    consumer reads as disagreement within a covered round (not silence).

    Article structure: rounds are <h2> headings 'OPENING ROUND' / 'ROUND N'; games
    within a round carry a 'TEAM (score) def.[ by] TEAM (score)' header and then
    the vote lines 'VALUE - Player (TEAM)[, Player (TEAM)]'.

    Raises ValueError if the expected round/vote structure is not found, so the
    caller can fail loudly and leave the existing CSV untouched.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text("\n", strip=True)

    marks = [(m.start(), m.end(),
              0 if m.group(1) == 'OPENING ROUND' else int(m.group(2)))
             for m in _ROUND_HDR_RE.finditer(text)]
    if not marks:
        raise ValueError(
            "ESPN round parse: no round headings (OPENING ROUND / ROUND N) found — "
            "article structure may have changed")

    rows = []
    for i, (_s, e, disp) in enumerate(marks):
        nxt = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        block = text[e:nxt]
        for vm in _ROUND_VOTE_RE.finditer(block):
            try:
                val = float(vm.group(1))
            except ValueError:
                continue
            if not (0 < val <= 3):
                continue
            for pm in _ROUND_PLAYER_RE.finditer(vm.group(2)):
                rows.append({'Player': pm.group(1).title().strip(),
                             'Round': disp, 'Vote': val})

    if not rows:
        raise ValueError(
            "ESPN round parse: round headings found but no per-game vote lines "
            "matched — article structure may have changed")
    return rows


def fetch():
    try:
        html = _pw_get_html(
            _ESPN_URL,
            wait_for=['article', 'main', 'body'],
            scroll=True,
        )
        if not html:
            raise ValueError('Playwright returned empty page')

        votes, lb_order = _parse_votes(html)
        if not votes:
            raise ValueError('No vote data found on ESPN page')

        df = pd.DataFrame([{'Player': n, 'Total_Votes': v} for n, v in votes.items()])
        # Sort: total votes descending, then by ESPN leaderboard position for ties
        # (players not in leaderboard table get position 9999)
        df['_lb_pos'] = df['Player'].map(lambda n: lb_order.get(n, 9999))
        df = df.sort_values(['Total_Votes', '_lb_pos'], ascending=[False, True])
        df = df.drop(columns='_lb_pos').reset_index(drop=True)
        df['Rank'] = df.index + 1
        _save_with_backup(df, _ESPN_CSV)

        print(f"[ESPN] OK ({len(df)} players)")
        print(df.head(10).to_string(index=False))

        # ── Per-round votes (same fetch; independent of the season output) ──
        # Fail loud on a structure mismatch and keep the existing CSV rather than
        # writing a partial/garbage file over good data.
        try:
            round_rows = _parse_round_votes(html)
            rdf = (pd.DataFrame(round_rows)
                   .sort_values(['Player', 'Round']).reset_index(drop=True))
            _save_with_backup(rdf, _ESPN_ROUND_CSV)
            polled = int((rdf['Vote'] >= 0.5).sum())
            print(f"[ESPN] round-level votes: {len(rdf)} rows "
                  f"({rdf['Round'].nunique()} rounds, {polled} with a vote) -> {_ESPN_ROUND_CSV}")
        except Exception as round_err:
            print(f"[ESPN] round parse FAILED: {round_err}")
            if os.path.exists(_ESPN_ROUND_CSV):
                print(f"[ESPN] Keeping existing {_ESPN_ROUND_CSV} (unchanged)")

        return True

    except Exception as e:
        print(f"[ESPN] FAILED: {e}")
        if os.path.exists(_ESPN_CSV):
            print("[ESPN] Using existing cached CSV (unchanged)")
        return False


if __name__ == '__main__':
    fetch()
