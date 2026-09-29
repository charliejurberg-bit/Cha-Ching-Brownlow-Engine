"""AFLW Best and Fairest SEASON TOTALS for every vote-getter, for the seasons
whose per-match votes are incomplete.

    python aflw/recover_totals.py [season ...]

Writes data_aflw/totals_<season>.csv (playerId, player, team, votes). A season
total cannot say which match a vote came from, but for every player NOT listed
it says something exact: she polled nothing in any match. With the club
articles' per-match votes (aflw/recover_club_votes.py) that pins down most of a
season by elimination, and the model can train on what remains through the
constraint rather than a guess (aflw/build.py).

SOURCE: the AFL's "How your club polled" article, which lists every club's
vote-getters as "Name - votes" under a "Total votes: N" line. The club names are
images, so each name is placed by matching it against the season's rosters in
data_aflw/stats_<year>.csv, and each block must sum to its own "Total votes".
The season must total 6 per home-and-away match or nothing is written.
"""

import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recover_votes as rv  # noqa: E402

ARTICLES = {
    "2023": ("https://www.afl.com.au/aflw/news/1068505/x", "How your club polled"),
}


def parse(lines):
    """[(block total, [(name, votes)])] in article order."""
    blocks, cur = [], None
    for ln in lines:
        m = re.fullmatch(r"Total votes:\s*(\d+)", ln)
        if m:
            cur = (int(m.group(1)), [])
            blocks.append(cur)
            continue
        m = re.fullmatch(r"(.+?)\s+[-–]\s+(\d+)", ln)
        if m and cur is not None:
            cur[1].append((m.group(1).strip(), int(m.group(2))))
    return blocks


def roster(season):
    st = rv.load_stats(season)
    cols = ["player.player.player.playerId", "player.player.player.givenName",
            "player.player.player.surname", "_team", "_given", "_sur"]
    return st[cols].drop_duplicates("player.player.player.playerId")


def place(name, ro, team=None):
    """The one roster player a published name means, within `team` if given."""
    cand = ro if team is None else ro[ro._team == team]
    hit = rv._find(cand, name)
    if len(hit) != 1:
        # A nickname ("Ally" for Alexandra, "Mon" for Monique): surname alone,
        # accepted when that surname is unique in the candidate set.
        sur = rv.norm(rv.NAME_FIXES.get(name.strip(), name))[-1:]
        hit = cand.loc[cand._sur.map(lambda s: s[-1:] == sur).astype(bool)]
    return hit


def main(argv):
    for season in argv or sorted(ARTICLES):
        url, must = ARTICLES[season]
        blocks = parse(rv.page_text(url, must))
        ro = roster(season)
        games = rv.load_stats(season).providerId.nunique()
        rows, bad = [], []
        # Every name in article order. The "Total votes" lines stop partway (from
        # St Kilda on in 2023), so blocks cannot be trusted to be clubs; each name
        # is placed league-wide instead, and a name two clubs share takes the
        # club of its neighbours, since the article lists club by club.
        names = [nv for _, ns in blocks for nv in ns]
        first = [place(n, ro) for n, _ in names]
        team_of = [h._team.iloc[0] if len(h) == 1 else None for h in first]
        for i, ((n, v), h) in enumerate(zip(names, first)):
            hit = h
            if len(h) != 1:
                near = [t for t in team_of[max(0, i - 3):i] + team_of[i + 1:i + 4] if t]
                team = max(set(near), key=near.count) if near else None
                hit = place(n, ro, team) if team else h
            if len(hit) != 1:
                bad.append(f"{n}: {len(hit)} players")
                continue
            r = hit.iloc[0]
            rows.append({"playerId": r["player.player.player.playerId"],
                         "player": f"{r['player.player.player.givenName']} {r['player.player.player.surname']}",
                         "team": r._team, "votes": v})
        for total, ns in blocks:
            if len(ns) and sum(v for _, v in ns) != total and len(ns) < 12:
                bad.append(f"block of {total} lists {sum(v for _, v in ns)}")
        df = pd.DataFrame(rows)
        want = games * 6
        print(f"{season}: {len(blocks)} club blocks, {len(df)} players, {int(df.votes.sum())} votes "
              f"(expected {want} from {games} matches)")
        for b in bad:
            print("   ", b)
        if bad or df.votes.sum() != want or df.playerId.duplicated().any():
            print("   refusing to write")
            continue
        df.insert(0, "season", season)
        df.to_csv(os.path.join(rv.OUT, f"totals_{season}.csv"), index=False)
        print(f"   wrote totals_{season}.csv")


if __name__ == "__main__":
    main(sys.argv[1:])
