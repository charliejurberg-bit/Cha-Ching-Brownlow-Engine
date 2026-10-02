"""Team comparison card, rows chosen by what actually separates Grand Final winners.

    python scripts/team_compare_card.py "Fremantle" "Brisbane Lions" --preview
    python scripts/team_compare_card.py "Fremantle" "Brisbane Lions" --min-pct 70

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, same geometry,
palette, fonts, logo and Twitter downsample as compare_card.py, all IMPORTED
from it rather than copied. A fourth drifting copy of the Midnight Turf palette
is worse than an import.

HOW THIS DIFFERS FROM compare_card.py, AND WHY IT MATTERS

compare_card.py picks its rows by hand and says so in its own docstring: the
rows are chosen to give each player his own strengths, so counting emerald bars
counts the author's row selection rather than a result.

This card does the opposite, deliberately. **The rows are not chosen, they are
measured.** Every stat available at team level is tested against every Grand
Final in the archive, and a row appears only if the eventual premier led that
stat often enough to clear --min-pct and a two-sided binomial test at p < 0.05.
So a lopsided card here IS a result, and the row count is reportable.

Two consequences, both load-bearing:

  - **Each row carries its own denominator**, "53 of 59", because the stats do
    not share a start year. Kicks and marks reach 1965; inside 50s, clearances
    and contested possessions only start in 1998 or 1999, so a row reading
    "20 of 23" is a genuinely smaller sample and the card must not hide it.
  - **Only "more is better" stats are eligible.** Clangers, frees for and
    rebound 50s all run the other way, where the premier tends to have FEWER,
    and a diverging bar cannot encode two directions without lying about one of
    them. They are excluded rather than flipped, and the count of what was
    excluded is printed to stdout so it is never silently dropped.

WHAT THIS CARD IS NOT

It is not a prediction, and it is not a full account of either team. Every row
is a possession or scoring measure, because those are the ones the archive
carries at team level. Defence does not appear: a club can win by denying rather
than by accumulating, which is exactly how the 2026 minor premier played. That
qualifier belongs in the draft copy, not on the card, per the standing rule that
cards carry the masthead and the figures and nothing else.
"""

import argparse
import os
import sys

import pandas as pd
from PIL import Image, ImageDraw
from scipy import stats as sps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compare_card import (BG, EMERALD, INK, LABEL, LINE, MUTED, S, SLATE,
                          TWITTER_LONG_EDGE, W, H, draw_mark, font, ordinal)

OUT_DIR = "drafts"
STATS_2026 = "data_2026/afltables_2026.csv"
STATS_ALL = "fitzroy_stats_all.csv"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"

# Team-level stats where MORE is better, so a diverging bar reads honestly.
# The inverted ones are named in EXCLUDED so the exclusion is reported rather
# than implied by absence.
CANDIDATES = [
    ("Kicks", "Kicks", 0),
    ("Marks", "Marks", 0),
    ("Handballs", "Handballs", 0),
    ("Disposals", "Disposals", 0),
    ("Inside.50s", "Inside 50s", 1),
    ("Clearances", "Clearances", 1),
    ("Contested.Possessions", "Contested possessions", 1),
    ("Uncontested.Possessions", "Uncontested possessions", 1),
    ("Contested.Marks", "Contested marks", 1),
    ("Marks.Inside.50", "Marks inside 50", 1),
    ("One.Percenters", "One percenters", 1),
    ("Tackles", "Tackles", 1),
    ("Hit.Outs", "Hit-outs", 1),
]
EXCLUDED = ["Clangers", "Frees.For", "Rebounds"]   # premier tends to have FEWER

# Not tested, because a hit rate for these would be trivially true rather than
# informative. A goal assist is recorded on the disposal that creates a goal, so
# "the premier had more goal assists" is close to restating "the premier kicked
# more goals", which is the definition of winning. It measured 18 of 20, the
# highest rate of anything tested, and that height is the tell: a row nobody
# could have been surprised by is spending space a real finding could use.
# Marks inside 50 sits on the same spectrum and is left in, because territory
# entering the arc is a step removed from the score itself.
CIRCULAR = ["Goal.Assists"]

MAX_ROWS = 8


def _load(cols):
    keep = lambda c: c in cols
    a = pd.read_csv(STATS_ALL, usecols=keep, low_memory=False)
    h = pd.read_csv(STATS_HIST, usecols=keep, low_memory=False)
    return pd.concat([a, h], ignore_index=True)


def gf_profile(min_pct, alpha=0.05):
    """For each candidate stat, how often the premier led it in a Grand Final.

    Returns rows clearing min_pct AND a two-sided binomial test, longest odds
    first. Every row carries its own n, because the stats start in different
    years and a shared denominator would be a fiction.
    """
    stats = [k for k, _, _ in CANDIDATES]
    cols = set(["Season", "Round", "Playing.for", "Home.team", "Away.team",
                "Home.score", "Away.score"]) | set(stats)
    d = _load(cols)
    gf = d[d["Round"].astype(str).str.upper() == "GF"].copy()

    meta = gf.groupby("Season").agg(H=("Home.team", "first"), A=("Away.team", "first"),
                                    HS=("Home.score", "first"), AS=("Away.score", "first"))
    meta["winner"] = meta.apply(
        lambda r: r.H if r.HS > r.AS else (r.A if r.AS > r.HS else "DRAW"), axis=1)
    meta = meta[meta.winner != "DRAW"]

    team = gf.groupby(["Season", "Playing.for"])[stats].sum(min_count=1)
    out = []
    for key, label, dec in CANDIDATES:
        led = n = 0
        for season, mrow in meta.iterrows():
            try:
                wv = team.loc[(season, mrow.winner), key]
            except KeyError:
                continue
            loser = mrow.A if mrow.winner == mrow.H else mrow.H
            try:
                lv = team.loc[(season, loser), key]
            except KeyError:
                continue
            if pd.isna(wv) or pd.isna(lv) or wv == lv:
                continue
            n += 1
            led += int(wv > lv)
        if n < 15:
            continue
        pct = led / n * 100
        p = sps.binomtest(led, n, 0.5).pvalue
        out.append(dict(key=key, label=label, dec=dec, led=led, n=n, pct=pct, p=p))
    res = pd.DataFrame(out)
    kept = res[(res.pct >= min_pct) & (res.p < alpha)].sort_values("pct", ascending=False)
    return kept.head(MAX_ROWS).reset_index(drop=True), res


def season_figures(season, stats):
    """Per-game team means for one season, home and away only, plus league rank."""
    path = STATS_2026 if season == 2026 else STATS_ALL
    cols = set(["Season", "Round", "Playing.for"]) | set(stats)
    d = pd.read_csv(path, usecols=lambda c: c in cols, low_memory=False)
    d = d[d["Season"] == season]
    d = d[pd.to_numeric(d["Round"], errors="coerce").notna()]
    per = (d.groupby(["Round", "Playing.for"])[list(stats)].sum(min_count=1)
             .reset_index().groupby("Playing.for")[list(stats)].mean())
    rank = per.rank(ascending=False)
    return per, rank


def draw(a, b, rows, per, rank, season, out_path, preview):
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)

    def text(xy, t, f, fill, anchor="la"):
        d.text((xy[0] * S, xy[1] * S), t, font=f, fill=fill, anchor=anchor)

    M = 64
    draw_mark(img, M * S, 38 * S, 26)
    short = lambda c: {"Brisbane Lions": "BRISBANE",
                       "Greater Western Sydney": "GWS",
                       "Western Bulldogs": "BULLDOGS"}.get(c, c.upper())
    text((M, 96), f"{short(a)}  v  {short(b)}", font("display", 60), INK)
    text((M, 172), "What separates a Grand Final winner", font("body", 23), MUTED)

    hy = 224
    for club, x, anc in ((a, M, "la"), (b, W - M, "ra")):
        text((x, hy), short(club), font("name", 29), INK, anchor=anc)
        text((x, hy + 36), f"Per game, {season} home and away",
             font("body", 20), MUTED, anchor=anc)
    d.line([(M * S, (hy + 76) * S), ((W - M) * S, (hy + 76) * S)], fill=LINE, width=2 * S)

    top = hy + 112
    FOOT_Y = 1382
    row_h = (FOOT_Y - 30 - top) / len(rows)
    # Each row's drawn content is shorter than its slot, so centre it inside the
    # slot. Without this the block hangs off the top rule and leaves the gap
    # between the last row and the footer reading as a missing row.
    ROW_CONTENT = 62
    pad = max(0.0, (row_h - ROW_CONTENT) / 2)
    gutter = 340
    cx = W / 2
    inner_l, inner_r = cx - gutter / 2, cx + gutter / 2
    VALUE_ROOM = 104
    max_bar = inner_l - M - VALUE_ROOM

    for i, r in rows.iterrows():
        y = top + i * row_h + pad
        av, bv = per.loc[a, r.key], per.loc[b, r.key]
        hi = max(av, bv) or 1
        la, lb = max_bar * av / hi, max_bar * bv / hi
        a_wins = av > bv

        text((cx, y + 14), r.label, font("body", 23), LABEL, anchor="ma")
        # The hit rate with its own denominator. A figure, not a caption: the
        # stats start in different years and 20 of 23 is not 53 of 59.
        text((cx, y + 44), f"{r.pct:.0f}% of winners  ·  {r.led} of {r.n}",
             font("body", 19), MUTED, anchor="ma")

        bar_y = y + 10
        bar_h = 34
        d.rounded_rectangle([((inner_l - la) * S, bar_y * S), (inner_l * S, (bar_y + bar_h) * S)],
                           radius=4 * S, fill=EMERALD if a_wins else SLATE)
        d.rounded_rectangle([(inner_r * S, bar_y * S), ((inner_r + lb) * S, (bar_y + bar_h) * S)],
                           radius=4 * S, fill=SLATE if a_wins else EMERALD)

        fmt = f"{{:,.{int(r.dec)}f}}"
        text((inner_l - la - 12, bar_y + 1), fmt.format(av), font("fig", 30),
             INK if a_wins else MUTED, anchor="ra")
        text((inner_r + lb + 12, bar_y + 1), fmt.format(bv), font("fig", 30),
             MUTED if a_wins else INK, anchor="la")
        # League rank sits under each figure, so a bar that looks close is still
        # read against the other sixteen clubs.
        text((inner_l - la - 12, bar_y + 38), ordinal(rank.loc[a, r.key]),
             font("body", 18), MUTED, anchor="ra")
        text((inner_r + lb + 12, bar_y + 38), ordinal(rank.loc[b, r.key]),
             font("body", 18), MUTED, anchor="la")

    d.line([(M * S, FOOT_Y * S), ((W - M) * S, FOOT_Y * S)], fill=LINE, width=2 * S)
    text((M, FOOT_Y + 20), "AFLTables", font("body", 18), MUTED)

    drawn = img.size
    if img.height > TWITTER_LONG_EDGE:
        img = img.resize((round(img.width * TWITTER_LONG_EDGE / img.height),
                          TWITTER_LONG_EDGE), Image.LANCZOS)
    img.save(out_path, optimize=True)
    print(f"wrote {out_path}  (drawn {drawn[0]}x{drawn[1]}, shipped "
          f"{img.width}x{img.height}, {os.path.getsize(out_path) / 1024:.0f} KB)")
    if preview:
        p = out_path.replace(".png", "_preview.png")
        img.resize((350, round(350 * img.height / img.width)), Image.LANCZOS).save(p)
        print(f"wrote {p}  (350px, what Twitter shows in-timeline)")
        j = out_path.replace(".png", "_asposted.jpg")
        img.save(j, "JPEG", quality=85, subsampling=2)
        print(f"wrote {j}  (q85 4:2:0, approximates what Twitter serves)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("team_a")
    ap.add_argument("team_b")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--min-pct", type=float, default=70.0)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows, allrows = gf_profile(args.min_pct)
    print(f"tested {len(allrows)} team stats against the Grand Final archive; "
          f"{len(rows)} cleared {args.min_pct:.0f}% and p<0.05")
    print(f"excluded as inverted (premier tends to have FEWER): {', '.join(EXCLUDED)}")
    print(f"excluded as circular (restates the scoreline): {', '.join(CIRCULAR)}")
    print(allrows.sort_values('pct', ascending=False)
          [['label', 'led', 'n', 'pct', 'p']].to_string(index=False))
    if not len(rows):
        sys.exit("no stat cleared the threshold, nothing drawn")

    per, rank = season_figures(args.season, [r for r in rows.key])
    for club in (args.team_a, args.team_b):
        if club not in per.index:
            sys.exit(f"'{club}' not in {args.season}. Clubs: {sorted(per.index)}")

    slug = "_".join(c.lower().replace(" ", "") for c in (args.team_a, args.team_b))
    out = args.out or os.path.join(OUT_DIR, f"teamcompare_{slug}_{args.season}.png")
    os.makedirs(OUT_DIR, exist_ok=True)
    draw(args.team_a, args.team_b, rows, per, rank, args.season, out, args.preview)


if __name__ == "__main__":
    main()
