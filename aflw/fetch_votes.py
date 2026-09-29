"""AFLW Best and Fairest votes per match, from the AFL's live-count feed.

    python aflw/fetch_votes.py [season ...]        default: every season the feed has

Writes data_aflw/votes_<season>.csv: one row per vote-getter per match, with the
AFL's match providerId and player id, which are the keys data_aflw/stats_*.csv
carries, so the join needs no names.

The feed (bfawards, see scripts/bfawards_feed.py) only holds the seasons counted
since it went live: 2024 and 2025 as of September 2026. Earlier seasons come
from aflw/recover_votes.py. A season is written only when the feed says
CONCLUDED and every match it lists totals exactly 6, so a partial count never
lands on disk.
"""

import os
import sys

import pandas as pd
import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import bfawards_feed as bf  # noqa: E402

OUT = os.path.join(REPO, "data_aflw")


def aflw_seasons():
    """{year label: providerId} for every AFLW compSeason. 2022 has two, labelled
    '2022S6' and '2022S7' as the stats files' compSeason names do."""
    r = requests.get(f"{bf.BASE}/competitions/3/compseasons?pageSize=40", headers=bf.HDRS, timeout=bf.TMO)
    r.raise_for_status()
    out = {}
    for c in r.json()["compSeasons"]:
        name = c["name"]
        year = name[:4]
        label = year + ("S6" if "Season 6" in name else "S7" if "Season 7" in name else "")
        out[label] = c["providerId"]
    return out


def fetch(provider_id, sess, tok):
    s = sess.get(f"{bf.CFS}/bfawards/season/{provider_id}", headers={"x-media-mis-token": tok}, timeout=30)
    s.raise_for_status()
    j = s.json()
    rows = []
    for m in j.get("matchVotes") or []:
        for v in m.get("votes") or []:
            p, t = v.get("player") or {}, v.get("team") or {}
            if v.get("votes"):
                rows.append({"matchId": m["matchId"], "round": m.get("roundNumber"),
                             "playerId": p.get("playerId"),
                             "player": f"{p.get('givenName', '')} {p.get('surname', '')}".strip(),
                             "team": t.get("teamName"), "votes": int(v["votes"])})
    return j.get("status"), pd.DataFrame(rows)


def main(argv):
    seasons = aflw_seasons()
    want = argv or sorted(seasons)
    tok, sess = bf.token()
    for label in want:
        status, df = fetch(seasons[label], sess, tok)
        if df.empty:
            print(f"  {label}: no votes on the feed (status {status})")
            continue
        per = df.groupby("matchId")["votes"].sum()
        if status != "CONCLUDED" or (per != 6).any():
            print(f"  {label}: refusing, status {status}, {int((per != 6).sum())} matches not totalling 6")
            continue
        df.insert(0, "season", label)
        path = os.path.join(OUT, f"votes_{label}.csv")
        df.to_csv(path, index=False)
        print(f"  {label}: {len(per)} matches, {int(df.votes.sum())} votes -> {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
