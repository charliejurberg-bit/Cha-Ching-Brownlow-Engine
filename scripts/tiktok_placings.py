# -*- coding: utf-8 -*-
"""The placings picks (top 3, 5, 10 and 20 finish) as one TikTok photo carousel.

    python scripts/sb_placings_board.py           # refresh prices first
    python scripts/tiktok_placings.py             # cover + 6 picks + closer
    python scripts/tiktok_placings.py --only oliver   # one slide, while iterating

Writes 1080x1920 PNGs to `drafts/tiktok_placings/` (gitignored), copies them to
`OneDrive/Pictures/ChaChing Slides/Placings/` so the phone can see them, and
writes the draft copy to `drafts/tiktok_placings_<season>.md`. It never posts.

THE DRAWING IS tiktok_market.py's, UNCHANGED
Same slide, cover and closer, so the two decks read as one series. Each pick
carries its market's wording (masthead label, the line that leads under the
name, the two words beside the price, the cover label) and draw_slide reads
them off the pick. The 3 vote deck renders byte-identical through the same
functions.

ONE DECK ACROSS FOUR BOARDS, NOT FOUR DECKS
Top 3 and top 5 have no short-priced runner the model rates above the book, so
a deck per board would have had no honest safe tier on two of them. The safe
picks come from top 10 and top 20, and every slide names its board, which is
why the board leads the line under the name where the 3 vote deck puts the
round.

TWO CELLS ARE FIXED AND FOUR ARE THE PLAYER'S OWN CASE
Projected votes top left and coaches votes under it, so the left column reads
as the vote case down the whole deck. The other four are chosen per player, for
the reason the 3 vote deck gives: a fixed set put "1 GAMES AS FAVOURITE" and
"1 COACHES BOG" on the slide arguing Clayton Oliver makes the top 10, which is
the slide arguing against itself. His case is ball winning (1st in the league
for contested possessions a game, 4th for clearances), so that is what shows.

Projected votes and model rank are the DECIMAL board, the same figures the site
labels PROJECTED VOTES, so a reader who follows the link finds the same number.
The simulator's own mean runs higher for players the model favours within
their games and is never shown. Rank is minimum-on-ties over the displayed
figure across every player, with an = where it is shared.

Score involvements is `Score_Involvements_Actual` from the footywire join, never
the engineered column of the same name in game_level; see CLAUDE.md.
"""

import argparse
import os
import shutil
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sb_3vote_board import _dashboard_ns                           # noqa: E402
from tiktok_market import (                                        # noqa: E402
    BOOK, COUNT_DATE, PHONE_DIR, SEASON, TIER_LABEL, draw_closer, draw_cover,
    draw_slide, hashtags, save,
)
from tiktok_top10 import DOMAIN, SAFE_BOT, SAFE_TOP, rank_text    # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(REPO, "data_betting", "sb_placings_board.csv")
GAME_LEVEL = os.path.join(REPO, "predictions", "game_level_2026.csv")
SEASON_TOTALS = os.path.join(REPO, "predictions", "season_2026.csv")
SI_PATH = os.path.join(REPO, "data_advanced", "score_involvements.csv")
OUT_DIR = os.path.join(REPO, "drafts", "tiktok_placings")
PHONE_SUB = os.path.join(PHONE_DIR, "Placings")
SIMS = "100,000"             # sb_placings_board.SIMS_2026, as the closer says it

# Every season figure a slide can show: the column in _season_frame, the label,
# the format. "proj" and "cv" are the fixed anchors in slots 0 and 3.
STATS = {
    "proj":   ("Exp_Total_Votes", "PROJECTED VOTES", "{:.1f}"),
    "cv":     ("cv", "COACHES VOTES", "{:.0f}"),
    "disp":   ("disp", "DISPOSALS / GAME", "{:.1f}"),
    "d30":    ("d30", "30+ DISPOSAL GAMES", "{:.0f}"),
    "cp":     ("cp", "CONTESTED POSS / GAME", "{:.1f}"),
    "clr":    ("clr", "CLEARANCES / GAME", "{:.1f}"),
    "goals":  ("goals", "GOALS", "{:.0f}"),
    "si":     ("si", "SCORE INVOLVEMENTS / GAME", "{:.1f}"),
    "bog":    ("bog", "COACHES BOG", "{:.0f}"),
    "fav":    ("fav", "GAMES AS FAVOURITE", "{:.0f}"),
    "poll50": ("poll50", "GAMES LIKELY TO POLL", "{:.0f}"),
    "games":  ("games", "GAMES", "{:.0f}"),
}

# Player, board, tier, and the four cells that are his own case (slots 1, 2, 4
# and 5). Everything else is read.
PICKS = [
    dict(key="sheezel", name="Harry Sheezel", board=10, tier="SAFE",
         cells=["disp", "d30", "fav", "si"]),
    dict(key="walsh", name="Sam Walsh", board=20, tier="SAFE",
         cells=["disp", "d30", "bog", "games"]),
    dict(key="hornefrancis", name="Jason Horne-Francis", board=10, tier="SAFE",
         cells=["clr", "goals", "poll50", "bog"]),
    dict(key="bolton", name="Shai Bolton", board=20, tier="VALUE",
         cells=["si", "goals", "bog", "fav"]),
    dict(key="ashcroft", name="Will Ashcroft", board=3, tier="VALUE",
         cells=["fav", "bog", "disp", "d30"]),
    dict(key="oliver", name="Clayton Oliver", board=10, tier="LONGSHOT",
         cells=["cp", "clr", "disp", "d30"]),
]
TIER_SHORT = {"SAFE": "SAFE", "VALUE": "VALUE", "LONGSHOT": "LONGSHOT"}


# ------------------------------------------------------------------ data
def _season_frame():
    """Per player, keyed name|club: the decimal board figure and its rank, and
    every season figure in STATS."""
    ns = _dashboard_ns()
    g = ns["_fit_game_probs"](pd.read_csv(GAME_LEVEL, low_memory=False))
    g = g.drop_duplicates(subset=["Game_ID", "Player_Name"]).copy()
    g["_key"] = g.Player_Name.astype(str) + "|" + g["Playing.for"].astype(str)
    g["_poll"] = g[["P_1_game", "P_2_game", "P_3_game"]].sum(axis=1)

    # The model's favourite for the 3 in each game, on the fitted P(3).
    fav = g.loc[g.groupby("Game_ID").P_3_game.idxmax(), "_key"].value_counts()
    # Coaches' best on ground: the most coaches votes in his game, ties shared.
    top_cv = g.groupby("Game_ID").Coaches_Votes.transform("max")
    g["_bog"] = (g.Coaches_Votes == top_cv) & (top_cv > 0)

    adv = pd.read_csv(SI_PATH)
    adv = adv[adv.Season == SEASON][["Round_num", "ID", "Score_Involvements_Actual"]]
    g = g.merge(adv.drop_duplicates(subset=["Round_num", "ID"]),
                on=["Round_num", "ID"], how="left")

    per = g.groupby("_key").agg(
        games=("Game_ID", "size"), disp=("Disposals", "mean"),
        d30=("Disposals", lambda x: int((x >= 30).sum())),
        cp=("Contested.Possessions", "mean"), clr=("Clearances", "mean"),
        goals=("Goals", "sum"), cv=("Coaches_Votes", "sum"), bog=("_bog", "sum"),
        poll50=("_poll", lambda x: int((x >= 0.5).sum())),
        si=("Score_Involvements_Actual", "mean"),
        si_n=("Score_Involvements_Actual", "count"))
    per["fav"] = fav.reindex(per.index).fillna(0).astype(int)

    s = pd.read_csv(SEASON_TOTALS)
    s["_key"] = s.Player_Name.astype(str) + "|" + s.Team.astype(str)
    shown = s.Exp_Total_Votes.round(1)
    s["rank"] = shown.rank(ascending=False, method="min").astype(int)
    s["tied"] = shown.map(shown.value_counts()) > 1
    return per.join(s.set_index("_key")[["Exp_Total_Votes", "rank", "tied"]])


def build():
    """Each pick, with its price, its model chance and its six figures."""
    board = pd.read_csv(BOARD)
    per = _season_frame()
    out = []
    for p in PICKS:
        row = board[(board.sel == p["name"]) & (board.board == p["board"])]
        if len(row) != 1:
            raise SystemExit(f"{p['name']} top {p['board']}: {len(row)} board rows, "
                             "re-run scripts/sb_placings_board.py")
        row = row.iloc[0]
        key = f"{row.player}|{row.club}"
        if key not in per.index or pd.isna(per.at[key, "rank"]):
            raise SystemExit(f"{p['name']}: no season row for {key}")
        x = per.loc[key]
        rank = rank_text(x["rank"], bool(x["tied"]))
        n = int(p["board"])
        keys = p["cells"][:2] + ["cv"] + p["cells"][2:]
        keys.insert(0, "proj")
        if "si" in keys and x.si_n < x.games:
            raise SystemExit(f"{p['name']}: score involvements for {int(x.si_n)} "
                             f"of {int(x.games)} games")
        cells = [(STATS[c][2].format(float(x[STATS[c][0]])), STATS[c][1]) for c in keys]
        out.append(dict(
            key=p["key"], name=p["name"], club=str(row.club), tier=p["tier"],
            board=n, rank=rank, price=f"${row.odds:,.2f}", fair=f"${row.fair:,.2f}",
            model=float(row.p), implied=1.0 / float(row.odds), cells=cells,
            mast="PLACINGS", lead=f"TOP {n} FINISH", qual=f"MODEL RANK {rank}",
            note=("TO FINISH", f"TOP {n}"),
            cover_label=f"{TIER_SHORT[p['tier']]} · TOP {n}",
        ))
    return out


CLOSER = ("THE MODEL RAN THE COUNT",
          f"{SIMS} TIMES, THEN PRICED",
          "EVERY PLACING ON THE BOOK.",
          f"NO {SEASON} VOTE IS PUBLIC",
          f"UNTIL THE COUNT ON {COUNT_DATE.split()[-2].upper()} "
          f"{COUNT_DATE.split()[-1].upper()}.")


# ------------------------------------------------------------------ copy
def caption(picks):
    """Templated, like every other draft in this repo, and for the same reason:
    a templated post cannot invent an accuracy claim under time pressure."""
    out = [
        f"The model ran the {SEASON} count {SIMS} times. Six placings where it "
        "disagrees with the book.",
        "",
        "Three safe, two value, one longshot, across the top 3, top 5, top 10 and "
        "top 20 finish markets. Every home and away game went through the model, "
        "the whole count was simulated from those games, and each runner's chance "
        "of the finish was set against what the book is paying.",
        "",
    ]
    for p in picks:
        out.append(f"{TIER_LABEL[p['tier']].lower()}: {p['name']}, top {p['board']} "
                   f"finish, {p['price']} ({BOOK.title()}), model "
                   f"{p['model'] * 100:.0f}%")
    out += [
        "",
        "The bar on each slide is the model's chance against the chance the "
        "price implies. The gap between them is the whole reason the pick is "
        "on the list.",
        "",
        f"Projected votes and model rank are the decimal board at {DOMAIN}. "
        "Games as favourite counts the games where he is the model's most likely "
        "player to poll the 3, and games likely to poll the ones where it makes "
        "him better than even to poll at all. Coaches BOG counts the games where "
        "he topped the coaches' votes.",
        "",
        "Two things said plainly. This is a model, not a leak: no "
        f"{SEASON} vote is public until the count on {COUNT_DATE}. And prices "
        f"move, so check the current one before you act on any of this. Dead heat "
        f"rules apply to every placing on {BOOK.title()}.",
        "",
        "18+. Gamble responsibly. Set a deposit limit. Think. Is this a bet "
        "you really want to place? For free and confidential support call "
        "1800 858 858 or visit gamblinghelponline.org.au.",
        "",
        "Which one is the model wrong about?",
    ]
    return "\n".join(out)


def write_copy(picks, paths, softs):
    cap, tags = caption(picks), hashtags(picks)
    out = [f"# TikTok carousel, placings, {SEASON}", "",
           "## Caption", "", "```", cap, "", tags, "```", "",
           f"{len(cap) + len(tags) + 2} characters including hashtags. "
           "TikTok's limit is 2,200.", "", "## Slides", "",
           "| # | File | Player | Board | Price | Model | Fair | Model rank |",
           "|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(picks):
        out.append(f"| {i + 2} | `{os.path.basename(paths[i + 1])}` | {p['name']} | "
                   f"Top {p['board']} | {p['price']} | {p['model'] * 100:.0f}% | "
                   f"{p['fair']} | {p['rank']} |")
    out += ["", f"Slide 1 is the cover, slide {len(picks) + 2} is the closer.", "",
            "## Before posting", "",
            "- **Re-check the prices.** Run `sb_placings_board.py`, then this "
            "script. A card showing a price the book is no longer offering is the "
            "one error here that cannot be walked back after posting.",
            f"- **No {SEASON} Brownlow vote is public until the count.** The "
            "closer says so; do not drop it.",
            "- **The model chance comes from the season simulator** in "
            "`sb_placings_board.py`, a rebuild of the 11 September market book's "
            "engine. It is backtested there on 18 walk-forward seasons. That "
            "backtest is internal: the deck claims no accuracy figure and must "
            "not start.",
            "- **The value on these boards sits at long prices**, which is the "
            "direction the umpires' new access to stats would hurt if it makes "
            "votes follow the stat sheet more closely. No backtest season covers "
            "that regime.",
            "- **SAFE here means 37 to 48%**, not the 70 to 82% of the 3 vote "
            "deck. Kept on purpose so the series reads as one; the bar shows the "
            "real figure.",
            "- **Projected votes and model rank are the decimal board**, the "
            "site's PROJECTED VOTES. Rank is minimum-on-ties over the one-decimal "
            "figure across every player, with = where shared.",
            "- **Games as favourite** is the model's fitted P(3), the game's "
            "highest. **Games likely to poll** is a fitted poll chance of 50% "
            "or more. **Coaches BOG** is the most coaches votes in his game, "
            "ties counted for each player. Score involvements is the real "
            "footywire stat, never the engineered column.",
            f"- Dead heat rules apply on {BOOK.title()} and are priced in.",
            f"- Everything a reader must see sits between y {SAFE_TOP} and "
            f"y {SAFE_BOT}, because TikTok centre-crops a carousel image."]
    for n, sc in softs:
        out.append(f"- {n}'s headshot is upscaled {sc:.1f} times and will look "
                   f"soft on a phone.")
    path = os.path.join(REPO, "drafts", f"tiktok_placings_{SEASON}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="render one pick by key, or 'cover' / 'closer'")
    ap.add_argument("--no-phone", action="store_true",
                    help="skip the copy into the OneDrive folder")
    a = ap.parse_args()
    os.chdir(REPO)

    picks = build()
    sub = "TOP 3, 5, 10 AND 20"
    if a.only:
        one = [p for p in picks if p["key"] == a.only]
        if a.only == "cover":
            print(save(draw_cover(picks, sub), os.path.join(OUT_DIR, "01_cover.png")))
        elif a.only == "closer":
            print(save(draw_closer(CLOSER), os.path.join(OUT_DIR, "99_closer.png")))
        elif one:
            img, _ = draw_slide(one[0])
            print(save(img, os.path.join(OUT_DIR, f"only_{a.only}.png")))
        else:
            raise SystemExit(f"no pick keyed {a.only!r}; "
                             f"have {[p['key'] for p in picks]}")
        return

    paths, softs = [save(draw_cover(picks, sub), os.path.join(OUT_DIR, "01_cover.png"))], []
    for i, p in enumerate(picks):
        img, soft = draw_slide(p)
        paths.append(save(img, os.path.join(
            OUT_DIR, f"{i + 2:02d}_{p['tier'].lower()}_{p['key']}.png")))
        if soft and soft > 1.8:
            softs.append((p["name"], soft))
    paths.append(save(draw_closer(CLOSER),
                      os.path.join(OUT_DIR, f"{len(picks) + 2:02d}_closer.png")))

    copy = write_copy(picks, paths, softs)
    print(f"  {len(paths)} slides to {OUT_DIR}")
    print(f"  copy: {copy}")
    for p in picks:
        print(f"  {p['tier']:8s} {p['name']:20s} top {p['board']:<2} {p['price']:>7} "
              f"model {p['model']:.1%}  rank {p['rank']}")

    if not a.no_phone:
        os.makedirs(PHONE_SUB, exist_ok=True)
        for p in paths:
            shutil.copy2(p, os.path.join(PHONE_SUB, os.path.basename(p)))
        print(f"  copied to {PHONE_SUB}")


if __name__ == "__main__":
    main()
