"""The season's model scorecard, as templated post drafts. Nothing posts.

    python scripts/scorecard_posts.py [season]      default: season.current_season()

Writes drafts/scorecard_<season>.md. Templated like draft_posts.py and
count_tweets.py, for the same reason: a template cannot invent an accuracy
claim. Every figure is computed from files, and each is a count a reader can
check on the site, never a percentage (project_brief.md, "Copy rules": no
accuracy percentages unless Charlie supplies the number).

Needs the season counted and backfilled (season_rollover.py --apply), because it
reads actual votes from predictions/game_level_<s>.csv and season_<s>.csv.

Board naming: the site's default board is the DECIMAL one, labelled "PROJECTED
VOTES", so "the model's No. 1" here is the decimal rank, and any 3-2-1 figure
says 3-2-1 (see the board-naming rule in memory and CLAUDE.md).
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import season as season_cfg  # noqa: E402
import site_data as sd  # noqa: E402

KEY = ["Round_num", "Home.team", "Away.team", "Player_Name"]
TAGS = "#AFL #Brownlow"
SITE = "chachingbrownlow.com"


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def top_pick(g):
    """(hits, games): the P_3 argmax in each complete game took the 3.
    dashboard.top_pick_record's rule, on the backfilled file."""
    g = g.drop_duplicates(KEY)
    gid = g["Round_num"].astype(str) + "|" + g["Home.team"] + "|" + g["Away.team"]
    ok = g.groupby(gid)["Brownlow.Votes"].transform("sum") == 6
    g, gid = g[ok], gid[ok]
    top = g.loc[g.groupby(gid)["P_3"].idxmax()]
    return int((top["Brownlow.Votes"] == 3).sum()), len(top)


def build(season):
    if not season_cfg.counted(season):
        raise SystemExit(f"{season} is not counted yet")
    g = sd.load_game(season)
    se = sd.load_season(season)
    if g is None or se is None or g["Brownlow.Votes"].fillna(0).sum() == 0:
        raise SystemExit(f"{season} has no votes in its prediction files; run season_rollover.py --apply")

    se = se.copy()
    se["Actual_Votes"] = se["Actual_Votes"].fillna(0).astype(int)
    se["model_rank"] = se["Exp_Total_Votes"].rank(ascending=False, method="min").astype(int)
    act = se.sort_values(["Actual_Votes", "Exp_Total_Votes"], ascending=False).reset_index(drop=True)
    mod = se.sort_values("Exp_Total_Votes", ascending=False).reset_index(drop=True)
    top_votes = int(act["Actual_Votes"].iloc[0])
    winners = act[act["Actual_Votes"] == top_votes]
    win_line = " & ".join(
        f"{r.Player_Name} ({'model No. 1' if r.model_rank == 1 else 'model ' + ordinal(r.model_rank)})"
        for r in winners.itertuples())

    a3, m3 = list(act["Player_Name"][:3]), list(mod["Player_Name"][:3])
    same3 = a3 == m3
    in3 = len(set(a3) & set(m3))
    a10, m10 = set(act["Player_Name"][:10]), set(mod["Player_Name"][:10])
    a20, m20 = set(act["Player_Name"][:20]), set(mod["Player_Name"][:20])
    hits, games = top_pick(g)

    posts = []
    posts.append(("scorecard", "\n".join([
        f"How the model called the {season} Brownlow:",
        "",
        f"Winner: {win_line}",
        f"Top 3: {'all three, in order' if same3 else f'{in3} of 3'}",
        f"Top 10: {len(a10 & m10)} of the actual top 10",
        f"Top 20: {len(a20 & m20)} of the actual top 20",
        f"Model's top pick polled 3 in {hits} of {games} games",
        "",
        f"Every game, every vote at {SITE}",
        TAGS,
    ])))

    r = sd.load_season_rounded(season)
    if r is not None and not r.empty:
        board = dict(zip(r["Player_Name"], r["Exp_Total_Votes"].astype(int)))
        rows = [f"{p.Player_Name} {p.Actual_Votes}, 3-2-1 board {board.get(p.Player_Name, 0)}"
                for p in act.head(4).itertuples()]
        exact = sum(1 for p in act.head(10).itertuples() if board.get(p.Player_Name) == p.Actual_Votes)
        posts.append(("3-2-1 board vs the count", "\n".join([
            "The count against our 3-2-1 board:",
            "",
            *rows,
            "",
            f"{exact} of the top 10 landed on their 3-2-1 total exactly.",
            f"{SITE}/leaderboard",
            TAGS,
        ])))

    close = act.head(20).assign(gap=lambda d: (d["Actual_Votes"] - d["Exp_Total_Votes"]).abs())
    closest = close.nsmallest(4, "gap")
    posts.append(("closest calls", "\n".join([
        f"The model's closest calls in the {season} top 20:",
        "",
        *[f"{p.Player_Name} {p.Actual_Votes}, model {p.Exp_Total_Votes:.1f} exp" for p in closest.itertuples()],
        "",
        f"Every player at {SITE}/leaderboard",
        TAGS,
    ])))
    return posts


def main(argv):
    season = int(argv[0]) if argv else season_cfg.current_season()
    posts = build(season)
    out = os.path.join("drafts", f"scorecard_{season}.md")
    os.makedirs("drafts", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {season} model scorecard: DRAFTS, not signed off\n\n")
        for name, body in posts:
            f.write(f"--- {name} [{len(body)} chars] ---\n{body}\n\n")
    long = [n for n, b in posts if len(b) > 280]
    if long:
        print(f"! over 280 characters: {', '.join(long)}")
    for name, body in posts:
        print(f"--- {name} [{len(body)} chars] ---\n{body}\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
