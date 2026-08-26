"""Round-by-round expected votes for one player, as a PNG for a tweet.

    python scripts/round_votes_chart.py "Sam Walsh"
    python scripts/round_votes_chart.py "Sam Walsh" --total

Portrait 4:5 at 2400x3000, matching countdown_card.py so a countdown post's two
images sit in the same design language. Writes a 350px _timeline.png beside it,
which is the width X actually renders in a phone timeline.

THE SCALE RUNS 0 TO 3, NOT 0 TO THE PLAYER'S BEST
Three votes is the most a game can be worth, so a bar's length reads directly as
"how close was this to a best-on-ground". Scaling to the player's own maximum
would stretch a 2.49 to the full width and imply a perfect game, and would make
every player's chart look identical no matter how big their year was. The cost
is honest: a player with few big games gets a mostly empty chart, which is what
the season was.

A game with almost no expected votes still gets a visible sliver (MIN_BAR), or a
quiet game would be indistinguishable from a bye, and the byes are exactly what
this chart should not be confused about.

ROUND LABELS ARE DISPLAY ROUNDS
From 2024 AFLTables counts Opening Round as Round 1, so its numbers run one
ahead of the AFL's. Raw round 2 is the AFL's Round 1; raw round 1 is Opening
Round and is labelled OR rather than 0, which is what the subtraction would
otherwise produce. Byes are simply absent: the player has no row for a round his
club did not play.
"""

import argparse
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

W, H, S = 1200, 1500, 2          # bars style; the grid style sets its own
OUT_DIR = "drafts"
MAX_VOTES = 3.0
MIN_BAR = 4              # px at S=1, so a played game is never invisible
OPENING_ROUND_FROM = 2024

BG = "#0a1017"
INK, MUTED = "#e9eef3", "#7e8c99"
EMERALD = "#34d399"
TRACK = "#141f2a"
LINE = "#1a2632"

F = r"C:\Windows\Fonts"
FONTS = dict(display="TCB_____.TTF", name="TCB_____.TTF",
             fig="TCB_____.TTF", body="segoeui.ttf", scale=1.02)


def font(role, size):
    return ImageFont.truetype(os.path.join(F, FONTS[role]),
                              int(size * S * FONTS["scale"]))


def rounds_for(player, season=2026):
    g = pd.read_csv(f"predictions/game_level_{season}.csv")
    g = g.drop_duplicates(["Round_num", "ID"], keep="first")
    w = g[g.Player_Name == player].sort_values("Round_num")
    if w.empty:
        raise SystemExit(f"{player} has no {season} games in the prediction file.")
    out = []
    for _, r in w.iterrows():
        rn = int(r.Round_num)
        d = rn - 1 if season >= OPENING_ROUND_FROM else rn
        out.append({"label": "OR" if d == 0 else str(d),
                    "exp": float(r.Exp_Votes)})
    return out, float(w.Exp_Votes.sum())


def draw(player, rows, total, show_total):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m = 56 * S
    right = (W - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    text((m, 44 * S), "CHA CHING", font("display", 29), EMERALD)
    if show_total:
        text((right, 44 * S), f"{total:.1f} EXPECTED VOTES",
             font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)
    text((m, 132 * S), player.upper(), font("name", 80), INK)
    text((m, 236 * S), "ROUND BY ROUND EXPECTED VOTES",
         font("display", 32), MUTED)

    lab_w = 62 * S                      # round label gutter
    x0 = m + lab_w + 18 * S             # bars start
    val_w = 96 * S                      # room for the value at the end
    x1 = right - val_w
    span = x1 - x0

    top = 322 * S
    bot = (H - 78) * S
    n = len(rows)
    pitch = (bot - top) / n
    bar_h = int(pitch * 0.56)

    # Gridlines at 1, 2 and 3 votes, labelled once at the top. A bar's length is
    # only readable as "how close to a three-vote game" if the scale is visible.
    for v in (1, 2, 3):
        gx = x0 + span * (v / MAX_VOTES)
        k.rectangle([gx, top - 26 * S, gx + 1 * S, bot], fill=LINE)
        text((gx, top - 52 * S), str(v), font("display", 24), MUTED, anchor="ma")

    for i, r in enumerate(rows):
        cy = top + pitch * i + pitch / 2
        y0 = int(cy - bar_h / 2)
        text((m + lab_w, cy), r["label"], font("display", 30), MUTED, anchor="rm")
        k.rectangle([x0, y0, x1, y0 + bar_h], fill=TRACK)
        w_px = max(int(span * min(r["exp"], MAX_VOTES) / MAX_VOTES), MIN_BAR * S)
        k.rectangle([x0, y0, x0 + w_px, y0 + bar_h], fill=EMERALD)
        text((x1 + 16 * S, cy), f"{r['exp']:.2f}", font("fig", 30),
             INK if r["exp"] >= 1 else MUTED, anchor="lm")

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"rounds_{slug}.png")
    img.save(path, "PNG", optimize=True)
    prev = os.path.join(OUT_DIR, f"rounds_{slug}_timeline.png")
    img.resize((350, int(350 * H / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


# ── grid style: the Leaderboard's own round cells ─────────────
# Lifted from dashboard._rd_cell so a posted image and the site say the same
# thing in the same language. Three states, deliberately distinct: a blank cell
# is a round the club did not play, a dot is a game that drew nothing, a number
# is a game that did.
#
# Tint runs against 3.0, the most one game can be worth, so a cell means the
# same thing on every player's image. Alpha tops out at 0.34, matching the site.
GRID_W = 1200                    # height is computed from the block count
# Cells per row. The site puts all 25 rounds in one strip and lets you scroll;
# a static image cannot, and 25 across renders at ~14px a cell once X has scaled
# the picture to a phone. Fewer per row means a taller image, and a taller image
# is shown LARGER in the timeline, so the cells grow twice over. 9 is the
# compromise: three rows, still obviously the site's grid.
WRAP = 9


def _tint(v):
    """rgba(52,211,153,a) over the page ground, resolved to a flat RGB."""
    a = 0.34 * min(1.0, v / MAX_VOTES)
    bg = (10, 16, 23)
    em = (52, 211, 153)
    return tuple(int(round(em[i] * a + bg[i] * (1 - a))) for i in range(3))


def all_rounds(player, season=2026):
    """Every round of the season, byes included as None. The site shows them."""
    g = pd.read_csv(f"predictions/game_level_{season}.csv")
    g = g.drop_duplicates(["Round_num", "ID"], keep="first")
    played = dict(zip(g[g.Player_Name == player].Round_num.astype(int),
                      g[g.Player_Name == player].Exp_Votes))
    if not played:
        raise SystemExit(f"{player} has no {season} games in the prediction file.")
    hi = int(g.Round_num.max())
    out = []
    for rn in range(1, hi + 1):
        d = rn - 1 if season >= OPENING_ROUND_FROM else rn
        out.append({"label": "OR" if d == 0 else str(d),
                    "exp": played.get(rn)})
    return out, float(sum(v for v in played.values()))


def draw_grid(player, rows, total, show_total):
    # Height follows the content. Hardcoding it left a third of the canvas empty,
    # which on X means the image is scaled down to fit dead space on screen.
    W2 = GRID_W
    n_blocks = -(-len(rows) // WRAP)
    cw_ = ((W2 - 112)) / WRAP
    ch_ = cw_ * 0.86
    H2 = int(330 + n_blocks * ch_ + (n_blocks - 1) * 66 + 56)
    img = Image.new("RGB", (W2 * S, H2 * S), BG)
    k = ImageDraw.Draw(img)
    m = 56 * S
    right = (W2 - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    text((m, 44 * S), "CHA CHING", font("display", 29), EMERALD)
    if show_total:
        text((right, 44 * S), f"{total:.1f} EXPECTED VOTES",
             font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)
    text((m, 132 * S), player.upper(), font("name", 80), INK)
    text((m, 236 * S), "ROUND BY ROUND EXPECTED VOTES",
         font("display", 32), MUTED)

    blocks = [rows[i:i + WRAP] for i in range(0, len(rows), WRAP)]
    cw = (right - m) / WRAP
    gap = 3 * S                                  # surface gap between fills
    ch = int(cw * 0.86)
    # Type scales with the cell, or a wider wrap just buys whitespace. Tuned so
    # "2.5" sits comfortably inside the box at any wrap.
    fs = int(cw / S * 0.40)
    ls = int(cw / S * 0.26)
    y = 330 * S
    for blk in blocks:
        for i, r in enumerate(blk):
            x = m + cw * i
            text((x + cw / 2, y - 16 * S), r["label"], font("display", ls),
                 MUTED, anchor="md")
            box = [x + gap / 2, y, x + cw - gap / 2, y + ch]
            if r["exp"] is None:
                k.rectangle(box, fill=BG, outline=LINE, width=max(1, S // 2))
                continue
            v = float(r["exp"])
            k.rectangle(box, fill=_tint(v))
            if v < 0.05:
                text((x + cw / 2, y + ch / 2), "·", font("fig", fs),
                     "#48555f", anchor="mm")
            else:
                hot = v >= 1.0
                text((x + cw / 2, y + ch / 2), f"{v:.1f}", font("fig", fs),
                     INK if hot else MUTED, anchor="mm")
        y += ch + 66 * S

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"rounds_{slug}_grid.png")
    img.save(path, "PNG", optimize=True)
    prev = os.path.join(OUT_DIR, f"rounds_{slug}_grid_timeline.png")
    img.resize((350, int(350 * H2 / W2)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--style", choices=("bars", "grid"), default="bars",
                    help="bars = horizontal bar chart; grid = the site's round cells")
    ap.add_argument("--total", action="store_true",
                    help="show the season expected total in the masthead")
    a = ap.parse_args()
    if a.style == "grid":
        rows, total = all_rounds(a.player, a.season)
        p, prev = draw_grid(a.player, rows, total, a.total)
    else:
        rows, total = rounds_for(a.player, a.season)
        p, prev = draw(a.player, rows, total, a.total)
    played = sum(1 for r in rows if r.get("exp") is not None)
    print(f"OK  wrote {p}  ({played} games, {total:.2f} expected votes)")
    print(f"    timeline preview: {prev}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
