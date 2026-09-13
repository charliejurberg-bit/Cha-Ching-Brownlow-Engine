"""Seasons clearing two per-game lines at once, with one player marked.

    python scripts/pair_seasons_card.py "Jordan Dawson" 8 \
        --stat1 Kicks --line1 17 --stat2 Tackles --line2 5.5

Writes a PNG to drafts/ (gitignored). Same 1200x1500 portrait, palette, fonts
and CHA CHING mark as countdown_card.py, imported rather than restated. No
footer text, by standing rule: the window and the games floor are stated in the
header instead, where they are set at a size that survives a timeline.

WHY THIS CARD EXISTS
A single-stat ladder only works for a player who leads something. Dawson's best
2026 rank is 12th, so every standing card reads as "quite good at a few things",
which is not the claim. What is rare about him is a COMBINATION: he kicks like a
rebounding defender and tackles like an inside midfielder, and almost nobody
does both. A two-condition ladder is the only shape that shows an intersection,
because the whole finding is how few rows there are.

SORTED BY SEASON, NOT BY VALUE
The claim is membership of a small set, not a ranking inside it. Ordering by
either stat invites the reader to treat row 1 as the best, which would be a
different and unsupported claim: Rockliff's 9.1 tackles does not make his season
better than Ablett's 19.5 kicks. Chronological order carries no such implication
and lets a repeat name show up as a repeat.

A PLAYER CAN OCCUPY MORE THAN ONE ROW AND THAT IS THE POINT
Marking is by name, so a player with two qualifying seasons is highlighted
twice. For Dawson that is the finding rather than a side effect: seven seasons
qualify and he owns two of them.

BOTH THRESHOLDS ARE CHOSEN, SO THE COPY MUST SAY SO
Nothing here makes 17 and 5.5 natural lines. The card is honest about its window
and its games floor but it cannot show a sensitivity grid, so the accompanying
copy carries the grid instead: state that the finding survives a band of lines
rather than presenting these two as given. Run --grid to print that band.

THE WINDOW IS THE PAIR'S, NOT THE ARCHIVE'S
Tackles are null in the archive before 1987, so a Kicks/Tackles card starts in
1987 even though the archive reaches 1965. The window is measured from the
first season BOTH stats are recorded, never assumed, and the header prints it.
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
    ABBR, BG, INK, MUTED, RANK_INK, EMERALD, LINE, PANEL,
    W, H, S, MIN_GAMES, draw_mark, font, ordinal, set_fonts, FONT_SETS,
)

OUT_DIR = "drafts"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"
STATS_ALL = "fitzroy_stats_all.csv"
STATS_CUR = "data_2026/afltables_2026.csv"

LABELS = {
    "Disposals": "DISPOSALS",
    "Kicks": "KICKS",
    "Handballs": "HANDBALLS",
    "Marks": "MARKS",
    "Tackles": "TACKLES",
    "Goals": "GOALS",
    "Clearances": "CLEARANCES",
    "Contested.Possessions": "CONTESTED POSS",
    "Uncontested.Possessions": "UNCONTESTED",
    "Inside.50s": "INSIDE 50s",
    "Rebounds": "REBOUND 50s",
    "Marks.Inside.50": "MARKS INSIDE 50",
    "One.Percenters": "ONE PERCENTERS",
    "Goal.Assists": "GOAL ASSISTS",
}


def _load(path):
    d = pd.read_csv(path, low_memory=False)
    d = d[pd.to_numeric(d["Round"], errors="coerce").notna()]
    return d.assign(P=(d["First.name"].astype(str).str.strip() + " "
                       + d["Surname"].astype(str).str.strip()))


def gather(stat1, line1, stat2, line2):
    """One row per season clearing both lines, oldest first.

    Returns the table, the first season the PAIR is recorded, and the last, plus
    the number of player-seasons that cleared the games floor and so were
    eligible to qualify. That denominator is what makes a count of seven mean
    anything.
    """
    d = pd.concat([_load(STATS_HIST), _load(STATS_ALL), _load(STATS_CUR)],
                  ignore_index=True)
    for stat in (stat1, stat2):
        if stat not in d.columns:
            raise SystemExit(f"{stat!r} is not a column in the archive")
    for col in ("Season", stat1, stat2):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    # The window belongs to the pair. A stat null before some season is not a
    # season with no qualifiers, it is a season that cannot be tested, and
    # letting it into the denominator understates how rare the pair is.
    d = d.dropna(subset=["Season", stat1, stat2])
    if d.empty:
        raise SystemExit(f"{stat1} and {stat2} are never both recorded")
    g = (d.groupby(["Season", "P"])
           .agg(games=(stat1, "size"), v1=(stat1, "mean"), v2=(stat2, "mean"),
                team=("Playing.for", "last"))
           .reset_index())
    eligible = g[g.games >= MIN_GAMES]
    q = eligible[(eligible.v1 >= line1) & (eligible.v2 >= line2)]
    if q.empty:
        raise SystemExit(
            f"no season reaches {line1} {stat1} and {line2} {stat2} "
            f"at {MIN_GAMES}+ games")
    return (q.sort_values("Season").reset_index(drop=True),
            int(d.Season.min()), int(d.Season.max()), len(eligible))


def draw(player, place, stat1, line1, stat2, line2, tbl, yr0, nqual,
         nrows, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    span = right - m
    lab1, lab2 = LABELS.get(stat1, stat1.upper()), LABELS.get(stat2, stat2.upper())

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def rule(y, fill=LINE):
        k.rectangle([m, y * S, right, y * S + S], fill=fill)

    def fit(t, role, size, width):
        while size > 24 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    # -- masthead --------------------------------------------------
    draw_mark(img, m, 44 * S, 29)
    if place:
        text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
             font("display", 29), MUTED, anchor="ra")
    rule(100)

    head = f"{line1:g} {lab1} AND {line2:g} {lab2}"
    text((m, 128 * S), head, fit(head, "name", 62, span), INK)
    text((m, 200 * S), "A GAME, IN ONE SEASON",
         fit("A GAME, IN ONE SEASON", "name", 62, span), INK)
    # The window and the floor live here, not in a footer. Both are statements
    # about the source and the claim is wrong without them.
    text((m, 282 * S),
         f"SINCE {yr0}   {MIN_GAMES} GAMES OR MORE   "
         f"{len(tbl)} OF {nqual:,} SEASONS",
         font("display", 30), RANK_INK)
    rule(330)

    # -- column heads ----------------------------------------------
    c_season = m + int(span * 0.20)
    c_name = m + int(span * 0.24)
    c_v1 = m + int(span * 0.80)
    # Shrink a long stat head to its own column rather than slicing it. A hard
    # cut turned CLEARANCES into CLEARANCE, which is a different word and reads
    # as a typo rather than as an abbreviation.
    def head_font(t, width, size=24):
        while size > 15 and k.textlength(t, font=font("display", size)) > width:
            size -= 1
        return font("display", size)

    for lab, x, anc, wd in (("SEASON", c_season, "ra", span),
                            ("PLAYER", c_name, "la", span),
                            (lab1, c_v1, "ra", c_v1 - c_name - 12 * S),
                            (lab2, right, "ra", right - c_v1 - 12 * S)):
        text((x, 356 * S), lab, head_font(lab, wd), MUTED, anchor=anc)

    # -- the ladder -------------------------------------------------
    # The pitch derives from the rows ACTUALLY drawn, not from --rows: an
    # intersection card is often shorter than the cap asks for, and pitching
    # seven rows as though there were ten leaves a quarter of the page blank.
    # Past the cap the ladder stops stretching and is centred in the band
    # instead, so a very short list reads as a short list rather than as a
    # table someone forgot to finish. At 12 rows this reproduces the original
    # 82-unit pitch starting at 408 exactly.
    shown = tbl.head(nrows)
    band_top, band_bot, row_h = 408 * S, 1372 * S, 62 * S
    n = max(len(shown), 1)
    rh = min(118 * S, (band_bot - row_h - band_top) // max(n - 1, 1))
    used = (n - 1) * rh + row_h
    top = band_top + max(0, (band_bot - band_top - used) // 2)
    for i, (_, r) in enumerate(shown.iterrows()):
        y = top + i * rh
        me = r.P == player
        if me:
            k.rectangle([m - 14 * S, y - 14 * S, right + 14 * S, y + 62 * S],
                        fill=PANEL)
            k.rectangle([m - 14 * S, y - 14 * S, m - 10 * S, y + 62 * S],
                        fill=EMERALD)
        ink = EMERALD if me else INK
        text((m, y), f"{i + 1}", font("display", 30), EMERALD if me else MUTED)
        text((c_season, y), str(int(r.Season)), font("fig", 36), ink,
             anchor="ra")
        nm = r.P.upper()
        text((c_name, y), nm, fit(nm, "display", 34, int(span * 0.50)), ink)
        club = ABBR.get(r.team, str(r.team).upper())
        text((c_name, y + 42 * S), club, font("display", 22), MUTED)
        text((c_v1, y), f"{r.v1:.1f}", font("fig", 36), ink, anchor="ra")
        text((right, y), f"{r.v2:.1f}", font("fig", 36), ink, anchor="ra")

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    s1 = re.sub(r"[^a-z0-9]+", "_", stat1.lower()).strip("_")
    s2 = re.sub(r"[^a-z0-9]+", "_", stat2.lower()).strip("_")
    path = os.path.join(
        OUT_DIR, f"countdown_{place:02d}_{slug}_{s1}_{line1:g}_{s2}_{line2:g}.png")
    img.save(path, "PNG", optimize=True)
    prev = None
    if preview:
        prev = path.replace(".png", "_timeline.png")
        img.resize((350, int(350 * H / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


def grid(player, stat1, line1, stat2, line2):
    """Print the claim across a band of lines around the chosen pair.

    A two-threshold claim is worthless without this. If the finding only holds
    at the exact pair that fits the subject, the pair was fitted to him and the
    card is drawing a coincidence.
    """
    d = pd.concat([_load(STATS_HIST), _load(STATS_ALL), _load(STATS_CUR)],
                  ignore_index=True)
    for col in ("Season", stat1, stat2):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["Season", stat1, stat2])
    g = (d.groupby(["Season", "P"])
           .agg(games=(stat1, "size"), v1=(stat1, "mean"), v2=(stat2, "mean"))
           .reset_index())
    g = g[g.games >= MIN_GAMES]
    print(f"\n  {stat1:>10} {stat2:>8} {'seasons':>9} {'players':>9} "
          f"{'subject':>9}   repeat names")
    for a in (line1 - 1, line1 - 0.5, line1, line1 + 0.5, line1 + 1):
        for b in (line2 - 0.5, line2, line2 + 0.5):
            h = g[(g.v1 >= a) & (g.v2 >= b)]
            if h.empty:
                continue
            vc = h.P.value_counts()
            rep = ", ".join(f"{p} {n}" for p, n in vc.items() if n >= 2)
            print(f"  {a:>10g} {b:>8g} {len(h):>9} {h.P.nunique():>9} "
                  f"{int(vc.get(player, 0)):>9}   {rep or 'none twice'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("place", type=int)
    ap.add_argument("--stat1", default="Kicks")
    ap.add_argument("--line1", type=float, default=17)
    ap.add_argument("--stat2", default="Tackles")
    ap.add_argument("--line2", type=float, default=5.5)
    ap.add_argument("--rows", type=int, default=10,
                    help="how many of the ladder to draw")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--grid", action="store_true",
                    help="print the threshold sensitivity band and exit")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    set_fonts(a.font)
    if a.grid:
        grid(a.player, a.stat1, a.line1, a.stat2, a.line2)
        return 0
    tbl, yr0, yr1, nqual = gather(a.stat1, a.line1, a.stat2, a.line2)
    if a.player not in set(tbl.P):
        raise SystemExit(
            f"{a.player} has no season at {a.line1}+ {a.stat1} "
            f"and {a.line2}+ {a.stat2}")
    path, prev = draw(a.player, a.place, a.stat1, a.line1, a.stat2, a.line2,
                      tbl, yr0, nqual, a.rows, a.preview)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    mine = tbl[tbl.P == a.player]
    print(f"    {len(tbl)} qualifying seasons of {nqual:,} eligible, "
          f"{tbl.P.nunique()} players, {yr0}-{yr1}, {MIN_GAMES}+ games")
    print(f"    {a.player}: {len(mine)} of them "
          f"({', '.join(str(int(s)) for s in mine.Season)})")
    twice = tbl.P.value_counts()
    twice = twice[twice >= 2]
    print(f"    players with more than one: "
          f"{', '.join(f'{p} {n}' for p, n in twice.items()) or 'none'}")
    for i, (_, r) in enumerate(tbl.head(max(a.rows, len(tbl))).iterrows(), 1):
        mark = "  <<" if r.P == a.player else ""
        print(f"      {i:2d} {int(r.Season)}  {r.P:24} "
              f"{r.v1:6.2f}  {r.v2:5.2f}  {int(r.games)}g{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
