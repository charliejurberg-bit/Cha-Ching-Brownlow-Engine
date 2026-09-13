"""The youngest (or oldest) seasons to average a figure in a stat, one marked.

    python scripts/age_record_card.py "Harry Sheezel" 9 --stat Disposals --line 30
    python scripts/age_record_card.py "Harry Sheezel" 9 --stat Disposals --line 30 --rows 12
    python scripts/age_record_card.py "Lachie Neale" 7 --stat Disposals --line 30 --oldest

Writes a PNG to drafts/ (gitignored). Same 1200x1500 portrait, palette, fonts
and CHA CHING mark as countdown_card.py, imported rather than restated. No
footer text, by standing rule: the window and the games floor are stated in the
header instead, where they are set at a size that survives a timeline.

WHY THIS CARD EXISTS
The season-comparison card only ever argues improvement, and improvement is a
different claim from standing. Sheezel's disposals sat between 29 and 30.5 for
three seasons, so a comparison card read flat while the actually remarkable fact
about him went unshown: he is the second-youngest player in sixty years to
average 30 a game. Pick the card from what is most relevant, never by default.

AGE IS A SEASON MEAN AND CANNOT SEPARATE NEIGHBOURS
The archive carries an `Age` column per row, so a player's age here is the mean
across his season: what he was through that year rather than on any one date.
That is the right measure for "at what age did he do this" and it is not precise
to the day. Sheezel and Zach Merrett sit 0.05 apart, about eighteen days, which
is inside what this can honestly resolve. Any copy off this card should lean on
a gap of a year, not on adjacent rows. main() prints the gap to the neighbouring
row on every run so the operator sees how much the ordering is worth: on the
oldest 30-disposal ladder it is 0.008 years, under three days, and the copy for
that card has to name both men rather than crown one.

--oldest: THE SAME LADDER TURNED ROUND, AND IT IS A DIFFERENT CLAIM
Youngest is a claim about precocity and has a natural floor at debut age.
Oldest is a claim about longevity and has no ceiling, so the top of that ladder
is thinner and a single season can sit alone by a rounding error. Read the gap
line before writing anything that says "the oldest".

THE 12-GAME FLOOR IS LOAD BEARING AND THE HEADER SAYS SO
Without it a player who managed three enormous games outranks a player who
averaged 30 across a season, which is not the claim. Half a 23-game home and
away season is the same threshold countdown_card.py uses.

1965 IS THE ARCHIVE'S FLOOR, NOT A CHOSEN WINDOW
data_history/fitzroy_stats_1965_2006.csv.gz begins there. Nothing earlier can be
built, so "since 1965" is a statement about the source. Say it; a reader who
takes an unqualified "youngest ever" on trust has been misled by the omission.
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
CUR_SEASON = 2026
# Label, and how to format the value. Anything in the archive works; these are
# the ones whose per-game average is a claim anyone recognises.
LABELS = {
    "Disposals": ("DISPOSALS", "{:.1f}"),
    "Kicks": ("KICKS", "{:.1f}"),
    "Handballs": ("HANDBALLS", "{:.1f}"),
    "Marks": ("MARKS", "{:.1f}"),
    "Tackles": ("TACKLES", "{:.1f}"),
    "Goals": ("GOALS", "{:.1f}"),
    "Clearances": ("CLEARANCES", "{:.1f}"),
    "Contested.Possessions": ("CONTESTED POSSESSIONS", "{:.1f}"),
    "Inside.50s": ("INSIDE 50s", "{:.1f}"),
}


AGE_UNIT = 1 / 365.25       # the Age column is (match date - birth date) in years


def _repair_age(d):
    """The archive writes Age as 0 for a game played ON the player's birthday.

    1,217 rows across the two historical files, and it is not cosmetic. Gary
    Ablett's 2017 carries one (14 May 2017, his 33rd) and reads a season mean of
    30.66 instead of 33.01, which is the difference between seventh on the
    30-disposal age ladder and first. A ladder built on the raw column is
    therefore wrong in exactly the rows it is most likely to be asked about: a
    long career is more likely to contain a birthday game.

    Age is the match date minus the birth date in years, so any other row of the
    same player-season recovers a missing one exactly by walking the date
    difference. The anchor is keyed on fitzRoy ID wherever there is one, never on
    the name alone: two players named Josh Kennedy appear in the same season and
    would anchor each other. ID is not universal (4 rows of fitzroy_stats_all
    and 92 of the 2026 file have none), so those rows fall back to the name and
    a whole-file test would have thrown the ID key away for the sake of them.
    A row with no good row to anchor to is left NaN rather than 0, so it drops
    out of a mean instead of dragging it toward zero.
    """
    bad = d["Age"] <= 0
    if not bad.any():
        return d
    d = d.assign(_k=d["ID"].astype(str).where(d["ID"].notna(), d["P"]))
    dt = pd.to_datetime(d["Date"], errors="coerce")
    anchor = (d[~bad].assign(_a=d.loc[~bad, "Age"], _d=dt[~bad])
                     .groupby(["_k", "Season"])[["_a", "_d"]].first())
    j = d.loc[bad, ["_k", "Season"]].join(anchor, on=["_k", "Season"])
    d.loc[bad, "Age"] = (j["_a"] + (dt[bad] - j["_d"]).dt.days * AGE_UNIT)
    return d.drop(columns="_k")


def _load(path):
    d = pd.read_csv(path, low_memory=False)
    d = d[pd.to_numeric(d["Round"], errors="coerce").notna()]
    d = d.assign(P=(d["First.name"].astype(str).str.strip() + " "
                    + d["Surname"].astype(str).str.strip()))
    return _repair_age(d)


def gather(stat, line, oldest=False):
    """One row per qualifying player-season, youngest first (or oldest)."""
    d = pd.concat([_load(STATS_HIST), _load(STATS_ALL), _load(STATS_CUR)],
                  ignore_index=True)
    if stat not in d.columns:
        raise SystemExit(f"{stat!r} is not a column in the archive")
    g = (d.groupby(["Season", "P"])
           .agg(games=(stat, "size"), val=(stat, "mean"),
                age=("Age", "mean"), team=("Playing.for", "last"))
           .reset_index())
    q = g[(g.games >= MIN_GAMES) & (g.val >= line) & g.age.notna()]
    if q.empty:
        raise SystemExit(f"no season reaches {line} {stat} at {MIN_GAMES}+ games")
    return (q.sort_values("age", ascending=not oldest).reset_index(drop=True),
            int(d.Season.min()), int(d.Season.max()))


def draw(player, place, stat, line, tbl, yr0, yr1, nrows, preview=False,
         oldest=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    span = right - m
    label, fmt = LABELS.get(stat, (stat.replace(".", " ").upper(), "{:.1f}"))

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

    head = f"{'OLDEST' if oldest else 'YOUNGEST'} TO AVERAGE {line:g}"
    text((m, 128 * S), head, fit(head, "name", 62, span), INK)
    text((m, 200 * S), f"{label} IN A SEASON", fit(f"{label} IN A SEASON",
                                                   "name", 62, span), INK)
    # The window and the floor live here, not in a footer. Both are statements
    # about the source and the claim is wrong without them.
    text((m, 282 * S),
         f"SINCE {yr0}   {MIN_GAMES} GAMES OR MORE   {len(tbl)} SEASONS IN ALL",
         font("display", 30), RANK_INK)
    rule(330)

    # -- column heads ----------------------------------------------
    c_age = m + int(span * 0.20)
    c_name = m + int(span * 0.24)
    c_season = m + int(span * 0.80)
    for lab, x, anc in (("AGE", c_age, "ra"), ("PLAYER", c_name, "la"),
                        ("SEASON", c_season, "ra"), (label[:9], right, "ra")):
        text((x, 356 * S), lab, font("display", 24), MUTED, anchor=anc)

    # -- the ladder -------------------------------------------------
    # The ladder fills the same band whatever the row count, so a shorter
    # card does not leave a quarter of the page empty. At 12 rows this
    # reproduces the original 82-unit pitch exactly. The cap stops a very
    # short ladder from spacing rows until they stop reading as one table.
    top, last = 408 * S, 1310 * S
    rh = min(110 * S, (last - top) // max(nrows - 1, 1))
    shown = tbl.head(nrows)
    for i, (_, r) in enumerate(shown.iterrows()):
        y = top + i * rh
        me = r.P == player
        if me:
            k.rectangle([m - 14 * S, y - 14 * S, right + 14 * S, y + 62 * S],
                        fill=PANEL)
            k.rectangle([m - 14 * S, y - 14 * S, m - 10 * S, y + 62 * S],
                        fill=EMERALD)
        ink = EMERALD if me else INK
        text((m, y), f"{i + 1}", font("display", 30),
             EMERALD if me else MUTED)
        text((c_age, y), f"{r.age:.1f}", font("fig", 36), ink, anchor="ra")
        nm = r.P.upper()
        text((c_name, y), nm, fit(nm, "display", 34, int(span * 0.50)), ink)
        club = ABBR.get(r.team, str(r.team).upper())
        text((c_name, y + 42 * S), club, font("display", 22), MUTED)
        text((c_season, y), str(int(r.Season)), font("fig", 34),
             ink if me else RANK_INK, anchor="ra")
        text((right, y), fmt.format(r.val), font("fig", 36), ink, anchor="ra")

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    sslug = re.sub(r"[^a-z0-9]+", "_", stat.lower()).strip("_")
    path = os.path.join(OUT_DIR,
                        f"countdown_{place:02d}_{slug}_"
                        f"{'oldest' if oldest else 'youngest'}_"
                        f"{sslug}_{line:g}.png")
    img.save(path, "PNG", optimize=True)
    prev = None
    if preview:
        prev = path.replace(".png", "_timeline.png")
        img.resize((350, int(350 * H / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("place", type=int)
    ap.add_argument("--stat", default="Disposals")
    ap.add_argument("--line", type=float, default=30)
    ap.add_argument("--rows", type=int, default=10,
                    help="how many of the ladder to draw")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--oldest", action="store_true",
                    help="rank oldest first instead of youngest")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    set_fonts(a.font)
    tbl, yr0, yr1 = gather(a.stat, a.line, a.oldest)
    if a.player not in set(tbl.P):
        raise SystemExit(f"{a.player} has no season at {a.line}+ {a.stat}")
    path, prev = draw(a.player, a.place, a.stat, a.line, tbl, yr0, yr1,
                      a.rows, a.preview, a.oldest)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    pos = int(tbl.index[tbl.P == a.player][0]) + 1
    # Distinct players ahead of him matters more than rows ahead: a player who
    # did it twice fills two rows and is still one player.
    ahead = tbl.head(pos - 1).P.nunique()
    print(f"    {a.player}: {ordinal(pos)} of {len(tbl)} seasons, "
          f"{ahead} player(s) {'older' if a.oldest else 'younger'}, "
          f"{yr0}-{yr1}, {MIN_GAMES}+ games")
    # The gap to the next row, because an ordering claim off a season mean is
    # only as good as the gap behind it. Neale leads the 30-disposal ladder by
    # 0.008 years, under three days, which is a tie in everything but sort
    # order and the copy has to say so.
    if pos < len(tbl):
        nxt = tbl.iloc[pos] if pos == 1 else tbl.iloc[pos - 2]
        gap = abs(float(tbl.iloc[pos - 1].age) - float(nxt.age))
        print(f"    gap to the row {'behind' if pos == 1 else 'ahead'}: "
              f"{gap:.3f} years ({gap * 365.25:.0f} days), {nxt.P} "
              f"{int(nxt.Season)}")
    for i, (_, r) in enumerate(tbl.head(max(a.rows, pos)).iterrows(), 1):
        mark = "  <<" if r.P == a.player else ""
        print(f"      {i:2d} {r.age:5.2f}  {r.P:26} {int(r.Season)}  "
              f"{r.val:6.2f}  {int(r.games)}g{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
