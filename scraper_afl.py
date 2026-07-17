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

A round-votes row means "this match was counted and he got this many votes" —
so a 0 there is a real disagreement, not silence. Matches the AFL hasn't counted
yet are omitted rather than written as zeros (see fetch), because a consumer
can't tell the two apart from the CSV alone: Polls-a-Vote reads any present row
as a verdict, so an uncounted match written as 0 would read as "the AFL says he
didn't poll".
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
            # Per-round breakdown. Three buckets:
            #   didn't play (bye/dnp)      → no providerId → omitted → reads NA
            #   played, match counted, 0   → vote 0 kept   → real disagreement
            #   played, match NOT counted  → dropped below → omitted → reads NA
            # The API can't tell the last two apart per player: an uncounted match
            # still carries a providerId with points 0. They're separated after the
            # loop, per match — hence _match is carried here and dropped before write.
            for rkey, entries in (p.get("rounds") or {}).items():
                try:
                    rnum = int(rkey)
                except (TypeError, ValueError):
                    continue
                played, pts, mid = False, 0, None
                for e in entries:
                    if isinstance(e, dict) and 'providerId' in e:
                        played = True
                        if mid is None:
                            mid = e['providerId']
                        pts = max(pts, int(e.get("points", 0) or 0))
                if played:
                    round_rows.append({'Player': name, 'Round': rnum,
                                       'Vote': float(pts), '_match': mid})

        sdf = (pd.DataFrame(season_rows)
               .sort_values('Total_Votes', ascending=False, kind='stable')
               .reset_index(drop=True))
        sdf['Rank'] = sdf.index + 1
        sdf = sdf[['Player', 'Team', 'Total_Votes', 'Rank']]
        _save_with_backup(sdf, _SEASON_CSV)
        print(f'[AFL] OK ({len(sdf)} players, {season_name})')
        print(sdf.head(10).to_string(index=False))

        if round_rows:
            rdf = pd.DataFrame(round_rows)
            # Drop uncounted matches. Votes are awarded per match (3+2+1=6), so a
            # match where nobody we captured polled has not been counted yet — its
            # zeros mean "not published", not "played, polled nothing". Filtering
            # per match rather than per round is what makes a round that's counted
            # game-by-game come out right: the counted games stay, the rest wait.
            # Zeros inside a match that has any vote are real disagreements (a
            # played-but-didn't-poll player) and are kept.
            #
            # Accepted edge case: a match IS counted but all three vote-getters sit
            # outside our capture (top ~180 by season total). The match then looks
            # uncounted and is dropped, so its players read NA instead of
            # TIPS_OTHER. Conservative — silence, never a false disagreement — and
            # rare, since a 3-vote game almost always lifts a player into the top
            # 180. Self-corrects on the next run once he's captured.
            _scored = rdf.groupby('_match')['Vote'].transform('sum') > 0
            _dropped_matches = rdf.loc[~_scored, '_match'].nunique()
            _dropped_rows = int((~_scored).sum())
            rdf = rdf[_scored].drop(columns='_match')
            rdf = rdf.sort_values(['Player', 'Round']).reset_index(drop=True)
            if _dropped_rows:
                print(f'[AFL] skipped {_dropped_rows} row(s) across {_dropped_matches} '
                      f'uncounted match(es) - votes not published yet.')

        if round_rows and not rdf.empty:
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
