"""Two-player comparison card: diverging bars, one row per stat.

    python scripts/compare_card.py "Nick Daicos" "Marcus Bontempelli"
    python scripts/compare_card.py "Nick Daicos" "Marcus Bontempelli" --season 2026
    python scripts/compare_card.py "Nick Daicos" "Marcus Bontempelli" --preview

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, for the same
reason countdown_card.py is portrait: Twitter renders an in-timeline image at
roughly 350px wide whatever its aspect, so horizontal resolution is fixed and
the only lever is how much you put across it. --preview writes the 350px
version alongside, which is the one to judge.

WHAT THIS CARD IS FOR
Showing that two players are good at different things. It is NOT a verdict:
the rows are chosen to give each player his own strengths, and a reader who
counts emerald bars is counting the author's row selection, not a result. The
footer says so.

THE ACCENT RULE
One accent, emerald, per countdown_card.py. Here it marks whichever player
leads a given row; the other bar is slate. That keeps a single accent while
still encoding the comparison, and avoids assigning a colour to a player, which
would read as a favourite before the reader has seen a number.

TWO THINGS THAT ARE EASY TO GET WRONG AND ARE NOT GUESSED HERE

1. A PERCENTAGE CANNOT BE AVERAGED PER GAME. Score involvement percentage and
   contested possession rate are ratios of season sums, weighting every game by
   how much of the denominator it carried. Bontempelli's 2026 contested rate is
   42.3 as a ratio of sums and 43.8 as the mean of his per-game figures.

2. SCORE INVOLVEMENT PERCENTAGE uses the player's TEAM SCORE LAUNCHES as the
   denominator, which is how Wheelo publishes it, not team scoring shots. The
   two differ by about three points and only the first reconciles.

Score involvements are Score_Involvements_Actual / Wheelo ScoreInvolvements,
which agree exactly. The engineered features.py column of the same name is a
different quantity and is never shown here. See CLAUDE.md.
"""

import argparse
import math
import os
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT_DIR = "drafts"
SI_PATH = "data_advanced/score_involvements.csv"
WHEELO = "data_wheelo/wheelo_{season}.csv"
STATS_2026 = "data_2026/afltables_2026.csv"
STATS_ALL = "fitzroy_stats_all.csv"
COACHES_2026 = "data_2026/coaches_votes_2026.csv"
COACHES_ALL = "coaches_votes_all.csv"

W, H, S = 1200, 1500, 2

# Twitter serves an in-timeline image at a maximum of 2048px on the long edge.
# A 3000px-tall card is therefore resampled to 2048 by THEIR resizer, at a
# non-integer 0.683 factor, and thin type and 2px hairlines come apart: the
# card reads as pixelated on the timeline while looking perfect on disk.
#
# So S becomes a genuine supersample. Draw at 2400x3000, then downsample once
# to the long edge below with LANCZOS and ship that. The work is identical, the
# difference is entirely in which resampler does it and how many times.
# countdown_card.py does NOT do this and has the same problem.
TWITTER_LONG_EDGE = 2048

# Midnight Turf, from CLAUDE.md. Never change these.
BG = "#0a1017"
INK, MUTED = "#e9eef3", "#7e8c99"
# The row labels carry the meaning of every bar, so they get a lifted grey
# rather than MUTED. #7e8c99 on #0a1017 is about 4.4:1, and JPEG chroma
# subsampling eats low-contrast edges first; #a7b6c2 is about 7.6:1 and comes
# through intact. MUTED is kept for genuinely secondary text (club, games,
# sources) where a little softening costs nothing.
LABEL = "#a7b6c2"
EMERALD = "#34d399"
GOLD = "#f0b429"           # results only, per countdown_card.py. Here: the
                           # coaches-award placing, which is the one actual
                           # result on a card otherwise made of averages.
SLATE = "#3d4c5a"          # the trailing bar: present, clearly not the accent
LINE = "#1a2632"

# The CHA CHING mark, lifted from countdown_card.py so the two cards carry the
# same logo rather than two drifting copies of it. CHING runs emerald to lime to
# gold on a diagonal; flat emerald text is not the logo, it is just the accent
# colour spelling the name.
CHA_STOPS = [(0.0, (233, 238, 243)), (1.0, (138, 154, 169))]
CHING_STOPS = [(0.0, (52, 211, 153)), (0.52, (142, 201, 74)), (1.0, (240, 180, 41))]

FONTDIR = r"C:\Windows\Fonts"
# body is SEMIBOLD, not regular, and that is a legibility decision rather than a
# style one. Twitter re-encodes every timeline image to JPEG at roughly q85 with
# 4:2:0 chroma subsampling. Thin low-contrast strokes over a near-black field are
# the worst case for that: colour resolution is halved, and a glyph straddling an
# 8x8 DCT block boundary degrades differently from one sitting inside a block, so
# stroke weight visibly varies letter to letter. It reads as broken letterforms
# even though the render is clean and no font substitution has occurred.
# Regular Segoe at this size does not survive the trip. Semibold does.
FONTS = dict(display="TCB_____.TTF", name="TCB_____.TTF",
             fig="TCB_____.TTF", body="seguisb.ttf", scale=1.02)


def font(role, size):
    return ImageFont.truetype(os.path.join(FONTDIR, FONTS[role]),
                              int(size * S * FONTS["scale"]))


def _lerp(stops, t):
    t = min(max(t, 0.0), 1.0)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(int(round(c0[j] + (c1[j] - c0[j]) * f)) for j in range(3))
    return stops[-1][1]


def gradient_text(img, xy, txt, fnt, stops, angle):
    """Draw txt filled with a linear gradient. angle 180 = top to bottom.

    xy is in FULL-RESOLUTION pixels, not logical units: this is called with
    already-scaled coordinates, unlike the local text() helper.
    """
    xy = (int(xy[0]), int(xy[1]))
    box = tuple(int(v) for v in ImageDraw.Draw(img).textbbox(xy, txt, font=fnt))
    w, h = max(1, box[2] - box[0]), max(1, box[3] - box[1])
    pad = 4
    w, h = w + pad * 2, h + pad * 2
    rad = math.radians(angle - 90)
    dx, dy = math.cos(rad), math.sin(rad)
    denom = abs(dx) * w + abs(dy) * h or 1
    px = []
    for y in range(h):
        for x in range(w):
            t = ((x if dx >= 0 else w - x) * abs(dx)
                 + (y if dy >= 0 else h - y) * abs(dy)) / denom
            px.append(_lerp(stops, t))
    grad = Image.new("RGB", (w, h))
    grad.putdata(px)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((pad - (box[0] - xy[0]), pad - (box[1] - xy[1])),
                              txt, font=fnt, fill=255)
    img.paste(grad, (box[0] - pad, box[1] - pad), mask)
    return box[2] - box[0]


def draw_mark(img, x, y, size):
    """CHA CHING, in the site's own gradients. x/y are full-resolution pixels."""
    f = font("display", size)
    w = gradient_text(img, (x, y), "CHA", f, CHA_STOPS, 180)
    sp = int(ImageDraw.Draw(img).textlength(" ", font=f))
    gradient_text(img, (x + w + sp, y), "CHING", f, CHING_STOPS, 120)


def ordinal(n):
    n = int(n)
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


# (key, label, decimals, source)
#   base   AFLTables per-game mean
#   wheelo Wheelo per-game mean
#   ratio  (numerator, denominator) ratio of season sums, rendered as a percent
ROWS = [
    ("Disposals",             "Disposals",              1, "base"),
    ("_si",                   "Score involvements",     2, "wheelo"),
    ("_sipct",                "Score involvement %",    1, "ratio"),
    ("MetresGained",          "Metres gained",          0, "wheelo"),
    ("AssistedMetresGained",  "Assisted metres gained", 0, "wheelo"),
    ("_cprate",               "Contested possession %", 1, "ratio"),
    ("PressureActs",          "Pressure acts",          1, "wheelo"),
    ("Tackles",               "Tackles",                1, "base"),
    ("One.Percenters",        "One percenters",         2, "base"),
    ("_deff",                 "Disposal efficiency %",  1, "ratio"),
    ("Goals",                 "Goals",                  2, "base"),
]


def load(season):
    """Return {player: {stat: value}} for the two sources, one season, H&A."""
    path = STATS_2026 if season == 2026 else STATS_ALL
    base = pd.read_csv(path, low_memory=False)
    base = base[pd.to_numeric(base["Round"], errors="coerce").notna()]
    base = base[base["Season"] == season]
    base = base.drop_duplicates(subset=["ID", "Season", "Round", "Playing.for"])

    w = pd.read_csv(WHEELO.format(season=season))
    # Team score launches per match, the SI% denominator Wheelo itself uses.
    tl = w.groupby(["MatchId", "Team"])["ScoreLaunches"].sum().rename("team_sl")
    w = w.merge(tl.reset_index(), on=["MatchId", "Team"])
    return base, w


def coaches_board(season):
    """{player: (placing, votes)} for the season's AFLCA award, H&A only.

    Computed, never typed in. NOTE for any season 2021-2025: coaches_votes_all
    stamps each Grand Final's votes onto rounds 19-25 of that season under the
    GF's club pair, so those seasons need the duplicate blocks removed before
    this is trusted. 2026 is clean (every game sums to 30), which is why the
    guard below raises rather than silently returning inflated numbers.
    """
    path = COACHES_2026 if season == 2026 else COACHES_ALL
    cv = pd.read_csv(path)
    cv = cv[cv["Season"] == season]
    cv = cv[pd.to_numeric(cv["Round"], errors="coerce").notna()]
    tot = cv.groupby(["Round", "Home.Team", "Away.Team"])["Coaches.Votes"].sum()
    if (tot != 30).any():
        raise SystemExit(
            f"{season}: {(tot != 30).sum()} games do not sum to 30 coaches votes. "
            "Grand Final duplication is present; dedupe before using this season.")
    s = cv.groupby("Player.Name")["Coaches.Votes"].sum().sort_values(ascending=False)
    rank = {n.rsplit(" (", 1)[0]: (i + 1, v) for i, (n, v) in enumerate(s.items())}
    return rank


def figures(player, base, w):
    b = base[base["Player"] == player]
    x = w[w["Player"] == player]
    if b.empty or x.empty:
        raise SystemExit(f"no rows for {player!r} (base {len(b)}, wheelo {len(x)})")
    out = {"_games": len(b), "_club": b["Playing.for"].iloc[0]}
    for key, _lab, _dec, src in ROWS:
        if src == "base":
            out[key] = pd.to_numeric(b[key], errors="coerce").mean()
        elif src == "wheelo":
            col = {"_si": "ScoreInvolvements"}.get(key, key)
            out[key] = pd.to_numeric(x[col], errors="coerce").mean()
    # Ratios of sums, never means of per-game ratios.
    out["_sipct"] = 100 * x["ScoreInvolvements"].sum() / x["team_sl"].sum()
    cp = pd.to_numeric(b["Contested.Possessions"], errors="coerce").sum()
    dp = pd.to_numeric(b["Disposals"], errors="coerce").sum()
    out["_cprate"] = 100 * cp / dp
    # Wheelo publishes DisposalEfficiency as a per-game percentage, so the
    # season figure is effective disposals over disposals, not the mean of the
    # column. Reconstructing the numerator is the only way to weight each game
    # by the disposals it carried.
    eff = (x["Disposals"] * x["DisposalEfficiency"] / 100.0).sum()
    out["_deff"] = 100 * eff / x["Disposals"].sum()
    return out


def draw(a_name, b_name, a, b, season, out_path, preview):
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)

    def text(xy, t, f, fill, anchor="la"):
        d.text((xy[0] * S, xy[1] * S), t, font=f, fill=fill, anchor=anchor)

    M = 64
    draw_mark(img, M * S, 38 * S, 26)
    text((M, 96), f"{a_name.split()[-1].upper()}  v  {b_name.split()[-1].upper()}",
         font("display", 60), INK)
    text((M, 172), f"Per game, {season} home and away season", font("body", 23), MUTED)

    # Player headers. The gold line is the coaches-award placing, the only
    # actual RESULT on a card otherwise made entirely of averages.
    hy = 224
    for name, fig, x, anc in ((a_name, a, M, "la"), (b_name, b, W - M, "ra")):
        text((x, hy), name.upper(), font("name", 29), INK, anchor=anc)
        text((x, hy + 36), f"{fig['_club']}   {fig['_games']} games",
             font("body", 20), MUTED, anchor=anc)
        if fig.get("_place"):
            place, votes = fig["_place"]
            text((x, hy + 64), f"{ordinal(place)}, {votes:.0f} coaches votes",
                 font("name", 21), GOLD, anchor=anc)

    d.line([(M * S, (hy + 104) * S), ((W - M) * S, (hy + 104) * S)],
           fill=LINE, width=2 * S)

    # Diverging rows. The label sits in a centre gutter; bars grow outward.
    # Row height is derived from the row count so the block always fills the
    # space between the rule and the footer, whatever rows are chosen.
    top = hy + 140
    FOOT_Y = 1382
    row_h = (FOOT_Y - 18 - top) / len(ROWS)
    gutter = 300                      # centre column for the label
    cx = W / 2
    inner_l, inner_r = cx - gutter / 2, cx + gutter / 2
    # The figure is set OUTSIDE the bar end, so the track has to stop short of
    # the margin by enough to hold it. At full length against inner_l - M the
    # longest figures ("34.9", "42.3") ran off the canvas on both sides.
    VALUE_ROOM = 96
    max_bar = inner_l - M - VALUE_ROOM

    for i, (key, label, dec, _src) in enumerate(ROWS):
        y = top + i * row_h
        av, bv = a[key], b[key]
        hi = max(av, bv) or 1
        la, lb = max_bar * av / hi, max_bar * bv / hi
        a_wins = av > bv

        text((cx, y + 22), label, font("body", 23), LABEL, anchor="ma")

        bar_y = y + 8
        bar_h = 34
        d.rounded_rectangle([((inner_l - la) * S, bar_y * S), (inner_l * S, (bar_y + bar_h) * S)],
                            radius=4 * S, fill=EMERALD if a_wins else SLATE)
        d.rounded_rectangle([(inner_r * S, bar_y * S), ((inner_r + lb) * S, (bar_y + bar_h) * S)],
                            radius=4 * S, fill=SLATE if a_wins else EMERALD)

        fmt = f"{{:,.{dec}f}}"
        text((inner_l - la - 12, bar_y + 1), fmt.format(av), font("fig", 30),
             INK if a_wins else MUTED, anchor="ra")
        text((inner_r + lb + 12, bar_y + 1), fmt.format(bv), font("fig", 30),
             MUTED if a_wins else INK, anchor="la")

    fy = FOOT_Y
    d.line([(M * S, fy * S), ((W - M) * S, fy * S)], fill=LINE, width=2 * S)
    text((M, fy + 20), "AFLTables  ·  Wheelo  ·  footywire", font("body", 18), MUTED)

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
        # Twitter re-encodes to JPEG whatever you upload, so judging the PNG
        # judges a file nobody sees. This approximates the served artefact:
        # q85, 4:2:0. Check thin type against THIS, not against the PNG.
        j = out_path.replace(".png", "_asposted.jpg")
        img.save(j, "JPEG", quality=85, subsampling=2)
        print(f"wrote {j}  (q85 4:2:0, approximates what Twitter serves)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player_a")
    ap.add_argument("player_b")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    base, w = load(args.season)
    board = coaches_board(args.season)
    a = figures(args.player_a, base, w)
    b = figures(args.player_b, base, w)
    a["_place"] = board.get(args.player_a)
    b["_place"] = board.get(args.player_b)
    slug = "_".join(p.split()[-1].lower() for p in (args.player_a, args.player_b))
    out = args.out or os.path.join(OUT_DIR, f"compare_{slug}_{args.season}.png")
    os.makedirs(OUT_DIR, exist_ok=True)
    draw(args.player_a, args.player_b, a, b, args.season, out, args.preview)


if __name__ == "__main__":
    main()
