# -*- coding: utf-8 -*-
"""The To Poll a Vote picks as a TikTok photo carousel, one slide per selection.

    python scripts/sb_poll_board.py               # refresh the prices first
    python scripts/tiktok_poll.py                 # cover + 6 picks + closer
    python scripts/tiktok_poll.py --only laird    # one slide, while iterating

Writes 1080x1920 PNGs to `drafts/tiktok_poll/` (gitignored), copies them to
`OneDrive/Pictures/ChaChing Slides/` with a `poll_` prefix so they cannot
overwrite the 3 vote deck's files of the same names, and writes the draft copy
to `drafts/tiktok_poll_<season>.md`. It never posts.

THE SAME DECK AS tiktok_market.py, FOR A SEASON MARKET
Layout, wash, cutout, tier chips and closer are that script's and are imported
from it rather than copied, so the two decks stay one design. What changes is
what a slide is about. A 3 vote pick is one game; a poll-a-vote pick is a whole
season, so the line under the name carries games played and the model's
projected votes where the round and fixture used to sit. Below the price bar,
where the 3 vote deck has its stat grid, sit the one or two games he is most
likely to poll in, each with his chance in that game and what he did in it.

EVERY FIGURE IS READ, NONE IS TYPED
Price and model chance come from `data_betting/sb_poll_board.csv`, which
`sb_poll_board.py` writes. A pick names a player, a tier and which stats to show.
The build REFUSES a pick whose edge has gone since the board was last fetched,
because prices move and a slide arguing for a price the book no longer offers
is the one error that cannot be walked back after posting.
"""

import argparse
import os
import shutil
import sys

import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from afl_headshots import head                                     # noqa: E402
from sb_3vote_board import _dashboard_ns                           # noqa: E402
from countdown_card import BG, EMERALD, INK, MUTED, GOLD, LINE, S, font  # noqa: E402
from tiktok_market import (                                        # noqa: E402
    BOOK, COUNT_DATE, CUT_BOT, CUT_TOP, PHONE_DIR, TIER_COL, TIER_LABEL,
    draw_closer, masthead, pill, place_cut, save, wash,
)
from tiktok_top10 import (                                         # noqa: E402
    W, H, M, SAFE_TOP, SAFE_BOT, BAR, DOMAIN, accent, fit_font, _initials,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(REPO, "data_betting", "sb_poll_board.csv")
GAME_LEVEL = os.path.join(REPO, "predictions", "game_level_2026.csv")
OUT_DIR = os.path.join(REPO, "drafts", "tiktok_poll")
PHONE_PREFIX = "poll_"
SEASON = 2026
MARKET = "TO POLL A VOTE"

# The figures a game row can carry: column in game_level, label. Integers,
# because they are one game's counts, not averages.
GAME_STATS = {
    "disp":    ("Disposals", "DISPOSALS"),
    "cv":      ("Coaches_Votes", "COACHES VOTES"),
    "clear":   ("Clearances", "CLEARANCES"),
    "tackles": ("Tackles", "TACKLES"),
    "marks":   ("Marks", "MARKS"),
    "hitouts": ("Hit.Outs", "HITOUTS"),
    "goals":   ("Goals", "GOALS"),
}

# WHICH GAMES A SLIDE HIGHLIGHTS. A game counts as one he is expected to poll
# in when the model gives him at least LIVE_GAME there, up to MAX_GAMES of
# them in round order; a player with none still shows his single best chance.
# The chance is the within-game fitted P(1) + P(2) + P(3), used as it is:
# across the 18 walk-forward seasons it lands within about a point of the
# realised rate in every band from 5% to 100%, and an isotonic map on top
# scored slightly WORSE leave-one-season-out, so there is no correction layer.
LIVE_GAME = 0.20
MAX_GAMES = 2

# Chosen off sb_poll_board.csv on 18 September 2026. Every pick clears the
# market book's own back rule: at least +15% on the model, still positive when
# blended halfway to Wheelo's expected votes, and at least a 15% chance. Tiers
# are by the model's chance, not by price: safe 70%+, value 45 to 70%,
# longshot under 45%. Within a tier, ranked by the smaller of the two edges.
# `stats` is what each highlighted game row shows: disposals and coaches votes
# on every slide, then the one figure that is the player's own case.
PICKS = [
    dict(key="crisp", name="Jack Crisp", tier="SAFE",
         stats=["disp", "cv", "tackles"]),
    dict(key="setterfield", name="Will Setterfield", tier="SAFE",
         stats=["disp", "cv", "clear"]),
    dict(key="laird", name="Rory Laird", tier="SAFE",
         stats=["disp", "cv", "marks"]),
    dict(key="byrnejones", name="Darcy Byrne-Jones", tier="VALUE",
         stats=["disp", "cv", "marks"]),
    dict(key="mcandrew", name="Lachlan McAndrew", tier="VALUE",
         stats=["disp", "cv", "hitouts"]),
    dict(key="nash", name="Conor Nash", tier="LONGSHOT",
         stats=["disp", "cv", "clear"]),
]


def _display_round(rn):
    """The AFL's round, from AFLTables' raw Round_num. 2026 runs one ahead."""
    return "Opening Round" if rn == 1 else f"Round {rn - 1}"


# ------------------------------------------------------------------ data
def build():
    board = pd.read_csv(BOARD)
    g = pd.read_csv(GAME_LEVEL, low_memory=False).drop_duplicates(
        subset=["Game_ID", "Player_Name"])
    # Fitted within each game so the 3, the 2 and the 1 are each handed out
    # once. Raw Poll_Prob is scored row by row and a game's column can sum to
    # well past three votes' worth, so it is never shown as a chance.
    g = _dashboard_ns()["_fit_game_probs"](g)
    g["poll_game"] = g.P_1_game + g.P_2_game + g.P_3_game

    out = []
    for p in PICKS:
        row = board[board.player == p["name"]]
        if len(row) != 1:
            raise SystemExit(f"{p['name']}: {len(row)} board rows, "
                             "re-run scripts/sb_poll_board.py")
        row = row.iloc[0]
        if not row.ev > 0:
            raise SystemExit(f"{p['name']}: no edge left at ${row.odds:.2f} "
                             f"(model {row.p:.0%}). Re-choose the pick.")
        gm = g[(g.Player_Name == p["name"]) & (g["Playing.for"] == row.club)]

        ranked = gm.sort_values("poll_game", ascending=False)
        live = ranked[ranked.poll_game >= LIVE_GAME].head(MAX_GAMES)
        pick = (live if len(live) else ranked.head(1)).sort_values("Round_num")
        games = []
        for _, x in pick.iterrows():
            opp = x["Away.team"] if x["Playing.for"] == x["Home.team"] else x["Home.team"]
            games.append(dict(
                round=_display_round(int(x.Round_num)), opp=opp,
                chance=float(x.poll_game),
                stats=[(f"{float(x[GAME_STATS[s][0]]):.0f}", GAME_STATS[s][1])
                       for s in p["stats"]],
            ))

        out.append(dict(
            key=p["key"], name=p["name"], club=str(row.club), tier=p["tier"],
            games=len(gm), proj=float(gm.Exp_Votes.sum()),
            price=f"${row.odds:,.2f}", fair=f"${row.fair:,.2f}",
            model=float(row.p), implied=float(row.implied), ev=float(row.ev),
            highlight=games,
        ))
    return out


# ------------------------------------------------------------------ drawing
# The game rows are this deck's reason to exist, so they get the height. The
# cutout band gives up LIFT px against the 3 vote deck's and everything under
# it moves up by the same, which is what lets two rows of large type end
# inside the crop's 1500 floor. Every y below is the 3 vote deck's minus LIFT.
LIFT = 24
CUT_END = CUT_BOT - LIFT


def draw_slide(p):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S
    acc = accent(p["club"])
    soft = None

    wash(img, p["club"], CUT_END * S)
    photo = head(p["name"])
    if photo:
        with Image.open(photo) as im:
            soft = (CUT_END - CUT_TOP) * S * 0.94 / im.height / S
        place_cut(img, photo, CUT_TOP * S, CUT_END * S)
    else:
        k.text((W * S // 2, (CUT_TOP + CUT_END) // 2 * S), _initials(p["name"]),
               font=font("display", 120), fill=INK, anchor="mm")
    k.line([0, CUT_END * S, W * S, CUT_END * S], fill=LINE, width=max(1, S))

    masthead(img, k, m, right, MARKET)
    pill(k, m, (CUT_END - 74) * S, TIER_LABEL[p["tier"]], TIER_COL[p["tier"]])

    nm = p["name"].upper()
    k.text((m, 954 * S), nm, font=fit_font(k, nm, "name", 66, right - m), fill=INK)

    # A season market has no round to lead with. Games played takes its place,
    # because it is how many chances he had, and the model's projected votes
    # are the qualifier behind it, in the club colour as the fixture was.
    gl = f"{p['games']} GAMES"
    rf = font("display", 38)
    k.text((m, 1028 * S), gl, font=rf, fill=INK)
    rw = k.textlength(gl, font=rf)
    k.text((m + rw + 20 * S, 1038 * S), f"{p['proj']:.1f} PROJECTED VOTES",
           font=font("display", 24), fill=acc)

    k.text((m, 1088 * S), p["price"], font=font("fig", 100), fill=GOLD)
    fw = k.textlength(p["price"], font=font("fig", 100))
    k.text((m + fw + 24 * S, 1108 * S), "TO POLL", font=font("display", 25), fill=INK)
    k.text((m + fw + 24 * S, 1142 * S), "A VOTE", font=font("display", 25), fill=INK)

    y, bh = 1216 * S, 16 * S
    k.rectangle([m, y, right, y + bh], fill=BAR)
    span = right - m
    k.rectangle([m, y, m + int(span * p["model"]), y + bh], fill=EMERALD)
    tick = m + int(span * p["implied"])
    k.rectangle([tick - 2 * S, y - 8 * S, tick + 2 * S, y + bh + 8 * S], fill=GOLD)
    k.text((m, y + bh + 12 * S), "MODEL %.0f%%" % (p["model"] * 100),
           font=font("display", 23), fill=EMERALD)
    k.text((right, y + bh + 12 * S), "PRICE IMPLIES %.0f%%" % (p["implied"] * 100),
           font=font("display", 23), fill=GOLD, anchor="ra")

    game_rows(k, m, right, p["highlight"], acc)
    return img, soft


# Type sizes for the game rows. Two games share the 200px between the price
# bar and the crop floor; one game gets all of it, so it sets larger and sits
# centred in the space instead of leaving the bottom half of it empty.
ROW_TWO = dict(y=1300, pitch=100, top=42, bot=84, rnd=44, opp=28, pct=58,
               poll=20, val=30, lab=22, gap=32)
ROW_ONE = dict(y=1318, pitch=0, top=62, bot=132, rnd=60, opp=36, pct=84,
               poll=26, val=42, lab=28, gap=40)


def _fit(k, parts, room, floor=0.7):
    """The largest scale, 1.0 down to `floor`, at which `parts` fit in `room`.

    parts is [(text, font kind, size, space after)]. A long opponent or a
    wide stat label shrinks its own line rather than running into the
    percentage on the right.
    """
    sc = 1.0
    while sc > floor:
        w = sum(k.textlength(t, font=font(kind, round(sz * sc))) + gap * sc * S
                for t, kind, sz, gap in parts)
        if w <= room:
            break
        sc -= 0.04
    return sc


def game_rows(k, m, right, games, acc):
    """One row per highlighted game: which game, his chance in it, what he did.

    Laid out like the price bar above it, the name of the thing on the left and
    the model's figure on the right, so the eye runs down one column of
    percentages. Everything sits on two shared BASELINES per row rather than
    on top edges, because the row mixes four type sizes and top-aligned mixed
    sizes read as a ragged line. Two rows end at y 1484 and one at y 1450,
    both inside the 1500 floor.
    """
    z = ROW_ONE if len(games) == 1 else ROW_TWO
    for i, gm in enumerate(games):
        y0 = z["y"] + i * z["pitch"]
        top, bot = (y0 + z["top"]) * S, (y0 + z["bot"]) * S   # the two baselines
        if i:
            # The gap between rows is barely wider than the gap inside one, so
            # without a rule the second round's stats read as the first's.
            k.line([m, (y0 - 3) * S, right, (y0 - 3) * S], fill=LINE, width=max(1, S))

        pct = "%.0f%%" % (gm["chance"] * 100)
        pf = font("fig", z["pct"])
        k.text((right, top), pct, font=pf, fill=EMERALD, anchor="rs")
        pl = font("display", z["poll"])
        k.text((right, bot), "TO POLL", font=pl, fill=MUTED, anchor="rs")

        rd, opp = gm["round"].upper(), f"v {gm['opp']}".upper()
        sc = _fit(k, [(rd, "display", z["rnd"], 18), (opp, "display", z["opp"], 0)],
                  right - m - k.textlength(pct, font=pf) - 28 * S)
        rf = font("display", round(z["rnd"] * sc))
        k.text((m, top), rd, font=rf, fill=INK, anchor="ls")
        k.text((m + k.textlength(rd, font=rf) + 18 * sc * S, top), opp,
               font=font("display", round(z["opp"] * sc)), fill=acc, anchor="ls")

        parts = []
        for val, label in gm["stats"]:
            parts += [(val, "display", z["val"], 9), (label, "display", z["lab"], z["gap"])]
        parts[-1] = parts[-1][:3] + (0,)
        sc = _fit(k, parts, right - m - k.textlength("TO POLL", font=pl) - 28 * S)
        vf = font("display", round(z["val"] * sc))
        lf = font("display", round(z["lab"] * sc))
        x = m
        for val, label in gm["stats"]:
            k.text((x, bot), val, font=vf, fill=INK, anchor="ls")
            x += k.textlength(val, font=vf) + 9 * sc * S
            k.text((x, bot), label, font=lf, fill=MUTED, anchor="ls")
            x += k.textlength(label, font=lf) + z["gap"] * sc * S


def draw_cover(picks):
    """tiktok_market's cover with this market's name in the emerald line."""
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S
    rule = 812
    wash(img, "Cha Ching", rule * S)
    masthead(img, k, m, right, f"{SEASON} MODEL")

    lines = ("BEST PICKS FOR", "THE BROWNLOW")
    tf = min((fit_font(k, ln, "display", 96, right - m) for ln in lines),
             key=lambda f: f.size)
    for i, ln in enumerate(lines):
        k.text((m, (500 + i * 104) * S), ln, font=tf, fill=INK)
    k.text((m, 722 * S), MARKET,
           font=fit_font(k, MARKET, "display", 52, right - m), fill=EMERALD)
    k.line([m, rule * S, right, rule * S], fill=LINE, width=max(1, S))

    cw = (right - m) / 3
    for i, p in enumerate(picks):
        cx = m + cw * (i % 3)
        yy = (866 + (i // 3) * 206) * S
        k.text((cx, yy), p["price"], font=fit_font(k, p["price"], "fig", 72, cw - 24 * S),
               fill=GOLD)
        k.text((cx, yy + 92 * S), TIER_LABEL[p["tier"]], font=font("display", 22),
               fill=MUTED)

    k.text((right, 1296 * S), "SWIPE", font=font("display", 32), fill=EMERALD,
           anchor="ra")
    return img


# ------------------------------------------------------------------ copy
def caption(picks):
    """Templated, like every other draft in this repo: a templated post cannot
    invent an accuracy claim under time pressure."""
    out = [
        "Six Brownlow players to poll a vote, priced by the model.",
        "",
        f"Three safe, two value, one longshot. Every home and away game of the "
        f"{SEASON} season went through the model, which then simulated the whole "
        "count to get each player's chance of polling at least one vote. That "
        f"chance was then set against every price on the {BOOK.title()} board.",
        "",
    ]
    for p in picks:
        hl = p["highlight"]
        games = ", ".join(f"{g['round'].lower()} v {g['opp']} ({g['chance'] * 100:.0f}%)"
                          for g in hl)
        out.append(f"{TIER_LABEL[p['tier']].lower()}: {p['name']}, {p['price']} "
                   f"({BOOK.title()}), model {p['model'] * 100:.0f}%. "
                   f"{'Best chances' if len(hl) > 1 else 'Best chance'}: {games}.")
    out += [
        "",
        "The bar on each slide is the model's chance against the chance the "
        "price implies. The gap between them is the whole reason the pick is "
        "on the list. Under it are the games he is most likely to poll in, "
        "with the model's chance for that game on its own.",
        "",
        "Two things said plainly. This is a model, not a leak: no "
        f"{SEASON} vote is public until the count on {COUNT_DATE}. And prices "
        "move, so check the current one before you act on any of this.",
        "",
        f"The full board, every player and every game, is at {DOMAIN}.",
        "",
        "18+. Gamble responsibly. Set a deposit limit. Think. Is this a bet "
        "you really want to place? For free and confidential support call "
        "1800 858 858 or visit gamblinghelponline.org.au.",
        "",
        "Which one is the model wrong about?",
    ]
    return "\n".join(out)


def hashtags(picks):
    tags = ["#brownlow", "#brownlowmedal", f"#brownlow{SEASON}", "#afl",
            f"#afl{SEASON}", "#aflfooty", "#footy", "#aussierules",
            "#aflpredictions", "#brownlowpredictions", "#sportsanalytics"]
    for p in picks:
        t = "#" + "".join(ch for ch in p["name"].lower() if ch.isalnum())
        if t not in tags:
            tags.append(t)
    return " ".join(tags)


def write_copy(picks, paths, softs):
    cap, tags = caption(picks), hashtags(picks)
    out = [f"# TikTok carousel, to poll a vote, {SEASON}", "",
           "## Caption", "", "```", cap, "", tags, "```", "",
           f"{len(cap) + len(tags) + 2} characters including hashtags. "
           "TikTok's limit is 2,200.", "", "## Slides", "",
           "| # | File | Player | Club | Games | Price | Model | Fair | Edge "
           "| Highlighted |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(picks):
        out.append(f"| {i + 2} | `{os.path.basename(paths[i + 1])}` | {p['name']} | "
                   f"{p['club']} | {p['games']} | {p['price']} | "
                   f"{p['model'] * 100:.0f}% | {p['fair']} | {p['ev']:+.0%} | "
                   + "; ".join(f"{g['round']} v {g['opp']} {g['chance'] * 100:.0f}%"
                               for g in p["highlight"]) + " |")
    out += ["", f"Slide 1 is the cover, slide {len(picks) + 2} is the closer.", "",
            "## Before posting", "",
            f"- **Re-check the prices.** Run `python scripts/sb_poll_board.py` "
            "then this script. The build refuses any pick whose edge has gone, "
            "but a price that has merely shortened still renders, so compare "
            "the slide against the app.",
            "- **The model chance is NOT the per-game P(3) the 3 vote deck "
            "uses.** A 1+ vote market is a season question: the unsharpened "
            "3-2-1 season simulator, then an isotonic map fitted on the 18 "
            "walk-forward seasons. The map is a step function, which is why "
            "all three safe picks read 77%. That is not a copy error.",
            "- **2026 is the first season umpires see the stats.** Every "
            "calibration here is fitted on seasons before that. If votes now "
            "follow the stat sheet more closely, fringe players poll less often "
            "than history says, and the value picks and the longshot are the "
            "ones exposed. The deck claims no accuracy figure and must not start.",
            "- **Sportsbet lists one \"Bailey Williams\" and two played in "
            "2026.** The runner is refused rather than guessed, so it is not "
            "priced and cannot be a pick.",
            "- **No 2026 Brownlow vote is public until the count.** Every slide "
            "carries the model label in the masthead; do not crop it off.",
            "- **The highlighted games.** Every game where the model gives him "
            f"{LIVE_GAME:.0%} or better, at most {MAX_GAMES}, in round order; a "
            "player with none shows his single best chance. The game chance is "
            "the within-game fitted P(1) + P(2) + P(3), used with no correction "
            "because it held its rate in every backtest band.",
            "- **The game chances do not multiply out to the season figure.** "
            "The season figure goes through its own calibration, which pulls "
            "fringe players down; the game chance needed none. Compounded over "
            "every game, Byrne-Jones reads 64% against his season 55%. Both are "
            "shown as the model gives them.",
            "- Round numbers are the AFL's, one behind the raw AFLTables number "
            "the CSVs carry.",
            f"- Everything a reader must see sits between y {SAFE_TOP} and "
            f"y {SAFE_BOT}, because TikTok centre-crops a carousel image.",
            f"- Phone copies carry a `{PHONE_PREFIX}` prefix so they sit beside "
            "the 3 vote deck's files rather than overwriting them."]
    for n, sc in softs:
        out.append(f"- {n}'s headshot is upscaled {sc:.1f} times and will look "
                   f"soft on a phone.")
    path = os.path.join(REPO, "drafts", f"tiktok_poll_{SEASON}.md")
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
    if a.only:
        one = [p for p in picks if p["key"] == a.only]
        if a.only == "cover":
            print(save(draw_cover(picks), os.path.join(OUT_DIR, "01_cover.png")))
        elif a.only == "closer":
            print(save(draw_closer(), os.path.join(OUT_DIR, "99_closer.png")))
        elif one:
            img, _ = draw_slide(one[0])
            print(save(img, os.path.join(OUT_DIR, f"only_{a.only}.png")))
        else:
            raise SystemExit(f"no pick keyed {a.only!r}; "
                             f"have {[p['key'] for p in picks]}")
        return

    paths, softs = [], []
    paths.append(save(draw_cover(picks), os.path.join(OUT_DIR, "01_cover.png")))
    for i, p in enumerate(picks):
        img, soft = draw_slide(p)
        paths.append(save(img, os.path.join(
            OUT_DIR, f"{i + 2:02d}_{p['tier'].lower()}_{p['key']}.png")))
        if soft and soft > 1.8:
            softs.append((p["name"], soft))
    paths.append(save(draw_closer(),
                      os.path.join(OUT_DIR, f"{len(picks) + 2:02d}_closer.png")))

    copy = write_copy(picks, paths, softs)
    print(f"  {len(paths)} slides to {OUT_DIR}")
    print(f"  copy: {copy}")

    if not a.no_phone:
        os.makedirs(PHONE_DIR, exist_ok=True)
        for p in paths:
            shutil.copy2(p, os.path.join(PHONE_DIR, PHONE_PREFIX + os.path.basename(p)))
        print(f"  copied to {PHONE_DIR}")


if __name__ == "__main__":
    main()
