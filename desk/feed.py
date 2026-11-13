"""The AFL's live match feeds, shaped for the desk.

Reuses the token and fixture code in scripts/fetch_match_chains.py (the
x-media-mis-token mint needs Origin, Referer and Content-Length: 0; see that
file). Two token endpoints per match:

    matchItem/<id>          status, venue, score by period
    playerStats/match/<id>  every player's running totals (Champion Data)

playerStats is the live source. Never use matchChains here: it lags the
broadcast by ten disposals or more mid-quarter (CLAUDE.md, "Player stats by
quarter").
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import fetch_match_chains as fmc  # noqa: E402

# Feed stat key -> desk stat key. clearances is nested.
FEED_STATS = {
    'disposals': 'Disposals', 'kicks': 'Kicks', 'handballs': 'Handballs',
    'marks': 'Marks', 'goals': 'Goals', 'tackles': 'Tackles', 'hitouts': 'Hitouts',
    'contestedPossessions': 'Contested Possessions', 'inside50s': 'Inside 50s',
    'rebound50s': 'Rebound 50s', 'contestedMarks': 'Contested Marks',
    'marksInside50': 'Marks Inside 50', 'onePercenters': 'One Percenters',
    'goalAssists': 'Goal Assists', 'bounces': 'Bounces',
    'scoreInvolvements': 'Score Involvements', 'metresGained': 'Metres Gained',
    'intercepts': 'Intercepts', 'tacklesInside50': 'Tackles Inside 50',
}
EXTENDED_STATS = {
    'interceptMarks': 'Intercept Marks', 'groundBallGets': 'Ground Ball Gets',
    'pressureActs': 'Pressure Acts', 'spoils': 'Spoils', 'hitoutsToAdvantage': 'Hitouts To Advantage',
    'effectiveDisposals': 'Effective Disposals', 'scoreLaunches': 'Score Launches',
}

LIVE = {'LIVE', 'IN_PROGRESS'}
DONE = {'CONCLUDED', 'POSTGAME', 'COMPLETED', 'FINAL'}

# AFL feed venue -> AFLTables venue (the record book's spelling). Sponsor
# names change; an unknown venue only loses the ground record, nothing else.
VENUES = {
    'MCG': 'M.C.G.', 'Marvel Stadium': 'Docklands', 'Adelaide Oval': 'Adelaide Oval',
    'Optus Stadium': 'Perth Stadium', 'Gabba': 'Gabba', 'SCG': 'S.C.G.',
    'People First Stadium': 'Carrara', 'Heritage Bank Stadium': 'Carrara',
    'GMHBA Stadium': 'Kardinia Park', 'ENGIE Stadium': 'Sydney Showground',
    'GIANTS Stadium': 'Sydney Showground', 'UTAS Stadium': 'York Park',
    'Ninja Stadium': 'Bellerive Oval', 'Blundstone Arena': 'Bellerive Oval',
    'Manuka Oval': 'Manuka Oval', 'Corroboree Group Oval Manuka': 'Manuka Oval',
    'TIO Stadium': 'Marrara Oval', 'Mars Stadium': 'Eureka Stadium',
    'Norwood Oval': 'Norwood Oval', 'TIO Traeger Park': 'Traeger Park',
    "Cazaly's Stadium": "Cazaly's Stadium", 'Hands Oval': 'Hands Oval',
    'Barossa Park': 'Barossa Park', 'Summit Sports Park': 'Summit Sports Park',
}


# The AFL's player list: provider id, date of birth, debut year. The only
# source of a date of birth for a player the record book has not seen (a
# debutant). It cannot be filtered, so it is walked whole (177 pages) and
# cached; a week-old copy is refreshed.
PLAYERS_CACHE = ROOT / 'data_feed' / 'afl_players.csv'
PLAYERS_MAX_AGE = 7 * 86400


class People:
    """Date of birth and games played for a feed player id, for players the
    record book cannot place. Loaded lazily, so a desk with every player
    matched never touches the player list."""

    def __init__(self, feed: 'Feed') -> None:
        self.feed = feed
        self._dob: dict[str, str] | None = None
        self._games: dict[str, int | None] = {}

    def dob(self, pid: str) -> str | None:
        if self._dob is None:
            self._dob = self.feed.player_dobs()
        return self._dob.get(pid)

    def career_games(self, pid: str) -> int | None:
        """playerProfile's careerGamesPlayed. Used only to tell a debutant
        (0 or 1, depending on when the AFL updates it during the match)."""
        if pid not in self._games:
            try:
                self._games[pid] = self.feed.cfs(f'playerProfile/{pid}')['playerProfile'].get('careerGamesPlayed')
            except Exception:
                self._games[pid] = None
        return self._games[pid]


class Feed:
    def __init__(self) -> None:
        self.s = fmc._session()
        self._tok = None
        self._tok_at = 0.0

    def player_dobs(self) -> dict[str, str]:
        import csv
        if not PLAYERS_CACHE.exists() or time.time() - PLAYERS_CACHE.stat().st_mtime > PLAYERS_MAX_AGE:
            rows, page = [], 0
            while True:
                r = self.s.get(f'{fmc.AFLAPI}/players', params={'pageSize': 100, 'page': page}, timeout=30)
                r.raise_for_status()
                j = r.json()
                rows += [(p['providerId'], p.get('firstName'), p.get('surname'), p.get('dateOfBirth'), p.get('debutYear'))
                         for p in j['players'] if p.get('providerId')]
                page += 1
                if page >= j['meta']['pagination']['numPages']:
                    break
            PLAYERS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            tmp = PLAYERS_CACHE.with_suffix('.tmp')
            with open(tmp, 'w', newline='', encoding='utf-8') as fh:
                w = csv.writer(fh)
                w.writerow(['providerId', 'firstName', 'surname', 'dateOfBirth', 'debutYear'])
                w.writerows(rows)
            tmp.replace(PLAYERS_CACHE)
            print(f'afl player list: {len(rows)} players cached')
        with open(PLAYERS_CACHE, encoding='utf-8') as fh:
            return {r['providerId']: r['dateOfBirth'] for r in csv.DictReader(fh) if r['dateOfBirth']}

    def token(self) -> str:
        if self._tok is None or time.time() - self._tok_at > 1800:
            self._tok = fmc._token(self.s)
            self._tok_at = time.time()
        return self._tok

    def cfs(self, path: str) -> dict:
        r = self.s.get(f'{fmc.CFS}/{path}', headers={'x-media-mis-token': self.token()}, timeout=20)
        if r.status_code == 401:
            self._tok = None
            r = self.s.get(f'{fmc.CFS}/{path}', headers={'x-media-mis-token': self.token()}, timeout=20)
        r.raise_for_status()
        return r.json()

    def compseason(self, season: int) -> int:
        cs = fmc._compseasons(self.s)
        if season not in cs:
            raise SystemExit(f'the AFL has no {season} premiership season yet')
        return cs[season]

    def round_matches(self, season: int, round_number: int | None = None) -> tuple[int, list[dict]]:
        """(round number, the round's matches). None means the AFL's current round."""
        cs = self.compseason(season)
        if round_number is None:
            r = self.s.get(f'{fmc.AFLAPI}/compseasons/{cs}', timeout=20)
            r.raise_for_status()
            round_number = r.json().get('currentRoundNumber')
        r = self.s.get(f'{fmc.AFLAPI}/matches', params={
            'competitionId': 1, 'compSeasonId': cs, 'roundNumber': round_number, 'pageSize': 20}, timeout=30)
        r.raise_for_status()
        out = []
        for m in r.json().get('matches', []):
            out.append({
                'id': m['providerId'],
                'home': fmc.CD_TEAM.get(m['home']['team']['providerId'], m['home']['team']['name']),
                'away': fmc.CD_TEAM.get(m['away']['team']['providerId'], m['away']['team']['name']),
                'home_cd': m['home']['team']['providerId'],
                'venue_feed': m['venue']['name'],
                'venue': VENUES.get(m['venue']['name']),
                'utc': m.get('utcStartTime'),
                'status': m.get('status'),
                'round_name': m['round'].get('name'),
                'round_abbr': m['round'].get('abbreviation'),
            })
        return round_number, out

    def match_state(self, mid: str) -> dict:
        """Status, period and score from matchItem."""
        j = self.cfs(f'matchItem/{mid}')
        sc = j.get('score') or {}
        status = sc.get('status') or j.get('match', {}).get('status')
        periods = [p['periodNumber'] for p in sc.get('homeTeamScore', {}).get('periodScore', [])]
        clock = sc.get('matchClock') or {}
        period = sc.get('currentPeriod') or clock.get('period') or (max(periods) if periods else 0)
        secs = clock.get('periodSeconds') or clock.get('seconds')
        score = None
        if sc.get('homeTeamScore'):
            h, a = sc['homeTeamScore']['matchScore'], sc['awayTeamScore']['matchScore']
            score = f"{h['goals']}.{h['behinds']} {h['totalScore']} - {a['goals']}.{a['behinds']} {a['totalScore']}"
        return {'status': status, 'period': int(period or 0), 'secs': secs, 'score': score}

    def players(self, mid: str) -> list[dict]:
        """Every player's running line: name, club, feed id, desk stats."""
        j = self.cfs(f'playerStats/match/{mid}')
        out = []
        for side in ('homeTeamPlayerStats', 'awayTeamPlayerStats'):
            for row in j.get(side, []):
                p = row['player']['player']['player']
                n = p['playerName']
                s = row['playerStats']['stats']
                line = {k: int(s.get(fk) or 0) for fk, k in FEED_STATS.items()}
                cl = s.get('clearances') or {}
                line['Clearances'] = int(cl.get('totalClearances') or 0)
                line['Centre Clearances'] = int(cl.get('centreClearances') or 0)
                e = s.get('extendedStats') or {}
                line.update({k: int(e.get(fk) or 0) for fk, k in EXTENDED_STATS.items()})
                out.append({
                    'feed_id': p['playerId'],
                    'name': f"{n.get('givenName', '')} {n.get('surname', '')}".strip(),
                    'surname': n.get('surname', ''),
                    'club': fmc.CD_TEAM.get(row.get('teamId'), row.get('teamId')),
                    'stats': line,
                })
        return out


def elapsed(state: dict) -> tuple[float, str]:
    """Share of the match played, and the label a post uses for the moment.

    At a break the label is the break (QT, HT, 3QT); mid-quarter it is the
    quarter (Q2). Unknown clock: assume the last scored period is complete,
    which is exactly right at a break, the moment the desk is built for.
    """
    st = (state.get('status') or '').upper()
    p = state.get('period') or 0
    if st in DONE:
        return 1.0, 'FT'
    if p <= 0:
        return 0.0, 'PRE'
    secs = state.get('secs')
    if isinstance(secs, (int, float)) and secs > 0:
        q = min(secs / 1800.0, 1.0)
        return min((p - 1 + q) / 4.0, 1.0), f'Q{p}'
    return min(p / 4.0, 1.0), {1: 'QT', 2: 'HT', 3: '3QT'}.get(p, 'FT')
