"""How a player polls when he clears a stat line. One square per game.

    python scripts/threshold_votes_card.py "Jason Horne-Francis" 13
    python scripts/threshold_votes_card.py "Jason Horne-Francis" 13 --stat Disposals --line 25

Writes a PNG to drafts/ (gitignored). Same 1200x1500 portrait, palette, fonts
and CHA CHING mark as countdown_card.py, imported rather than restated.

WHY A UNIT CHART AND NOT A PERCENTAGE BAR
The honest problem with "80% poll rate, 46.7% three-vote rate" is that both are
fifteenths. A percentage bar renders 46.7% at the same visual weight whether it
came from 7 of 15 or 700 of 1500, and the reader has no way to tell. One square
per game makes the denominator the graphic: the sample is countable on sight, so
the card cannot overstate its own certainty. Sorted 3-2-1-0 down the rows, the
shape also carries the actual finding, which is that his big games are bimodal
rather than average. Seven maximums and three blanks is not a bell.

FINALS ARE EXCLUDED AND THAT IS NOT COSMETIC
No Brownlow votes are awarded in a final, so a 25-disposal final would enter the
denominator as a game he could not have polled in and drag every rate down. The
archive labels finals with a string round (QF, EF, SF, PF, GF), so coercing
Round to a number and dropping the nulls is the whole filter. None of
Horne-Francis' 15 are finals, checked rather than assumed, but a Brisbane or a
Geelong player would have several.

THE CURRENT SEASON IS COUNTED, NEVER POLLED
Votes for the running season are not awarded until count night, so the rate is
built from completed seasons only and the current season appears as a volume
line rather than as squares. Mixing them would put games with a structural zero
into a poll rate.
"""

import argparse
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from countdown_card import (  # noqa: E402
    BG, INK, MUTED, RANK_INK, EMERALD, LINE,
    W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS,
)

OUT_DIR = "drafts"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"
STATS_ALL = "fitzroy_stats_all.csv"
STATS_CUR = "data_2026/afltables_2026.csv"
CUR_SEASON = 2026

# An ordered ramp, because votes are ordered. Four unrelated hues would say the
# categories are unrelated, and 3 votes is not a different kind of thing from 1.
VOTE_FILL = {3: "#34d399", 2: "#2a9d78", 1: "#1a6b52", 0: None}
VOTE_EDGE = {3: "#34d399", 2: "#2a9d78", 1: "#1a6b52", 0: "#31404e"}
VOTE_LABEL = {3: "3 VOTES", 2: "2 VOTES", 1: "1 VOTE", 0: "NO VOTES"}


def _name(d):
    return (d["First.name"].astype(str).str.strip() + " "
            + d["Surname"].astype(str).str.strip())


def _ha_only(d):
    """Home-and-away rows. Finals carry a string round and coerce to NaN."""
    return d[pd.to_numeric(d["Round"], errors="coerce").notna()]


def _won(d):
    """True where the player's club won. Draws read as not-a-win."""
    return ((d["Playing.for"] == d["Home.team"])
            == (d["Home.score"] > d["Away.score"]))


def gather(player, stat, line):
    """Completed-season games over the line, plus the current season's count."""
    hist = []
    for path in (STATS_HIST, STATS_ALL):
        d = pd.read_csv(path, low_memory=False)
        d = d[_name(d) == player]
        if not d.empty:
            hist.append(_ha_only(d))
    if not hist:
        raise SystemExit(f"{player!r} not found in the archives")
    h = pd.concat(hist, ignore_index=True)
    over = h[h[stat] >= line]
    if over.empty:
        raise SystemExit(f"{player!r} has no games with {stat} >= {line}")

    cur = pd.read_csv(STATS_CUR, low_memory=False)
    cur = _ha_only(cur[_name(cur) == player])

    counts = {v: int((over["Brownlow.Votes"] == v).sum()) for v in (3, 2, 1, 0)}
    return dict(
        counts=counts, n=len(over),
        polled=int((over["Brownlow.Votes"] > 0).sum()),
        yr0=int(over["Season"].min()), yr1=int(over["Season"].max()),
        prior_seasons=int(over["Season"].nunique()),
        cur_over=int((cur[stat] >= line).sum()), cur_games=len(cur),
        # The comparison needs BOTH halves of the prior rate, not just the
        # numerator. "9 this year against 15 before" reads as a fall until the
        # reader learns the 15 came from 75 games. Prior games counts every
        # completed home-and-away game he played, not only the qualifying ones.
        prior_games=len(h), prior_span=int(h["Season"].nunique()),
        # Result split. Home team wins when its score is higher; a player won if
        # his club was on that side. Draws fall to the "not a win" side, which
        # is right for a vote claim and wrong for a ladder.
        won_n=int(_won(over).sum()),
        won_polled=int((over.loc[_won(over), "Brownlow.Votes"] > 0).sum()),
        lost_n=int((~_won(over)).sum()),
        lost_polled=int((over.loc[~_won(over), "Brownlow.Votes"] > 0).sum()),
    )


def draw(player, place, stat, line, b, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def fit(t, role, size, width):
        while size > 20 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    stat_t = stat.replace(".", " ").upper()

    # -- masthead --------------------------------------------------
    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    text((m, 130 * S), player.upper(), fit(player.upper(), "name", 76, right - m), INK)
    text((m, 232 * S), f"BROWNLOW VOTES IN GAMES WITH {line}+ {stat_t}",
         font("display", 30), MUTED)
    text((m, 274 * S), f"{b['yr0']}-{b['yr1']}   {b['n']} GAMES",
         font("display", 30), RANK_INK)
    k.rectangle([m, 326 * S, right, 327 * S], fill=LINE)

    # -- the unit chart --------------------------------------------
    top = 372 * S
    rh = 128 * S
    lab_w = 214 * S
    # Cell size adapts to the LONGEST row, not to a fixed 60px. A player with a
    # long no-votes row (Sheezel: 21 of 34) ran the squares straight off the
    # right edge at a fixed size, and the count printed on top of them. The
    # squares must stay square and stay on one row per category, because the
    # row length IS the comparison.
    gap = 13 * S
    avail = right - (m + lab_w) - 70 * S      # 70 leaves room for the count
    widest = max(b["counts"].values()) or 1
    cell = min(60 * S, max(18 * S, avail // widest - gap))
    for i, v in enumerate((3, 2, 1, 0)):
        y = top + i * rh
        n = b["counts"][v]
        text((m, y + 12 * S), VOTE_LABEL[v], font("display", 34),
             INK if v else MUTED)
        for j in range(n):
            x = m + lab_w + j * (cell + gap)
            k.rectangle([x, y, x + cell, y + cell],
                        fill=VOTE_FILL[v], outline=VOTE_EDGE[v], width=3 * S)
        text((right, y + 4 * S), str(n), font("fig", 46),
             INK if v else MUTED, anchor="ra")
    k.rectangle([m, 890 * S, right, 891 * S], fill=LINE)

    # -- the two rates ---------------------------------------------
    poll = 100.0 * b["polled"] / b["n"]
    three = 100.0 * b["counts"][3] / b["n"]
    half = m + (right - m) // 2
    for x, val, lab, sub in (
            (m, f"{poll:.0f}%", "POLLED", f"{b['polled']} of {b['n']}"),
            (half, f"{three:.1f}%", "THREE VOTES",
             f"{b['counts'][3]} of {b['n']}")):
        text((x, 928 * S), val, font("fig", 108), EMERALD)
        text((x, 1058 * S), lab, font("display", 32), INK)
        text((x, 1100 * S), sub, font("display", 27), MUTED)
    k.rectangle([m, 1156 * S, right, 1157 * S], fill=LINE)

    # -- the current season, counted but not polled -----------------
    text((m, 1192 * S), f"{CUR_SEASON}", font("display", 32), EMERALD)
    text((m, 1240 * S),
         f"He reached {line} {stat_t.lower()} in {b['cur_over']} of "
         f"{b['cur_games']} games, against {b['n']} of {b['prior_games']} "
         f"across his first {b['prior_span']} seasons.",
         font("body", 27), INK)
    # A poll rate without the result split is close to meaningless for a player
    # from a beaten side: the same statline polls about twice as often in a win.
    if b.get("won_n"):
        text((m, 1290 * S),
             f"{b['won_n']} of those {b['n']} came in a win, and he polled in "
             f"{b['won_polled']} of them.", font("body", 27), MUTED)

    # No footer text on a card, by standing rule. The sample size is still
    # visible because the unit chart IS the denominator: one square, one game.

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR,
                        f"threshold_{place:02d}_{slug}_{stat.lower()}_{line}.png")
    long_edge = max(W, H) * S
    if long_edge > 2048:
        img = img.resize((int(W * S * 2048 / long_edge), 2048), Image.LANCZOS)
    img.save(path, "PNG", optimize=True)
    prev = None
    if preview:
        prev = path.replace(".png", "_timeline.png")
        img.resize((350, int(350 * img.height / img.width)),
                   Image.LANCZOS).save(prev, "PNG")
    return path, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("place", type=int)
    ap.add_argument("--stat", default="Disposals")
    ap.add_argument("--line", type=int, default=25)
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    set_fonts(a.font)
    b = gather(a.player, a.stat, a.line)
    path, prev = draw(a.player, a.place, a.stat, a.line, b, a.preview)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    {a.line}+ {a.stat}: {b['n']} games {b['yr0']}-{b['yr1']}, "
          f"{b['polled']} polled ({100.0*b['polled']/b['n']:.1f}%), "
          f"{b['counts'][3]} three-vote ({100.0*b['counts'][3]/b['n']:.1f}%)")
    print(f"    counts 3/2/1/0: {[b['counts'][v] for v in (3,2,1,0)]}")
    print(f"    in a win  {b['won_n']:3d} games, polled {b['won_polled']}"
          f" ({100.0*b['won_polled']/b['won_n']:.1f}%)" if b["won_n"] else "")
    print(f"    in a loss {b['lost_n']:3d} games, polled {b['lost_polled']}"
          f" ({100.0*b['lost_polled']/b['lost_n']:.1f}%)" if b["lost_n"] else "")
    print(f"    {CUR_SEASON}: {b['cur_over']} of {b['cur_games']} over the line")
    return 0


if __name__ == "__main__":
    sys.exit(main())
