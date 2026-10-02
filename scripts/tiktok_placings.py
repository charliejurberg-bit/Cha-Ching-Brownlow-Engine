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

import tiktok_market as tm                                         # noqa: E402
from sb_3vote_board import _dashboard_ns                           # noqa: E402
from countdown_card import (                                       # noqa: E402
    BG, EMERALD, GOLD, INK, LINE, MUTED, S, font,
)
from tiktok_market import (                                        # noqa: E402
    BOOK, COUNT_DATE, PHONE_DIR, SEASON, TIER_LABEL, accent, add_no_odds_arg,
    backdrop, blur_text, caption_len, draw_closer, draw_slide, hashtags,
    masthead, odds_paths, order_picks, prob_bar, prune, rg_line, save,
    set_no_odds, slide_stem, tier_for, tier_split,
)
from tiktok_top10 import (                                         # noqa: E402
    DOMAIN, M, SAFE_BOT, SAFE_TOP, W, H, fit_font, rank_text,
)
from PIL import Image, ImageDraw                                   # noqa: E402

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

# Player, board, and the four cells that are his own case (slots 1, 2, 4 and
# 5). Everything else is read, INCLUDING THE TIER: tiktok_market.tier_for
# derives it from the price, so the chip cannot contradict the figure beside it.
#
# THREE PER BAND, AND THE THREE ARE THE THREE BIGGEST EDGES IN IT
# Re-chosen 19 September 2026 off sb_placings_board.csv, by the rule the 3 vote
# deck uses: drop refused rows, require at least a 15% chance and at least +15%
# on the model, one pick per player at his own biggest edge, then take the top
# by edge in each band.
#
# THE SAFE BAND IS CHOSEN ON PROBABILITY, NOT ON EDGE, AND THAT IS DELIBERATE
# Every other pick on every deck is here because the model and the book
# disagree. A safe pick is not: it is here because the model says it lands.
# The deck owner's rule, 19 September 2026, is that a safe pick does not need
# an edge, it needs to be highly likely to get up.
#
# The two things cannot be had at once, and the board says so exactly. Inside
# the $2.00 band: at 80% or better the longest price on offer is $1.11, at 60%
# it is $1.42, and only by dropping to 50% does it reach $1.95. The book
# prices a near-certainty correctly, so every pick below carries NEGATIVE EV,
# from -8.8% to -14.3%. That is the cost of the word "safe" and it is paid
# knowingly.
#
# Two guards on it. SAFE_MIN_P is what "highly likely" means, so the rule is
# checkable rather than a feel; and SAFE_MIN_PRICE stops a refresh putting
# Daicos at $1.001 on a slide, where a 100% chance returns a tenth of a cent
# in the dollar and the thing is not a bet at all.
#
# THE COPY MUST NOT CLAIM AN EDGE THESE DO NOT HAVE. The caption used to say
# the gap between model and price "is the whole reason the pick is on the
# list", which is now true of six picks and false of three. It has been split
# in two. The slide needs no special case: its bar draws the model against the
# price honestly, so a safe pick renders with the price ahead, which is the
# truth about it.
SAFE_MIN_P = 0.80
SAFE_MIN_PRICE = 1.05
#
# Ordered by ascending price, so the deck escalates and ends on the $71.
PICKS = [
    dict(key="sheezel", name="Harry Sheezel", board=20,
         cells=["disp", "d30", "fav", "si"]),
    dict(key="ashcroft", name="Will Ashcroft", board=10,
         cells=["fav", "bog", "disp", "poll50"]),
    dict(key="baileysmith", name="Bailey Smith", board=3,
         cells=["disp", "d30", "poll50", "cp"]),
    dict(key="walsh", name="Sam Walsh", board=20,
         cells=["disp", "d30", "bog", "games"]),
    dict(key="hornefrancis", name="Jason Horne-Francis", board=10,
         cells=["clr", "goals", "poll50", "bog"]),
    dict(key="neale", name="Lachie Neale", board=5,
         cells=["disp", "d30", "cp", "bog"]),
    dict(key="bolton", name="Shai Bolton", board=20,
         cells=["si", "goals", "bog", "fav"]),
    dict(key="sparrow", name="Tom Sparrow", board=20,
         cells=["clr", "goals", "cp", "games"]),
    dict(key="oliver", name="Clayton Oliver", board=10,
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
            key=p["key"], name=p["name"], club=str(row.club),
            tier=tier_for(row.odds),
            board=n, rank=rank, price=f"${row.odds:,.2f}", fair=f"${row.fair:,.2f}",
            model=float(row.p), implied=1.0 / float(row.odds), cells=cells,
            mast="PLACINGS", lead=f"TOP {n} FINISH", qual=f"MODEL RANK {rank}",
            note=("TO FINISH", f"TOP {n}"),
            cover_label=((f"TOP {n} FINISH") if tm.NO_ODDS else
                         (f"{TIER_SHORT[tier_for(row.odds)]}  ·  "
                          f"TOP {n} FINISH")),
        ))
    return out


# ------------------------------------------------------------------ cover
# THIS DECK GETS ITS OWN COVER, NOT tiktok_market's SLIP
# The 3 vote and poll decks both open on the blurred slip, and three decks
# opening on the same object read as one post published three times. This one
# has something neither of those has: a pick here is a FINISHING POSITION, and
# the six sit across three different boards. Grouping them under the board each
# is backed for says what the deck is before a word of it is read.
#
# Names are blurred exactly as on the slip: the board, the price and the club
# colour are the tease, and the names are the only thing a reader cannot work
# out for himself.
LADDER_TOP, LADDER_BOT = 686, 1412
# Nominal geometry and type. The whole ladder is scaled down from these when
# the picks do not fit; nothing here is a hard size.
BAND_HEAD, BAND_GAP, ROW_PITCH = 50, 18, 74
F_BOARD, F_COUNT, F_NAME, F_PRICE = 30, 22, 26, 38
MIN_SCALE = 0.68
NAME_BLUR, NAME_BLUR_GAIN = 0.30, 2.6


def _ladder_scale(n_bands, n_rows):
    """One factor applied to every height and every type size on the ladder.

    THE LADDER MUST SHRINK AS A WHOLE, NOT ROW BY ROW. The first version
    solved only for row pitch and clamped it to a minimum, which is a
    contradiction: clamping is exactly what stops it fitting. At three bands
    and seven picks it was fine; adding the safe tier took it to four bands
    and nine picks, the clamp held the pitch at its floor, and the last band
    ran straight through the footer.

    Scaling the band header, the gap, the pitch and the four type sizes
    together keeps the proportions, so a fuller ladder reads as the same
    object set smaller rather than as a squashed one.
    """
    room = LADDER_BOT - LADDER_TOP
    need = (n_bands * BAND_HEAD + (n_bands - 1) * BAND_GAP + n_rows * ROW_PITCH)
    sc = max(MIN_SCALE, min(1.0, room / need))
    # MIN_SCALE is a legibility floor, so past it the ladder cannot fit and
    # scaling further would only make it unreadable as well as overflowing.
    # Say so: a cover running through its own footer is the kind of fault that
    # is obvious in the file and invisible in a build log. Roughly ten picks
    # across four boards is the ceiling for this layout.
    if need * sc > room:
        print(f"  WARNING: ladder needs {need * sc:.0f}px of {room}px for "
              f"{n_rows} picks across {n_bands} boards. The cover will "
              f"overflow. Drop a pick or raise MIN_SCALE deliberately.")
    return sc


def _boards_upper(picks):
    """"TOP 5, 10 AND 20", off the picks themselves."""
    ns = [str(n) for n in sorted({int(q["board"]) for q in picks})]
    return "TOP " + (", ".join(ns[:-1]) + " AND " + ns[-1]
                     if len(ns) > 1 else ns[0])


def draw_cover(picks, sub=None):
    """The six grouped by the board each one is backed to finish inside."""
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S

    backdrop(img, int(W * 0.50 * S), 1000 * S)
    masthead(img, k, m, right, f"{SEASON} MODEL")

    tl = ("WHERE DOES HE", "FINISH?")
    tf = min((fit_font(k, ln, "display", 78, right - m) for ln in tl),
             key=lambda f: f.size)
    for i, ln in enumerate(tl):
        k.text((m, (SAFE_TOP + 54 + i * 80) * S), ln, font=tf, fill=INK)
    k.text((m, (SAFE_TOP + 218) * S),
           sub or f"{len(picks)} PLACINGS THE MODEL LIKES",
           font=font("display", 28), fill=GOLD)

    # Only boards that actually carry a pick get a band. A TOP 3 rail with
    # nothing on it reads as a rendering fault, not as an empty market.
    boards = sorted({int(q["board"]) for q in picks})
    by = {n: [q for q in picks if int(q["board"]) == n] for n in boards}
    sc = _ladder_scale(len(boards), len(picks))
    head, gap, pitch = BAND_HEAD * sc, BAND_GAP * sc, ROW_PITCH * sc
    f_board, f_count = font("display", round(F_BOARD * sc)), font("display", round(F_COUNT * sc))
    f_price = font("fig", round(F_PRICE * sc))

    y = LADDER_TOP * S
    for n in boards:
        rows = by[n]
        bh = (head + pitch * len(rows)) * S
        k.rectangle([m, y, right, y + bh], fill="#0c141c", outline=LINE,
                    width=max(1, S))
        k.rectangle([m, y, m + 6 * S, y + bh], fill=GOLD)
        k.text((m + 24 * S, y + head / 2 * S), f"TOP {n} FINISH",
               font=f_board, fill=INK, anchor="lm")
        k.text((right - 24 * S, y + head / 2 * S),
               f"{len(rows)} PICK{'S' if len(rows) > 1 else ''}",
               font=f_count, fill=MUTED, anchor="rm")
        for i, q in enumerate(rows):
            mid = y + (head + pitch * i + pitch / 2) * S
            k.rectangle([m + 24 * S, mid - 19 * sc * S, m + 29 * S,
                         mid + 19 * sc * S], fill=accent(q["club"]))
            nm = q["name"].upper()
            nf = fit_font(k, nm, "display", round(F_NAME * sc), 300 * S)
            blur_text(img, (m + 46 * S, mid), nm, nf, INK,
                      max(2, round(nf.size * NAME_BLUR)),
                      anchor="lm", gain=NAME_BLUR_GAIN)
            fig = ("%.0f%%" % (q["model"] * 100)) if tm.NO_ODDS else q["price"]
            k.text((right - 24 * S, mid), fig, font=f_price,
                   fill=EMERALD if tm.NO_ODDS else GOLD, anchor="rm")
            prob_bar(k, right - 300 * S, right - 150 * S, mid - 4 * S,
                     q["model"], q["implied"], h=8)
        y += bh + gap * S

    k.text((m, 1436 * S),
           f"{SEASON} MODEL PROJECTION" if tm.NO_ODDS else f"PRICES {BOOK}",
           font=font("display", 19), fill=MUTED)
    k.text((right, 1436 * S), "SWIPE FOR THE NAMES", font=font("display", 20),
           fill=EMERALD, anchor="ra")
    if not tm.NO_ODDS:
        rg_line(k, m, 1472 * S)
    return img


CLOSER = ("THE MODEL RAN THE COUNT",
          f"{SIMS} TIMES, THEN PRICED",
          "EVERY PLACING ON THE BOOK.",
          f"NO {SEASON} VOTE IS PUBLIC",
          f"UNTIL THE COUNT ON {COUNT_DATE.split()[-2].upper()} "
          f"{COUNT_DATE.split()[-1].upper()}.")
CLOSER_CLEAN = ("THE MODEL RAN THE COUNT",
                f"{SIMS} TIMES, THEN COUNTED",
                "WHERE EVERY PLAYER FINISHED.",
                f"NO {SEASON} VOTE IS PUBLIC",
                f"UNTIL THE COUNT ON {COUNT_DATE.split()[-2].upper()} "
                f"{COUNT_DATE.split()[-1].upper()}.")


# ------------------------------------------------------------------ copy
def _board_list(picks):
    """"top 5, top 10 and top 20", off the picks themselves."""
    bs = [f"top {n}" for n in sorted({int(p["board"]) for p in picks})]
    return ", ".join(bs[:-1]) + (" and " + bs[-1] if len(bs) > 1 else bs[0])


def caption(picks):
    """Templated, like every other draft in this repo, and for the same reason:
    a templated post cannot invent an accuracy claim under time pressure."""
    if tm.NO_ODDS:
        # No book, no price, no tier, no dead-heat rule and no responsible
        # gambling block: on a post with no market on it the 18+ line tells a
        # classifier the post is about betting. See tiktok_market.NO_ODDS.
        out = [
            f"The model ran the {SEASON} Brownlow count {SIMS} times. Here is "
            f"where it has {len(picks)} players finishing.",
            "",
            f"Across the {_board_list(picks)} finish markets. Every home and "
            "away game went through the model, the whole count was simulated "
            "from those games, and this is how often each player landed "
            "inside the finish.",
            "",
        ]
        for q in picks:
            out.append(f"{q['name']}, top {q['board']}, "
                       f"{q['model'] * 100:.0f}%")
        out += [
            "",
            "The bar on each slide is that chance. Projected votes and model "
            f"rank are the decimal board at {DOMAIN}. Games as favourite: the "
            "model's most likely player to poll the 3. Games likely to poll: "
            "better than even to poll at all. Coaches BOG: he topped the "
            "coaches' votes.",
            "",
            "This is a model, not a leak: no "
            f"{SEASON} vote is public until the count on {COUNT_DATE}.",
            "",
            "Which one has the model got wrong?",
        ]
        return "\n".join(out)

    out = [
        # COUNTED, and no longer claiming all of them disagree with the book:
        # the safe picks are chosen on probability and the book has those
        # about right. It said "Six placings where it disagrees with the
        # book" while nine were on the deck and three of the nine agreed.
        f"The model ran the {SEASON} count {SIMS} times. Here are "
        f"{len(picks)} Brownlow placings worth a look.",
        "",
        # The boards are COUNTED off the picks, never listed by hand. This
        # line asserted "top 3, top 5, top 10 and top 20" while no pick sat on
        # the top 3 board at all, which is the same stale-assertion bug the
        # tier split had.
        f"{tier_split(picks).capitalize()}, across the "
        f"{_board_list(picks)} finish markets, priced off the "
        f"{BOOK.title()} board. Every home and away game went through the "
        "model, the whole count was simulated from those games, and each "
        "chance was set against the price.",
        "",
    ]
    for p in picks:
        # NINE picks, so the per-pick line is as short as it can be while
        # staying searchable. The book is named once above instead of nine
        # times here, which is 117 characters of a 362 character overrun.
        out.append(f"{TIER_LABEL[p['tier']].lower()}: {p['name']}, top "
                   f"{p['board']}, {p['price']}, model {p['model'] * 100:.0f}%")
    out += [
        "",
        # THE TWO KINDS OF PICK ARE DESCRIBED SEPARATELY, because they are on
        # the list for opposite reasons and one sentence covering both would
        # have to claim an edge the safe picks do not have.
        "The bar on each slide is the model's chance against the chance the "
        "price implies. On the value and longshot picks the model is ahead, "
        "and that gap is why the pick is there.",
        "",
        "The safe picks are the other way round and are not value bets. The "
        "model makes them highly likely to land and the book prices a near "
        "certainty about right, so the price sits ahead. Anchors, not edges.",
        "",
        # Same three definitions, one clause each. The slides use labels a
        # reader cannot infer, so this paragraph has to stay; it does not have
        # to be a paragraph of sentences.
        f"Projected votes and model rank are the decimal board at {DOMAIN}. "
        "Games as favourite: the model's most likely player to poll the 3. "
        "Games likely to poll: better than even to poll at all. Coaches BOG: "
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
           f"{caption_len(cap, tags)} characters including hashtags. "
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
    path = os.path.join(REPO, "drafts", f"tiktok_placings_{SEASON}{'_noodds' if tm.NO_ODDS else ''}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="render one pick by key, or 'cover' / 'closer'")
    add_no_odds_arg(ap)
    ap.add_argument("--no-phone", action="store_true",
                    help="skip the copy into the OneDrive folder")
    a = ap.parse_args()
    set_no_odds(a.no_odds)
    out_dir, phone_sub = odds_paths(OUT_DIR, PHONE_SUB)
    os.chdir(REPO)

    picks = order_picks(build())
    # COUNTED off the picks, like the caption's board list and the tier split.
    # Hard-typed, this read "TOP 3, 5, 10 AND 20" over a ladder with no top 3
    # band on it, because the deck's only top 3 pick left in the re-pick.
    sub = _boards_upper(picks)
    if a.only:
        one = [p for p in picks if p["key"] == a.only]
        if a.only == "cover":
            print(save(draw_cover(picks, sub), os.path.join(out_dir, "01_cover.png")))
        elif a.only == "closer":
            print(save(draw_closer(CLOSER_CLEAN if tm.NO_ODDS else CLOSER), os.path.join(out_dir, "99_closer.png")))
        elif one:
            img, _ = draw_slide(one[0])
            print(save(img, os.path.join(out_dir, f"only_{a.only}.png")))
        else:
            raise SystemExit(f"no pick keyed {a.only!r}; "
                             f"have {[p['key'] for p in picks]}")
        return

    paths, softs = [save(draw_cover(picks, sub), os.path.join(out_dir, "01_cover.png"))], []
    for i, p in enumerate(picks):
        img, soft = draw_slide(p)
        paths.append(save(img, os.path.join(
            out_dir, slide_stem(p, i + 2) + ".png")))
        if soft and soft > 1.8:
            softs.append((p["name"], soft))
    paths.append(save(draw_closer(CLOSER_CLEAN if tm.NO_ODDS else CLOSER),
                      os.path.join(out_dir, f"{len(picks) + 2:02d}_closer.png")))

    copy = write_copy(picks, paths, softs)
    prune([out_dir], {os.path.basename(x) for x in paths})
    print(f"  {len(paths)} slides to {out_dir}")
    print(f"  copy: {copy}")
    for p in picks:
        print(f"  {p['tier']:8s} {p['name']:20s} top {p['board']:<2} {p['price']:>7} "
              f"model {p['model']:.1%}  rank {p['rank']}")

    if not a.no_phone:
        os.makedirs(phone_sub, exist_ok=True)
        for p in paths:
            shutil.copy2(p, os.path.join(phone_sub, os.path.basename(p)))
        prune([phone_sub], {os.path.basename(x) for x in paths})
        print(f"  copied to {phone_sub}")


if __name__ == "__main__":
    main()
