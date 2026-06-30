"""Standalone AFL Brownlow Predictor scraper.

Pulls the AFL's own per-round Brownlow vote predictions from the official AFL
award API (the feed behind afl.com.au/brownlow-medal/live-tracker). Each player
object carries a `rounds` map giving a real per-round 3-2-1 breakdown — not just
a season total — which is what makes this usable for the Polls-a-Vote round
verdict.

Writes:
  data_2026/afl_predictor_predictions.csv   season totals (Player, Team, Total_Votes, Rank)
  data_2026/afl_predictor_round_votes.csv   per-round votes (Player, Round, Vote)

Round numbers are the AFL's native round (display/AFL convention: 0 = Opening
Round), matching betfair_round_votes.csv and the dashboard's My_Rounds picks.
"""

import os
import shutil
import pandas as pd
import requests

_BASE = "https://aflapi.afl.com.au/afl/v2"
_HDRS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Referer": "https://www.afl.com.au/brownlow-medal/live-tracker",
}
_SEASON_CSV = "data_2026/afl_predictor_predictions.csv"
_ROUND_CSV = "data_2026/afl_predictor_round_votes.csv"


def _save_with_backup(df, csv_path):
    _prev = csv_path.replace('.csv', '_prev.csv')
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    if os.path.exists(csv_path):
        shutil.copy2(csv_path, _prev)
    df.to_csv(csv_path, index=False)


def _resolve_season(sess, timeout):
    """Current AFLM Premiership compSeason id + name."""
    cr = sess.get(f"{_BASE}/competitions/1/compseasons?pageSize=5", timeout=timeout)
    cr.raise_for_status()
    seasons = [s for s in cr.json().get("compSeasons", [])
               if "Premiership" in s.get("name", "")]
    if not seasons:
        raise ValueError("Could not resolve current AFL Premiership season.")
    return seasons[0]["id"], seasons[0].get("name", "")


def _team_map(sess, season_id, timeout):
    tr = sess.get(f"{_BASE}/teams?compSeasonId={season_id}&pageSize=100", timeout=timeout)
    if tr.status_code != 200:
        return {}
    return {t["id"]: t.get("name", str(t["id"])) for t in tr.json().get("teams", [])}


def fetch(timeout=20):
    try:
        print('[AFL] Fetching predictions from AFL award API...')
        sess = requests.Session()
        sess.headers.update(_HDRS)

        season_id, season_name = _resolve_season(sess, timeout)
        teams = _team_map(sess, season_id, timeout)

        players = []
        for page in range(6):
            pr = sess.get(
                f"{_BASE}/compseasons/{season_id}/award/brownlow"
                f"?page={page}&pageSize=100", timeout=timeout)
            if pr.status_code != 200:
                break
            batch = pr.json().get("players", [])
            if not batch:
                break
            players.extend(batch)
            if batch[-1].get("totalVotes", 0) == 0 and page >= 1:
                break
        if not players:
            raise ValueError("AFL API returned no player data.")

        season_rows, round_rows = [], []
        for p in players:
            name = f"{p.get('firstName', '')} {p.get('surname', '')}".title().strip()
            if not name:
                continue
            team = teams.get(p.get("teamId", 0), "")
            season_rows.append({
                'Player': name, 'Team': team,
                'Total_Votes': float(p.get("totalVotes", 0) or 0),
            })
            # Per-round breakdown. A round is "covered" only if he played it
            # (entry carries a providerId / match id). Byes and unplayed rounds
            # have no providerId, so they're omitted → read as NA, not a 0-vote
            # disagreement. Played-but-didn't-poll keeps vote 0 (real disagree).
            for rkey, entries in (p.get("rounds") or {}).items():
                try:
                    rnum = int(rkey)
                except (TypeError, ValueError):
                    continue
                played, pts = False, 0
                for e in entries:
                    if isinstance(e, dict) and 'providerId' in e:
                        played = True
                        pts = max(pts, int(e.get("points", 0) or 0))
                if played:
                    round_rows.append({'Player': name, 'Round': rnum, 'Vote': float(pts)})

        sdf = (pd.DataFrame(season_rows)
               .sort_values('Total_Votes', ascending=False, kind='stable')
               .reset_index(drop=True))
        sdf['Rank'] = sdf.index + 1
        sdf = sdf[['Player', 'Team', 'Total_Votes', 'Rank']]
        _save_with_backup(sdf, _SEASON_CSV)
        print(f'[AFL] OK ({len(sdf)} players, {season_name})')
        print(sdf.head(10).to_string(index=False))

        if round_rows:
            rdf = (pd.DataFrame(round_rows)
                   .sort_values(['Player', 'Round']).reset_index(drop=True))
            _save_with_backup(rdf, _ROUND_CSV)
            polled = (rdf['Vote'] >= 1).sum()
            print(f'[AFL] round-level votes: {len(rdf)} rows '
                  f'({rdf["Round"].nunique()} rounds, {polled} with a vote) -> {_ROUND_CSV}')
        else:
            print('[AFL] no per-round data available yet (no votes published).')

        return True

    except Exception as e:
        print(f'[AFL] FAILED: {e}')
        for f in (_SEASON_CSV, _ROUND_CSV):
            if os.path.exists(f):
                print(f'[AFL] Keeping existing cached {f} (unchanged)')
        return False


if __name__ == '__main__':
    fetch()
