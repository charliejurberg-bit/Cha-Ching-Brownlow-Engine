# -*- coding: utf-8 -*-
"""A season's actual Brownlow votes, per player per game, off the AFL's live feed.

    python scripts/fetch_brownlow_votes.py            # season.LIVE_SEASON
    python scripts/fetch_brownlow_votes.py 2027       # after the 2027 count

Writes `data_2026/brownlow_votes_2026.csv`: one row per vote-getter per game,
keyed the way `predictions/game_level_2026.csv` is (Round_num, Home.team,
Away.team, Player_Name, Playing.for, ID). It is the only record of the count in
the repo. `game_level_2026.csv` still carries Brownlow.Votes = 0 on every row,
and is left alone because the dashboard reads it as the season's predictions.

The feed is `bfawards_feed.raw()`, the one that actually carried the count (see
CLAUDE.md, "Count night and the Live Tracker"). Its round numbers are the AFL's,
so Round_num = roundNumber + 1 in 2026.

Names are matched INSIDE one club's side of one round, never league-wide: full
name, then first initial plus surname, then a surname unique within that side.
The run refuses to write unless every vote lands on a row and all 207 games
total exactly 6, which is the whole acceptance test.
"""

import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bfawards_feed  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import season as season_cfg  # noqa: E402

# The feed's club names against the AFLTables spellings game_level uses.
FEED_CLUBS = {
    "Sydney Swans": "Sydney", "GWS GIANTS": "Greater Western Sydney",
    "Geelong Cats": "Geelong", "Gold Coast SUNS": "Gold Coast",
    "Adelaide Crows": "Adelaide", "West Coast Eagles": "West Coast",
}


def _norm(s):
    return re.sub(r"[^a-z]", "", str(s).lower())


def main():
    season = int(sys.argv[1]) if len(sys.argv) > 1 else season_cfg.LIVE_SEASON
    GAME_LEVEL = os.path.join(REPO, season_cfg.pred_path("game_level_{s}.csv", season))
    OUT = os.path.join(REPO, season_cfg.data_path("brownlow_votes_{s}.csv", season))
    GAMES = season_cfg.cfg(season)["games"]
    if not GAMES:
        raise SystemExit(f"season.py has no game count for {season}; set it first")
    status, match_votes, _ = bfawards_feed.raw(bfawards_feed.season_ids(season)[1])
    if status != "CONCLUDED":
        raise SystemExit(f"feed status is {status!r}, not CONCLUDED: the count "
                         "is not final, refusing to write a partial record")

    g = pd.read_csv(GAME_LEVEL, low_memory=False,
                    usecols=["Round_num", "Home.team", "Away.team", "Player_Name",
                             "First.name", "Surname", "Playing.for", "ID"])
    g = g.drop_duplicates(["Round_num", "Player_Name", "Playing.for"])
    g["_full"] = (g["First.name"] + g["Surname"]).map(_norm)
    g["_sur"] = g.Surname.map(_norm)
    g["_ini"] = g["First.name"].map(lambda x: _norm(x)[:1])

    rows, missed = [], []
    for m in match_votes:
        # The feed numbers Opening Round 0; AFLTables numbers it raw round 1.
        # True from 2024 (the first Opening Round), the same law as _display_round.
        rn = m["roundNumber"] + (1 if season >= 2024 else 0)
        for v in m.get("votes") or []:
            if not v.get("votes"):
                continue
            p = v["player"]
            name = v["team"]["teamName"]
            club = FEED_CLUBS.get(name, name)
            side = g[(g.Round_num == rn) & (g["Playing.for"] == club)]
            hit = side[side._full == _norm(p["givenName"] + p["surname"])]
            if len(hit) != 1:
                hit = side[(side._sur == _norm(p["surname"]))
                           & (side._ini == _norm(p["givenName"])[:1])]
            if len(hit) != 1:
                hit = side[side._sur == _norm(p["surname"])]
            if len(hit) != 1:
                missed.append(f"R{rn} {club}: {p['givenName']} {p['surname']} "
                              f"({len(hit)} candidates)")
                continue
            r = hit.iloc[0]
            rows.append({"Season": season, "Round_num": rn,
                         "Home.team": r["Home.team"], "Away.team": r["Away.team"],
                         "Player_Name": r.Player_Name, "Playing.for": club,
                         "ID": r.ID, "Brownlow.Votes": v["votes"],
                         "Eligible": v.get("eligible", True),
                         "matchId": m["matchId"]})
    if missed:
        raise SystemExit("unmatched vote-getters, refusing to write:\n  "
                         + "\n  ".join(missed))

    out = pd.DataFrame(rows)
    per_game = out.groupby(["Round_num", "Home.team", "Away.team"])["Brownlow.Votes"].sum()
    bad = per_game[per_game != 6]
    if len(per_game) != GAMES or len(bad):
        raise SystemExit(f"{len(per_game)} games, {len(bad)} not totalling 6: "
                         f"{bad.to_dict()}. Refusing to write.")
    out.sort_values(["Round_num", "Home.team", "Brownlow.Votes"],
                    ascending=[True, True, False]).to_csv(OUT, index=False)
    print(f"wrote {len(out)} rows, {len(per_game)} games, "
          f"{out['Brownlow.Votes'].sum()} votes -> {os.path.relpath(OUT, REPO)}")


if __name__ == "__main__":
    main()
